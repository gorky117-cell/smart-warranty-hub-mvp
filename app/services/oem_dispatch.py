from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db_models import (
    BehaviourProfile,
    OemIssueSignalDB,
    SymptomSearch,
    TelemetryEventDB,
    WarrantyDB,
)
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
        "min_issue_count": 1,
        "min_issue_severity": 0.5,
        "issue_lookback_days": 90,
        "include_regions": [],
        "exclude_regions": [],
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


def run_weekly_dispatch(db: Session, *, dry_run: bool = False) -> Dict:
    policy = get_dispatch_policy()
    if not bool(policy.get("enabled", True)):
        return {"ok": True, "enabled": False, "sent": 0, "blocked": 0, "eligible": 0, "targets": 0}

    allowed_kinds = {str(x).strip() for x in (policy.get("allowed_kinds") or []) if str(x).strip()}
    max_targets = int(policy.get("max_targets_per_run", 250) or 250)
    min_issue_count = int(policy.get("min_issue_count", 1) or 1)
    min_issue_sev = float(policy.get("min_issue_severity", 0.5) or 0.5)
    issue_lookback_days = int(policy.get("issue_lookback_days", 90) or 90)
    include_regions = list(policy.get("include_regions") or [])
    exclude_regions = list(policy.get("exclude_regions") or [])
    sender_user_id = str(policy.get("sender_user_id") or "oem-system")
    sender_role = str(policy.get("sender_role") or "oem")

    pairs = _recipient_pairs(db)[: max(1, max_targets)]
    sent = 0
    blocked = 0
    eligible = 0
    inspected = 0

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
            eligible += 1
            title = "Important product update"
            msg = (
                "We detected an important reliability update for your registered product. "
                "Please review care and service guidance in your dashboard."
            )
            if dry_run:
                continue
            res = send_oem_message(
                db,
                sender_user_id=sender_user_id,
                sender_role=sender_role,
                recipient_user_id=user_id,
                kind="important_update",
                title=title,
                message=msg,
                warranty_id=warranty_id,
                brand=brand,
                model_code=model_code,
                region=region,
                metadata={
                    "dispatch_mode": "weekly_auto",
                    "issue_count": issue_count,
                    "issue_avg_severity": issue_sev,
                },
            )
            if res.get("decision") == "sent":
                sent += 1
                continue
            blocked += 1

        # 2) Product recommendation dispatch (only if enabled by policy).
        if "product_recommendation" in allowed_kinds and bool(policy.get("send_product_recommendations", True)):
            eligible += 1
            title = "Helpful recommendation for your product"
            msg = (
                "Based on your usage pattern and recent reliability signals, we found a relevant recommendation "
                "that may reduce failure risk."
            )
            if dry_run:
                continue
            res = send_oem_message(
                db,
                sender_user_id=sender_user_id,
                sender_role=sender_role,
                recipient_user_id=user_id,
                kind="product_recommendation",
                title=title,
                message=msg,
                warranty_id=warranty_id,
                brand=brand,
                model_code=model_code,
                region=region,
                metadata={
                    "dispatch_mode": "weekly_auto",
                },
            )
            if res.get("decision") == "sent":
                sent += 1
            else:
                blocked += 1

    return {
        "ok": True,
        "enabled": True,
        "targets": inspected,
        "eligible": eligible,
        "sent": sent,
        "blocked": blocked,
        "policy": policy,
    }
