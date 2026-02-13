from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from ..db_models import (
    BehaviourProfile,
    OemIssueSignalDB,
    SymptomSearch,
    TelemetryEventDB,
    UserDB,
    WarrantyDB,
)
from .notifications import create_oem_notification
from .oem_communication import send_oem_message


def _policy_path() -> Path:
    return Path(os.getenv("OEM_DISPATCH_POLICY_FILE", "data/oem_dispatch_policy.json"))


def _default_policy() -> Dict:
    return {
        "enabled": True,
        "plan_tier": "free",
        "allowed_kinds": ["important_update", "product_recommendation"],
        "send_product_recommendations": True,
        "max_targets_per_run": 250,
        "min_eligible_for_send": 2,
        "min_issue_count": 1,
        "min_issue_severity": 0.5,
        "issue_lookback_days": 90,
        "include_regions": [],
        "exclude_regions": [],
        "notify_oem_when_no_signal": True,
        "notify_oem_summary": True,
        "sender_user_id": "oem-system",
        "sender_role": "oem",
    }


def get_dispatch_policy() -> Dict:
    path = _policy_path()
    if not path.exists():
        return _default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _default_policy()
        merged = _default_policy()
        merged.update(raw)
        return merged
    except Exception:
        return _default_policy()


def set_dispatch_policy(payload: Dict) -> Dict:
    if not isinstance(payload, dict):
        payload = {}
    current = get_dispatch_policy()
    current.update(payload)
    path = _policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def _normalize(v: Optional[str]) -> Optional[str]:
    val = (v or "").strip()
    return val or None


def _region_allowed(region: Optional[str], include_regions: List[str], exclude_regions: List[str]) -> bool:
    r = (region or "").strip().lower()
    inc = {(x or "").strip().lower() for x in include_regions or [] if (x or "").strip()}
    exc = {(x or "").strip().lower() for x in exclude_regions or [] if (x or "").strip()}
    if r and r in exc:
        return False
    if inc and (not r or r not in inc):
        return False
    return True


def _recipient_pairs(db: Session) -> List[Tuple[str, str]]:
    # Build unique (user_id, warranty_id) candidates from behavior/symptoms/telemetry.
    out: Set[Tuple[str, str]] = set()

    for row in db.query(BehaviourProfile.user_id, BehaviourProfile.warranty_id).all():
        if row[0] and row[1]:
            out.add((str(row[0]), str(row[1])))

    for row in db.query(SymptomSearch.user_id, SymptomSearch.warranty_id).all():
        if row[0] and row[1]:
            out.add((str(row[0]), str(row[1])))

    for row in db.query(TelemetryEventDB.user_id, TelemetryEventDB.warranty_id).all():
        if row[0] and row[1]:
            out.add((str(row[0]), str(row[1])))

    return sorted(out)


def _issue_strength(
    db: Session,
    *,
    brand: Optional[str],
    model_code: Optional[str],
    region: Optional[str],
    lookback_days: int,
) -> Tuple[int, float]:
    if not brand:
        return 0, 0.0
    now = datetime.utcnow()
    q = db.query(OemIssueSignalDB).filter(OemIssueSignalDB.created_at >= now - timedelta(days=max(1, lookback_days)))
    q = q.filter(OemIssueSignalDB.brand == brand)
    if model_code:
        q = q.filter(OemIssueSignalDB.model_code == model_code)
    if region:
        q = q.filter((OemIssueSignalDB.region == region) | (OemIssueSignalDB.region.is_(None)))
    rows = q.all()
    if not rows:
        return 0, 0.0
    total_count = sum(int(r.count or 1) for r in rows)
    avg_severity = float(sum(float(r.severity or 0.0) for r in rows) / max(len(rows), 1))
    return total_count, avg_severity


def _oem_recipients(db: Session, sender_user_id: str) -> List[str]:
    rows = db.query(UserDB.username).filter(UserDB.role == "oem").all()
    recipients = [str(r[0]) for r in rows if r and r[0]]
    if not recipients and sender_user_id:
        recipients.append(sender_user_id)
    # unique, preserve order
    out: List[str] = []
    for x in recipients:
        if x not in out:
            out.append(x)
    return out


def _notify_oems(db: Session, sender_user_id: str, title: str, message: str, severity: str = "info") -> int:
    count = 0
    for user_id in _oem_recipients(db, sender_user_id):
        try:
            created = create_oem_notification(
                db=db,
                user_id=user_id,
                ntype="oem_dispatch_summary",
                title=title,
                message=message,
                severity=severity,
            )
            if created:
                count += 1
        except Exception:
            pass
    return count


def run_weekly_dispatch(db: Session, *, dry_run: bool = False) -> Dict:
    policy = get_dispatch_policy()
    if not bool(policy.get("enabled", True)):
        return {"ok": True, "enabled": False, "sent": 0, "blocked": 0, "eligible": 0, "targets": 0}

    allowed_kinds = {str(x).strip() for x in (policy.get("allowed_kinds") or []) if str(x).strip()}
    max_targets = int(policy.get("max_targets_per_run", 250) or 250)
    min_eligible_for_send = int(policy.get("min_eligible_for_send", 2) or 2)
    min_issue_count = int(policy.get("min_issue_count", 1) or 1)
    min_issue_sev = float(policy.get("min_issue_severity", 0.5) or 0.5)
    issue_lookback_days = int(policy.get("issue_lookback_days", 90) or 90)
    include_regions = list(policy.get("include_regions") or [])
    exclude_regions = list(policy.get("exclude_regions") or [])
    sender_user_id = str(policy.get("sender_user_id") or "oem-system")
    sender_role = str(policy.get("sender_role") or "oem")

    pairs = _recipient_pairs(db)[: max(1, max_targets)]
    inspected = 0
    candidate_actions: List[Dict[str, str]] = []

    for user_id, warranty_id in pairs:
        inspected += 1
        w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
        if not w:
            continue
        brand = _normalize(w.brand)
        model_code = _normalize(w.model_code)
        region = _normalize(w.region_code)
        if not _region_allowed(region, include_regions, exclude_regions):
            continue

        issue_count, issue_sev = _issue_strength(
            db,
            brand=brand,
            model_code=model_code,
            region=region,
            lookback_days=issue_lookback_days,
        )

        # 1) Important update dispatch based on OEM issue strength.
        if "important_update" in allowed_kinds and issue_count >= min_issue_count and issue_sev >= min_issue_sev:
            candidate_actions.append(
                {
                    "recipient_user_id": user_id,
                    "warranty_id": warranty_id,
                    "brand": brand or "",
                    "model_code": model_code or "",
                    "region": region or "",
                    "kind": "important_update",
                    "title": "Important product update",
                    "message": (
                        "We detected an important reliability update for your registered product. "
                        "Please review care and service guidance in your dashboard."
                    ),
                    "issue_count": str(issue_count),
                    "issue_avg_severity": str(issue_sev),
                }
            )
            continue

        # 2) Product recommendation dispatch (only if enabled by policy).
        if "product_recommendation" in allowed_kinds and bool(policy.get("send_product_recommendations", True)):
            candidate_actions.append(
                {
                    "recipient_user_id": user_id,
                    "warranty_id": warranty_id,
                    "brand": brand or "",
                    "model_code": model_code or "",
                    "region": region or "",
                    "kind": "product_recommendation",
                    "title": "Helpful recommendation for your product",
                    "message": (
                        "Based on your usage pattern and recent reliability signals, we found a relevant recommendation "
                        "that may reduce failure risk."
                    ),
                }
            )

    eligible = len(candidate_actions)
    if dry_run:
        return {
            "ok": True,
            "enabled": True,
            "targets": inspected,
            "eligible": eligible,
            "sent": 0,
            "blocked": 0,
            "decision": "dry_run",
            "policy": policy,
        }

    if eligible < max(1, min_eligible_for_send):
        notified = 0
        if bool(policy.get("notify_oem_when_no_signal", True)):
            notified = _notify_oems(
                db,
                sender_user_id=sender_user_id,
                title="Monthly analysis not yet conclusive",
                message=(
                    "No strong product/user signal pattern was found this cycle. "
                    "System will continue weekly analysis and re-evaluate next month."
                ),
                severity="info",
            )
        return {
            "ok": True,
            "enabled": True,
            "targets": inspected,
            "eligible": eligible,
            "sent": 0,
            "blocked": 0,
            "decision": "insufficient_signal",
            "oem_notified": notified,
            "policy": policy,
        }

    sent = 0
    blocked = 0
    for action in candidate_actions:
        res = send_oem_message(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=action["recipient_user_id"],
            kind=action["kind"],
            title=action["title"],
            message=action["message"],
            warranty_id=action["warranty_id"],
            brand=action["brand"] or None,
            model_code=action["model_code"] or None,
            region=action["region"] or None,
            metadata={
                "dispatch_mode": "monthly_auto",
                "issue_count": action.get("issue_count"),
                "issue_avg_severity": action.get("issue_avg_severity"),
            },
        )
        if res.get("decision") == "sent":
            sent += 1
        else:
            blocked += 1

    oem_notified = 0
    if bool(policy.get("notify_oem_summary", True)):
        oem_notified = _notify_oems(
            db,
            sender_user_id=sender_user_id,
            title="Monthly dispatch summary",
            message=f"Dispatch complete. Eligible={eligible}, Sent={sent}, Blocked={blocked}.",
            severity="info",
        )

    return {
        "ok": True,
        "enabled": True,
        "targets": inspected,
        "eligible": eligible,
        "sent": sent,
        "blocked": blocked,
        "decision": "completed",
        "oem_notified": oem_notified,
        "policy": policy,
    }
