from datetime import datetime, timedelta, date
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from . import predictive, ev_battery
from ..db_models import NotificationDB, WarrantyDB
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

    # Expiry soon
    try:
        if warranty.expiry_date:
            today = date.today()
            days_left = (warranty.expiry_date.date() if hasattr(warranty.expiry_date, "date") else warranty.expiry_date) - today
            if hasattr(days_left, "days"):
                days = days_left.days
                if 0 <= days <= 30:
                    create_notification(
                        db=db,
                        user_id=user_id,
                        warranty_id=warranty_id,
                        type="expiry_soon",
                        title="Warranty expiring soon",
                        message=f"Your warranty expires in {days} days. Consider backing up receipts or buying extended cover.",
                        severity="warning",
                    )
    except Exception:
        pass
