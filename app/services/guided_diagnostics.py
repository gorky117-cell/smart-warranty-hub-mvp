from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..db_models import (
    GuidedDiagnosticAnswerDB,
    GuidedDiagnosticEvidenceDB,
    GuidedDiagnosticSessionDB,
    WarrantyDB,
)
from ..services.service import create_ticket
from ..storage import generate_id


SERVICE_CENTERS_FILE = Path(__file__).resolve().parents[2] / "data" / "service_centers.json"


def _now() -> datetime:
    return datetime.utcnow()


def _load_centers() -> List[Dict]:
    if not SERVICE_CENTERS_FILE.exists():
        return []
    try:
        data = json.loads(SERVICE_CENTERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def _question_flow(product_name: Optional[str]) -> List[Dict]:
    p = (product_name or "").lower()
    extra = []
    if "ac" in p or "air" in p:
        extra = [
            {"id": "q_temp", "text": "Is cooling weak or uneven?", "type": "choice", "options": ["Yes", "No", "Not sure"]},
        ]
    elif "fridge" in p or "refrigerator" in p:
        extra = [
            {"id": "q_noise", "text": "Do you hear unusual noise from the back side?", "type": "choice", "options": ["Yes", "No"]},
        ]
    elif "phone" in p or "mobile" in p:
        extra = [
            {"id": "q_battery", "text": "Battery draining unusually fast?", "type": "choice", "options": ["Yes", "No", "Sometimes"]},
        ]

    base = [
        {"id": "q_issue", "text": "What is the main problem you see?", "type": "choice", "options": ["Not turning on", "Performance issue", "Heating", "Noise", "Connectivity", "Other"]},
        {"id": "q_since", "text": "Since when is this happening?", "type": "choice", "options": ["Today", "2-3 days", "1 week", "More than 1 week"]},
        {"id": "q_severity", "text": "How bad is it right now?", "type": "choice", "options": ["Mild", "Moderate", "Severe"]},
        {"id": "q_restart", "text": "Did restart/power cycle help?", "type": "choice", "options": ["Yes", "No", "Not tried"]},
        {"id": "q_error", "text": "Any error code/message (if visible)?", "type": "text", "options": []},
        {"id": "q_safety", "text": "Any smoke, burning smell, sparking, or leak?", "type": "choice", "options": ["Yes", "No"]},
    ]
    return base[:3] + extra + base[3:]


def _probable_issue(answers: Dict[str, str]) -> Tuple[str, float, str]:
    issue = (answers.get("q_issue", "") or "").lower()
    severity = (answers.get("q_severity", "") or "").lower()
    safety = (answers.get("q_safety", "") or "").lower()
    restart = (answers.get("q_restart", "") or "").lower()
    code = (answers.get("q_error", "") or "").strip()

    confidence = 0.45
    priority = "normal"
    probable = "General diagnostic needed"

    if "not turning on" in issue:
        probable = "Power path issue (adapter/board/fuse)"
        confidence = 0.76
    elif "heating" in issue:
        probable = "Thermal stress or ventilation issue"
        confidence = 0.71
    elif "noise" in issue:
        probable = "Mechanical wear or fan/compressor imbalance"
        confidence = 0.69
    elif "connectivity" in issue:
        probable = "Network module or router compatibility issue"
        confidence = 0.67
    elif "performance" in issue:
        probable = "Performance degradation; firmware/app check required"
        confidence = 0.63

    if code:
        confidence = min(0.92, confidence + 0.07)
    if restart == "yes":
        confidence = max(0.4, confidence - 0.08)
    if severity == "severe":
        priority = "high"
    if safety == "yes":
        probable = "Safety-critical condition detected"
        confidence = max(confidence, 0.88)
        priority = "critical"
    return probable, round(confidence, 2), priority


def _service_centers(brand: Optional[str], region: Optional[str], city: Optional[str], limit: int = 3) -> List[Dict]:
    rows = _load_centers()
    b = (brand or "").strip().lower()
    r = (region or "").strip().lower()
    c = (city or "").strip().lower()
    scored: List[Tuple[int, Dict]] = []
    for row in rows:
        score = 0
        rb = (row.get("brand") or "").strip().lower()
        rr = (row.get("region") or "").strip().lower()
        rc = (row.get("city") or "").strip().lower()
        if b and rb == b:
            score += 4
        if r and rr == r:
            score += 3
        if c and rc == c:
            score += 5
        if not b and not r and not c:
            score += 1
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[: max(1, limit)]]


def create_session(db: Session, *, user_id: str, warranty_id: str, city: Optional[str] = None) -> GuidedDiagnosticSessionDB:
    w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
    if not w:
        raise ValueError("warranty_not_found")
    row = GuidedDiagnosticSessionDB(
        id=generate_id("gds"),
        user_id=user_id,
        warranty_id=warranty_id,
        product_name=w.product_name,
        brand=w.brand,
        model_code=w.model_code,
        region=w.region_code,
        city=city,
        status="active",
        current_step=0,
        context_json={},
        summary_json=None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: str) -> Optional[GuidedDiagnosticSessionDB]:
    return db.query(GuidedDiagnosticSessionDB).filter_by(id=session_id).first()


def next_question(db: Session, *, session_id: str) -> Dict:
    s = get_session(db, session_id)
    if not s:
        raise ValueError("session_not_found")
    flow = _question_flow(s.product_name)
    answered = db.query(GuidedDiagnosticAnswerDB).filter_by(session_id=session_id).count()
    if answered >= len(flow):
        return {"done": True, "question": None}
    q = flow[answered]
    s.current_step = answered
    s.updated_at = _now()
    db.add(s)
    db.commit()
    return {
        "done": False,
        "question": {
            "id": q["id"],
            "text": q["text"],
            "type": q["type"],
            "options": q.get("options", []),
            "friendly_tip": "Take your time. Even short answers are okay.",
        },
        "step": answered + 1,
        "total_steps": len(flow),
    }


def answer_question(db: Session, *, session_id: str, question_id: str, answer_value: str) -> GuidedDiagnosticAnswerDB:
    s = get_session(db, session_id)
    if not s:
        raise ValueError("session_not_found")
    flow = _question_flow(s.product_name)
    qmap = {q["id"]: q for q in flow}
    q = qmap.get(question_id)
    if not q:
        raise ValueError("invalid_question_id")
    rec = GuidedDiagnosticAnswerDB(
        session_id=session_id,
        question_id=question_id,
        question_text=q.get("text"),
        answer_value=(answer_value or "").strip()[:2000],
        created_at=_now(),
    )
    db.add(rec)
    s.updated_at = _now()
    db.add(s)
    db.commit()
    db.refresh(rec)
    return rec


def add_evidence(db: Session, *, session_id: str, evidence_type: str, uri: Optional[str], notes: Optional[str]) -> GuidedDiagnosticEvidenceDB:
    s = get_session(db, session_id)
    if not s:
        raise ValueError("session_not_found")
    et = (evidence_type or "").strip().lower() or "text"
    if et not in ("photo", "video", "log", "text"):
        et = "text"
    rec = GuidedDiagnosticEvidenceDB(
        session_id=session_id,
        evidence_type=et,
        uri=(uri or "").strip()[:2000] or None,
        notes=(notes or "").strip()[:4000] or None,
        created_at=_now(),
    )
    db.add(rec)
    s.updated_at = _now()
    db.add(s)
    db.commit()
    db.refresh(rec)
    return rec


def finalize(db: Session, *, session_id: str, create_service_ticket: bool = True) -> Dict:
    s = get_session(db, session_id)
    if not s:
        raise ValueError("session_not_found")
    ans = db.query(GuidedDiagnosticAnswerDB).filter_by(session_id=session_id).all()
    ev = db.query(GuidedDiagnosticEvidenceDB).filter_by(session_id=session_id).all()
    amap: Dict[str, str] = {a.question_id: a.answer_value for a in ans}
    probable, confidence, priority = _probable_issue(amap)

    centers = _service_centers(s.brand, s.region, s.city, limit=3)
    next_steps = [
        "Keep invoice and product serial number ready.",
        "Share 1 clear photo/video of the issue if possible.",
        "Visit or call nearest authorized service center for diagnostic confirmation.",
    ]
    if priority == "critical":
        next_steps = [
            "Stop using the product immediately for safety.",
            "Disconnect power and avoid further operation.",
            "Contact authorized service center urgently.",
        ]

    ticket = None
    if create_service_ticket:
        symptom = (amap.get("q_issue") or "other").lower().replace(" ", "_")
        evidence = [x.uri for x in ev if x.uri]
        try:
            t = create_ticket(s.user_id, s.warranty_id, symptom=symptom, evidence=evidence)
            ticket = {
                "id": t.id,
                "status": t.status,
                "recommended_parts": t.recommended_parts,
            }
            s.status = "escalated"
        except Exception:
            ticket = None
    if s.status != "escalated":
        s.status = "completed"

    out = {
        "probable_issue": probable,
        "confidence": confidence,
        "priority": priority,
        "human_summary": (
            f"We checked your answers and this looks like: {probable}. "
            f"Confidence: {int(confidence*100)}%. "
            "Please follow the next steps below."
        ),
        "next_steps": next_steps,
        "nearest_service_centers": centers,
        "evidence_count": len(ev),
        "service_ticket": ticket,
    }
    s.summary_json = out
    s.updated_at = _now()
    db.add(s)
    db.commit()
    return out
