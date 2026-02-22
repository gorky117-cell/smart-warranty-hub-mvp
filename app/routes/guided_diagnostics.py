from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, require_user
from ..services import guided_diagnostics as gd


router = APIRouter()


class StartRequest(BaseModel):
    user_id: Optional[str] = None
    warranty_id: str
    city: Optional[str] = None


class AnswerRequest(BaseModel):
    question_id: str
    answer_value: str


class EvidenceRequest(BaseModel):
    evidence_type: str = "text"
    uri: Optional[str] = None
    notes: Optional[str] = None


class FinalizeRequest(BaseModel):
    create_service_ticket: bool = True


@router.post("/start")
def start(payload: StartRequest, db: Session = Depends(get_db), current=Depends(require_user)):
    uid = payload.user_id or current.username
    try:
        s = gd.create_session(db, user_id=uid, warranty_id=payload.warranty_id, city=payload.city)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "session_id": s.id, "status": s.status}


@router.get("/{session_id}")
def session_state(session_id: str, db: Session = Depends(get_db), current=Depends(require_user)):
    s = gd.get_session(db, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {
        "ok": True,
        "session": {
            "id": s.id,
            "user_id": s.user_id,
            "warranty_id": s.warranty_id,
            "product_name": s.product_name,
            "brand": s.brand,
            "model_code": s.model_code,
            "region": s.region,
            "city": s.city,
            "status": s.status,
            "current_step": s.current_step,
            "summary": s.summary_json,
        },
    }


@router.get("/{session_id}/next")
def next_q(session_id: str, db: Session = Depends(get_db), current=Depends(require_user)):
    try:
        out = gd.next_question(db, session_id=session_id)
        return {"ok": True, **out}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{session_id}/answer")
def answer(session_id: str, payload: AnswerRequest, db: Session = Depends(get_db), current=Depends(require_user)):
    try:
        rec = gd.answer_question(
            db,
            session_id=session_id,
            question_id=payload.question_id,
            answer_value=payload.answer_value,
        )
        return {"ok": True, "answer_id": rec.id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{session_id}/evidence")
def add_evidence(session_id: str, payload: EvidenceRequest, db: Session = Depends(get_db), current=Depends(require_user)):
    try:
        rec = gd.add_evidence(
            db,
            session_id=session_id,
            evidence_type=payload.evidence_type,
            uri=payload.uri,
            notes=payload.notes,
        )
        return {"ok": True, "evidence_id": rec.id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{session_id}/finalize")
def finalize(session_id: str, payload: FinalizeRequest, db: Session = Depends(get_db), current=Depends(require_user)):
    try:
        out = gd.finalize(
            db,
            session_id=session_id,
            create_service_ticket=payload.create_service_ticket,
        )
        return {"ok": True, **out}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
