from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..db_models import (
    BehaviourProfile,
    OemCommunicationTraceDB,
    OemIssueSignalDB,
    SymptomSearch,
    UserDB,
    WarrantyDB,
)
from .notifications import create_notification
from .predictive import score_warranty


ALLOWED_KINDS = {"important_update", "product_recommendation"}
_MIN_DAYS = int(os.getenv("OEM_CONTACT_MIN_DAYS", "180"))
_MAX_PER_WINDOW = int(os.getenv("OEM_CONTACT_MAX_PER_WINDOW", "1"))
_REQUIRE_IMPORTANCE = os.getenv("OEM_CONTACT_REQUIRE_IMPORTANCE", "true").strip().lower() in ("1", "true", "yes")
_ALLOW_MARKETING = os.getenv("OEM_CONTACT_ALLOW_MARKETING", "false").strip().lower() in ("1", "true", "yes")
_ISSUE_LOOKBACK_DAYS = int(os.getenv("OEM_IMPORTANCE_ISSUE_LOOKBACK_DAYS", "90"))
_SYMPTOM_LOOKBACK_DAYS = int(os.getenv("OEM_IMPORTANCE_SYMPTOM_LOOKBACK_DAYS", "30"))
_EXPIRY_SOON_DAYS = int(os.getenv("OEM_IMPORTANCE_EXPIRY_DAYS", "45"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _record_trace(
    db: Session,
    *,
    sender_user_id: str,
    sender_role: str,
    recipient_user_id: str,
    kind: str,
    channel: str,
    title: str,
    message: str,
    decision: str,
    blocked_reason: Optional[str] = None,
    reason_code: Optional[str] = None,
    reason_text: Optional[str] = None,
    warranty_id: Optional[str] = None,
    brand: Optional[str] = None,
    model_code: Optional[str] = None,
    product_type: Optional[str] = None,
    region: Optional[str] = None,
    trace_json: Optional[Dict[str, Any]] = None,
) -> OemCommunicationTraceDB:
    row = OemCommunicationTraceDB(
        sender_user_id=sender_user_id,
        sender_role=sender_role,
        recipient_user_id=recipient_user_id,
        warranty_id=warranty_id,
        kind=kind,
        channel=channel or "in_app",
        title=title,
        message=message,
        brand=brand,
        model_code=model_code,
        product_type=product_type,
        region=region,
        reason_code=reason_code,
        reason_text=reason_text,
        decision=decision,
        blocked_reason=blocked_reason,
        trace_json=_json_safe(trace_json or {}),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _recent_sent_count(db: Session, recipient_user_id: str) -> int:
    window_start = datetime.utcnow() - timedelta(days=max(0, _MIN_DAYS))
    return (
        db.query(OemCommunicationTraceDB)
        .filter(
            OemCommunicationTraceDB.recipient_user_id == recipient_user_id,
            OemCommunicationTraceDB.decision == "sent",
            OemCommunicationTraceDB.created_at >= window_start,
        )
        .count()
    )


def _resolve_warranty_context(
    db: Session,
    warranty_id: Optional[str],
    brand: Optional[str],
    model_code: Optional[str],
    product_type: Optional[str],
    region: Optional[str],
) -> Dict[str, Optional[str]]:
    out = {
        "brand": (brand or "").strip() or None,
        "model_code": (model_code or "").strip() or None,
        "product_type": (product_type or "").strip() or None,
        "region": (region or "").strip() or None,
    }
    if not warranty_id:
        return out
    w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
    if not w:
        return out
    out["brand"] = out["brand"] or w.brand
    out["model_code"] = out["model_code"] or w.model_code
    out["region"] = out["region"] or w.region_code
    out["product_type"] = out["product_type"] or None
    return out


def _collect_importance_signals(
    db: Session,
    *,
    recipient_user_id: str,
    warranty_id: Optional[str],
    kind: str,
    brand: Optional[str],
    model_code: Optional[str],
    region: Optional[str],
) -> Dict[str, Any]:
    now = datetime.utcnow()
    reasons: List[str] = []
    reason_codes: List[str] = []
    detail: Dict[str, Any] = {}

    # 1) Risk signal from predictive model if this is a known warranty
    if warranty_id:
        try:
            scored = score_warranty(recipient_user_id, warranty_id)
            label = str(scored.get("risk_label", "")).upper()
            score = float(scored.get("risk_score", 0.0))
            detail["risk_label"] = label
            detail["risk_score"] = score
            if label in ("MEDIUM", "HIGH"):
                reason_codes.append("risk_medium_high")
                reasons.append(f"Predictive risk is {label}.")
        except Exception:
            pass

    # 2) Warranty expiry signal
    if warranty_id:
        w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
        if w and w.expiry_date:
            try:
                days_left = (w.expiry_date.date() if hasattr(w.expiry_date, "date") else w.expiry_date) - datetime.utcnow().date()
                detail["days_to_expiry"] = int(days_left.days)
                if 0 <= int(days_left.days) <= _EXPIRY_SOON_DAYS:
                    reason_codes.append("warranty_expiring_soon")
                    reasons.append(f"Warranty expires in {int(days_left.days)} days.")
            except Exception:
                pass

    # 3) OEM issue signals
    q = db.query(OemIssueSignalDB).filter(OemIssueSignalDB.created_at >= now - timedelta(days=max(1, _ISSUE_LOOKBACK_DAYS)))
    if brand:
        q = q.filter(OemIssueSignalDB.brand == brand)
    if model_code:
        q = q.filter(OemIssueSignalDB.model_code == model_code)
    if region:
        q = q.filter(OemIssueSignalDB.region == region)
    issue_rows = q.all()
    issue_count = sum(int(r.count or 1) for r in issue_rows) if issue_rows else 0
    detail["issue_signal_count"] = issue_count
    if issue_count > 0:
        reason_codes.append("oem_issue_signal")
        reasons.append(f"Recent OEM issue signals found ({issue_count}).")

    # 4) Behaviour/symptom matching for product recommendations
    if kind == "product_recommendation":
        if warranty_id:
            profile = (
                db.query(BehaviourProfile)
                .filter_by(user_id=recipient_user_id, warranty_id=warranty_id)
                .order_by(BehaviourProfile.last_updated_at.desc().nullslast(), BehaviourProfile.id.desc())
                .first()
            )
        else:
            profile = (
                db.query(BehaviourProfile)
                .filter_by(user_id=recipient_user_id)
                .order_by(BehaviourProfile.last_updated_at.desc().nullslast(), BehaviourProfile.id.desc())
                .first()
            )
        if profile:
            detail["behaviour_score"] = float(profile.behaviour_score or 0.0)
            detail["care_score"] = float(profile.care_score or 0.0)
            detail["responsiveness_score"] = float(profile.responsiveness_score or 0.0)
            if (profile.care_score or 0.0) <= 0.45:
                reason_codes.append("behaviour_low_care")
                reasons.append("Care score is low; recommendation can reduce failure risk.")
            if (profile.responsiveness_score or 0.0) <= 0.45:
                reason_codes.append("behaviour_low_responsiveness")
                reasons.append("Responsiveness score is low; recommendation is timely.")

        sq = db.query(SymptomSearch).filter(
            SymptomSearch.user_id == recipient_user_id,
            SymptomSearch.created_at >= now - timedelta(days=max(1, _SYMPTOM_LOOKBACK_DAYS)),
        )
        if warranty_id:
            sq = sq.filter(SymptomSearch.warranty_id == warranty_id)
        symptom_count = sq.count()
        detail["recent_symptom_searches"] = symptom_count
        if symptom_count >= 2:
            reason_codes.append("symptom_search_spike")
            reasons.append(f"User searched symptoms {symptom_count} times recently.")

    eligible = len(reason_codes) > 0
    return {
        "eligible": eligible,
        "reason_codes": reason_codes,
        "reason_text": " ".join(reasons).strip() or None,
        "detail": detail,
    }


def send_oem_message(
    db: Session,
    *,
    sender_user_id: str,
    sender_role: str,
    recipient_user_id: str,
    kind: str,
    title: str,
    message: str,
    channel: str = "in_app",
    warranty_id: Optional[str] = None,
    brand: Optional[str] = None,
    model_code: Optional[str] = None,
    product_type: Optional[str] = None,
    region: Optional[str] = None,
    send_if_ineligible: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    kind = (kind or "").strip().lower()
    if kind not in ALLOWED_KINDS:
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind or "unknown",
            channel=channel,
            title=title,
            message=message,
            decision="blocked",
            blocked_reason="invalid_kind",
            trace_json={"metadata": metadata or {}},
        )
        return {"ok": False, "decision": "blocked", "blocked_reason": "invalid_kind", "trace_id": row.id}

    if kind == "marketing" and not _ALLOW_MARKETING:
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind,
            channel=channel,
            title=title,
            message=message,
            decision="blocked",
            blocked_reason="marketing_disabled",
            trace_json={"metadata": metadata or {}},
        )
        return {"ok": False, "decision": "blocked", "blocked_reason": "marketing_disabled", "trace_id": row.id}

    user = db.query(UserDB).filter_by(username=recipient_user_id).first()
    if not user:
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind,
            channel=channel,
            title=title,
            message=message,
            decision="blocked",
            blocked_reason="recipient_not_found",
            trace_json={"metadata": metadata or {}},
        )
        return {"ok": False, "decision": "blocked", "blocked_reason": "recipient_not_found", "trace_id": row.id}

    if os.getenv("REQUIRE_USER_CONSENT", "false").lower() == "true" and not bool(getattr(user, "consent_analytics", 0)):
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind,
            channel=channel,
            title=title,
            message=message,
            decision="blocked",
            blocked_reason="consent_required",
            trace_json={"metadata": metadata or {}},
        )
        return {"ok": False, "decision": "blocked", "blocked_reason": "consent_required", "trace_id": row.id}

    sent_count = _recent_sent_count(db, recipient_user_id=recipient_user_id)
    if sent_count >= max(1, _MAX_PER_WINDOW):
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind,
            channel=channel,
            title=title,
            message=message,
            decision="blocked",
            blocked_reason="rate_limited_6_months",
            trace_json={"sent_in_window": sent_count, "metadata": metadata or {}},
        )
        return {"ok": False, "decision": "blocked", "blocked_reason": "rate_limited_6_months", "trace_id": row.id}

    ctx = _resolve_warranty_context(db, warranty_id, brand, model_code, product_type, region)
    match = _collect_importance_signals(
        db,
        recipient_user_id=recipient_user_id,
        warranty_id=warranty_id,
        kind=kind,
        brand=ctx.get("brand"),
        model_code=ctx.get("model_code"),
        region=ctx.get("region"),
    )
    if _REQUIRE_IMPORTANCE and not match["eligible"] and not send_if_ineligible:
        row = _record_trace(
            db,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            recipient_user_id=recipient_user_id,
            warranty_id=warranty_id,
            kind=kind,
            channel=channel,
            title=title,
            message=message,
            brand=ctx.get("brand"),
            model_code=ctx.get("model_code"),
            product_type=ctx.get("product_type"),
            region=ctx.get("region"),
            decision="blocked",
            blocked_reason="not_important_or_not_matched",
            trace_json={"match": match, "metadata": metadata or {}},
        )
        return {
            "ok": False,
            "decision": "blocked",
            "blocked_reason": "not_important_or_not_matched",
            "trace_id": row.id,
            "match": match,
        }

    notification = create_notification(
        user_id=recipient_user_id,
        warranty_id=warranty_id or "",
        type=f"oem_{kind}",
        title=title,
        message=message,
        severity="info",
        db=db,
        audience="user",
        brand=ctx.get("brand"),
        region=ctx.get("region"),
    )
    row = _record_trace(
        db,
        sender_user_id=sender_user_id,
        sender_role=sender_role,
        recipient_user_id=recipient_user_id,
        warranty_id=warranty_id,
        kind=kind,
        channel=channel,
        title=title,
        message=message,
        brand=ctx.get("brand"),
        model_code=ctx.get("model_code"),
        product_type=ctx.get("product_type"),
        region=ctx.get("region"),
        reason_code=",".join(match.get("reason_codes") or []) or None,
        reason_text=match.get("reason_text"),
        decision="sent",
        trace_json={"match": match, "metadata": metadata or {}, "notification": notification or {}},
    )
    return {"ok": True, "decision": "sent", "trace_id": row.id, "match": match, "notification": notification}


def list_traces(
    db: Session,
    *,
    recipient_user_id: Optional[str] = None,
    warranty_id: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    q = db.query(OemCommunicationTraceDB).order_by(OemCommunicationTraceDB.created_at.desc())
    if recipient_user_id:
        q = q.filter(OemCommunicationTraceDB.recipient_user_id == recipient_user_id)
    if warranty_id:
        q = q.filter(OemCommunicationTraceDB.warranty_id == warranty_id)
    if decision:
        q = q.filter(OemCommunicationTraceDB.decision == decision)
    rows = q.limit(max(1, min(int(limit or 100), 500))).all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "sender_user_id": r.sender_user_id,
                "sender_role": r.sender_role,
                "recipient_user_id": r.recipient_user_id,
                "warranty_id": r.warranty_id,
                "kind": r.kind,
                "channel": r.channel,
                "title": r.title,
                "message": r.message,
                "brand": r.brand,
                "model_code": r.model_code,
                "product_type": r.product_type,
                "region": r.region,
                "reason_code": r.reason_code,
                "reason_text": r.reason_text,
                "decision": r.decision,
                "blocked_reason": r.blocked_reason,
                "trace_json": r.trace_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out
