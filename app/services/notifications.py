import os
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from . import predictive, ev_battery
from ..db_models import NotificationDB, WarrantyDB, RiskSnapshotDB
from ..storage import generate_id

# existing functions ----------------------------------------------------------------


def _ensure_schema(db: Session):
    """
    Backward-compatible guard: ensure new columns exist on the notifications table.
    Adds nullable audience/brand/region columns if missing (SQLite-safe).
    """
    try:
        cols = {row[1] for row in db.execute(text("PRAGMA table_info(notifications)")).fetchall()}
        alters = []
        if "audience" not in cols:
            alters.append("ALTER TABLE notifications ADD COLUMN audience TEXT DEFAULT 'user'")
        if "brand" not in cols:
            alters.append("ALTER TABLE notifications ADD COLUMN brand TEXT")
        if "region" not in cols:
            alters.append("ALTER TABLE notifications ADD COLUMN region TEXT")
        for stmt in alters:
            db.execute(text(stmt))
        if alters:
            db.commit()
    except Exception:
        # Do not block main flow if pragma fails; queries may still work if schema is current.
        pass


def _to_dict(n: NotificationDB) -> dict:
    return {
        "id": n.id,
        "user_id": n.user_id,
        "warranty_id": n.warranty_id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "severity": n.severity,
        "is_read": bool(n.is_read),
        "created_at": n.created_at,
    }


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(
        start.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
            month - 1
        ],
    )
    return date(year, month, day)


def resolve_expiry_date(warranty: Optional[WarrantyDB]) -> Optional[date]:
    if not warranty:
        return None
    direct = _as_date(getattr(warranty, "expiry_date", None))
    if direct:
        return direct
    purchase = _as_date(getattr(warranty, "purchase_date", None))
    coverage = getattr(warranty, "coverage_months", None)
    if purchase and coverage:
        try:
            return _add_months(purchase, int(coverage))
        except Exception:
            return None
    return None


def _parse_expiry_stages() -> List[int]:
    raw = os.getenv("EXPIRY_REMINDER_STAGE_DAYS", "30,7,0")
    vals: Set[int] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = int(part)
        except ValueError:
            continue
        if v >= 0:
            vals.add(v)
    if not vals:
        vals = {30, 7, 0}
    return sorted(vals)


def _closest_stage(days_left: int, stages: List[int]) -> Optional[int]:
    eligible = [s for s in stages if days_left <= s]
    if not eligible:
        return None
    return min(eligible)


def _notification_exists(db: Session, user_id: str, warranty_id: str, ntype: str) -> bool:
    row = (
        db.query(NotificationDB.id)
        .filter(
            NotificationDB.user_id == user_id,
            NotificationDB.warranty_id == warranty_id,
            NotificationDB.type == ntype,
            NotificationDB.audience == "user",
        )
        .first()
    )
    return bool(row)


def _expiry_payload(days_left: int, expiry_dt: date) -> Tuple[str, str, str]:
    if days_left < 0:
        days_over = abs(days_left)
        return (
            "expiry_expired",
            "Warranty expired",
            f"Your warranty expired {days_over} day(s) ago on {expiry_dt.isoformat()}.",
        )
    if days_left == 0:
        return (
            "expiry_due",
            "Warranty expires today",
            f"Your warranty expires today ({expiry_dt.isoformat()}). Save documents and claim if needed.",
        )
    stage = _closest_stage(days_left, _parse_expiry_stages())
    if stage is None:
        return ("", "", "")
    if stage <= 7:
        return (
            f"expiry_{stage}d",
            f"Warranty expires in {days_left} day(s)",
            f"Your warranty ends on {expiry_dt.isoformat()} ({days_left} day(s) left). Finalize any pending claim steps now.",
        )
    return (
        f"expiry_{stage}d",
        f"Warranty expires in {days_left} day(s)",
        f"Your warranty ends on {expiry_dt.isoformat()} ({days_left} day(s) left). Keep invoice and service docs ready.",
    )


def create_expiry_notifications(
    db: Session,
    user_id: str,
    warranty_id: str,
    warranty: Optional[WarrantyDB] = None,
) -> List[dict]:
    """
    Create staged expiry reminders (30d/7d/today/expired) exactly once per stage+user+warranty.
    Returns list of created notifications (0 or 1).
    """
    _ensure_schema(db)
    w = warranty or db.query(WarrantyDB).filter(WarrantyDB.id == warranty_id).first()
    expiry_dt = resolve_expiry_date(w)
    if not expiry_dt:
        return []
    days_left = (expiry_dt - date.today()).days
    ntype, title, message = _expiry_payload(days_left, expiry_dt)
    if not ntype:
        return []
    if _notification_exists(db, user_id, warranty_id, ntype):
        return []
    severity = "critical" if ntype in ("expiry_due", "expiry_expired") else "warning"
    created = create_notification(
        db=db,
        user_id=user_id,
        warranty_id=warranty_id,
        type=ntype,
        title=title,
        message=message,
        severity=severity,
    )
    return [created] if created else []


def _distinct_user_warranty_pairs_for_expiry(db: Session, limit: int = 2000) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    rows_a = (
        db.query(NotificationDB.user_id, NotificationDB.warranty_id)
        .filter(NotificationDB.user_id.isnot(None), NotificationDB.warranty_id.isnot(None))
        .limit(max(1, int(limit)))
        .all()
    )
    for user_id, warranty_id in rows_a:
        if user_id and warranty_id:
            pairs.add((str(user_id), str(warranty_id)))
    rows_b = (
        db.query(RiskSnapshotDB.user_id, RiskSnapshotDB.warranty_id)
        .filter(RiskSnapshotDB.user_id.isnot(None), RiskSnapshotDB.warranty_id.isnot(None))
        .limit(max(1, int(limit)))
        .all()
    )
    for user_id, warranty_id in rows_b:
        if user_id and warranty_id:
            pairs.add((str(user_id), str(warranty_id)))
    return pairs


def refresh_expiry_notifications(db: Session) -> Dict[str, int]:
    """
    Periodic sweep to send staged expiry reminders for existing user+warranty pairs.
    Safe to run repeatedly (idempotent by stage type checks).
    """
    _ensure_schema(db)
    scan_limit = int(os.getenv("EXPIRY_REMINDER_SCAN_LIMIT", "1500"))
    stages = _parse_expiry_stages()
    max_days = max(stages) if stages else 30
    scanned = 0
    created = 0
    skipped_no_expiry = 0
    pairs = _distinct_user_warranty_pairs_for_expiry(db, limit=scan_limit)
    warranty_cache: Dict[str, Optional[WarrantyDB]] = {}
    for user_id, warranty_id in pairs:
        scanned += 1
        if scanned > scan_limit:
            break
        if warranty_id not in warranty_cache:
            warranty_cache[warranty_id] = db.query(WarrantyDB).filter(WarrantyDB.id == warranty_id).first()
        w = warranty_cache[warranty_id]
        exp = resolve_expiry_date(w)
        if not exp:
            skipped_no_expiry += 1
            continue
        days_left = (exp - date.today()).days
        # Only evaluate near-expiry and overdue windows.
        if days_left > max_days:
            continue
        created += len(create_expiry_notifications(db=db, user_id=user_id, warranty_id=warranty_id, warranty=w))
    return {
        "scanned": scanned,
        "created": created,
        "skipped_no_expiry": skipped_no_expiry,
    }


def create_notification(
    user_id: str,
    warranty_id: str,
    type: str,
    title: str,
    message: str,
    severity: str = "info",
    db: Optional[Session] = None,
    audience: str = "user",
    brand: Optional[str] = None,
    region: Optional[str] = None,
) -> Optional[dict]:
    """
    Optional db injection; if not provided, will open a new session.
    Dedupe: skip if same type/warranty/user unread within last 7 days.
    """
    from ..db import SessionLocal  # local import to avoid cycle

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        _ensure_schema(db)
        window_start = datetime.utcnow() - timedelta(days=7)
        existing = (
            db.query(NotificationDB)
            .filter(
                NotificationDB.user_id == user_id,
                NotificationDB.warranty_id == warranty_id,
                NotificationDB.type == type,
                NotificationDB.audience == audience,
                NotificationDB.is_read == 0,
                NotificationDB.created_at >= window_start,
            )
            .first()
        )
        if existing:
            return _to_dict(existing)
        n = NotificationDB(
            id=generate_id("ntf"),
            user_id=user_id,
            warranty_id=warranty_id,
            audience=audience or "user",
            brand=brand,
            region=region,
            type=type,
            title=title,
            message=message,
            severity=severity,
            is_read=0,
            created_at=datetime.utcnow(),
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return _to_dict(n)
    finally:
        if close_db:
            db.close()


def list_notifications(user_id: str, only_unread: bool = False, db: Optional[Session] = None) -> List[dict]:
    from ..db import SessionLocal

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        _ensure_schema(db)
        q = db.query(NotificationDB).filter(NotificationDB.user_id == user_id)
        if only_unread:
            q = q.filter(NotificationDB.is_read == 0)
        q = q.order_by(NotificationDB.created_at.desc())
        return [_to_dict(n) for n in q.all()]
    finally:
        if close_db:
            db.close()


def mark_notification_read(user_id: str, notification_id: str, db: Optional[Session] = None) -> bool:
    from ..db import SessionLocal

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        _ensure_schema(db)
        n = (
            db.query(NotificationDB)
            .filter(
                NotificationDB.id == notification_id,
                NotificationDB.user_id == user_id,
            )
            .first()
        )
        if not n:
            return False
        n.is_read = 1
        db.add(n)
        db.commit()
        return True
    finally:
        if close_db:
            db.close()

# OEM helpers -----------------------------------------------------------------------


def create_oem_notification(
    db: Session,
    user_id: str,
    ntype: str,
    title: str,
    message: str,
    severity: str = "warning",
    brand: Optional[str] = None,
    region: Optional[str] = None,
) -> Optional[dict]:
    """
    Create an OEM-facing notification for a specific OEM/admin user.
    Dedupe: 7-day window on (user_id, warranty_id=None, type, audience='oem', unread).

    # Example usage (manual testing only):
    # create_oem_notification(db, user_id='oem-1', ntype='oem_high_risk_cluster',
    #   title='High-risk cluster detected', message='More than 15% HIGH risk in region.', severity='warning')
    """
    return create_notification(
        user_id=user_id,
        warranty_id=None,
        type=ntype,
        title=title,
        message=message,
        severity=severity,
        db=db,
        audience="oem",
        brand=brand,
        region=region,
    )


def list_notifications_for_oem(
    db: Session,
    user_id: str,
    only_unread: bool = False,
    limit: int = 50,
) -> List[NotificationDB]:
    _ensure_schema(db)
    q = (
        db.query(NotificationDB)
        .filter(NotificationDB.audience == "oem", NotificationDB.user_id == user_id)
        .order_by(NotificationDB.created_at.desc())
    )
    if only_unread:
        q = q.filter(NotificationDB.is_read == 0)
    return q.limit(limit).all()


def mark_notification_read_for_oem(
    db: Session,
    notification_id: str,
    user_id: str,
) -> Optional[NotificationDB]:
    _ensure_schema(db)
    n = (
        db.query(NotificationDB)
        .filter(
            NotificationDB.id == notification_id,
            NotificationDB.audience == "oem",
            NotificationDB.user_id == user_id,
        )
        .first()
    )
    if not n:
        return None
    if not n.is_read:
        n.is_read = True
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


# new helper ------------------------------------------------------------------------


def run_initial_analysis_and_notifications(db: Session, user_id: str, warranty_id: str) -> None:
    """
    Load warranty, run predictive + EV scoring, and create onboarding + risk + expiry notifications.
    Uses existing dedupe in create_notification.
    """
    warranty: Optional[WarrantyDB] = (
        db.query(WarrantyDB).filter(WarrantyDB.id == warranty_id).first()
    )
    if not warranty:
        return

    # Onboarded
    create_notification(
        db=db,
        user_id=user_id,
        warranty_id=warranty_id,
        type="warranty_onboarded",
        title="Warranty onboarded",
        message=f"We’ve registered your {getattr(warranty, 'product_name', '') or 'device'} and started health checks.",
        severity="info",
    )

    # Predictive risk (reuse score_warranty)
    try:
        risk_result = predictive.score_warranty(user_id, warranty_id)
    except Exception:
        risk_result = None
    if risk_result:
        label = (risk_result.get("risk_label") or "LOW").upper()
        score = float(risk_result.get("risk_score", 0.0) or 0.0)
        try:
            db.add(
                RiskSnapshotDB(
                    user_id=user_id,
                    warranty_id=warranty_id,
                    risk_label=label,
                    risk_score=score,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        if label == "MEDIUM":
            create_notification(
                db=db,
                user_id=user_id,
                warranty_id=warranty_id,
                type="risk_medium",
                title="Medium risk detected",
                message="Our checks suggest this device may need some care soon.",
                severity="warning",
            )
        elif label == "HIGH":
            create_notification(
                db=db,
                user_id=user_id,
                warranty_id=warranty_id,
                type="risk_high",
                title="High risk detected",
                message="This device shows a high risk of issues. Consider backup or service.",
                severity="critical",
            )

    # EV battery risk if EV
    try:
        if getattr(warranty, "product_type", None) in (3, 4):
            try:
                ev_features = ev_battery.build_features_from_db(db, user_id, warranty_id)
            except Exception:
                ev_features = None
            if ev_features:
                ev_res = ev_battery.score_ev_battery(ev_features)
                if ev_res and ev_res.get("risk_label") in ("MEDIUM", "HIGH"):
                    create_notification(
                        db=db,
                        user_id=user_id,
                        warranty_id=warranty_id,
                        type="ev_battery_risk",
                        title="EV battery health alert",
                        message="We’ve detected potential stress on your EV battery. See EV tips in your dashboard.",
                        severity="warning" if ev_res["risk_label"] == "MEDIUM" else "critical",
                    )
    except Exception:
        pass

    try:
        create_expiry_notifications(db=db, user_id=user_id, warranty_id=warranty_id, warranty=warranty)
    except Exception:
        pass
