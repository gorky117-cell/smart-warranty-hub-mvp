from fastapi import APIRouter, Body
from typing import Dict
import os
from app.services import ollama_questions, oem_question_service

router = APIRouter()


@router.get("/llm-status")
def llm_status():
    try:
        st = ollama_questions.status()
        return {"ok": True, "provider": "ollama", "model": st.get("model"), "details": st}
    except Exception:
        return {"ok": False, "provider": "ollama", "available": False, "error": "server_error"}


@router.get("/active")
def list_active(product_type: str | None = None, brand: str | None = None, model_code: str | None = None, region: str | None = None):
    try:
        items = oem_question_service.list_active(
            {"brand": brand, "model_code": model_code, "product_type": product_type, "region": region}
        )
        return {"ok": True, "items": items, "count": len(items)}
    except Exception:
        return {"ok": False, "items": [], "count": 0, "error": "server_error"}


@router.post("/generate")
def generate_questions(payload: Dict = Body(None)):
    try:
        payload = payload or {}
        ctx = {
            "brand": payload.get("brand"),
            "model_code": payload.get("model_code") or payload.get("model"),
            "product_type": payload.get("product_type"),
            "region": payload.get("region"),
        }
        n = payload.get("count") or payload.get("max_questions") or 5
        qs = ollama_questions.generate_questions(ctx, n=n)
        return {"ok": True, "generated": qs}
    except Exception:
        return {"ok": False, "generated": [], "error": "server_error"}


@router.post("/publish")
def publish_question(payload: Dict = Body(...)):
    try:
        target = {
            "brand": payload.get("brand"),
            "model_code": payload.get("model_code") or payload.get("model"),
            "product_type": payload.get("product_type"),
            "region": payload.get("region"),
        }
        q = payload.get("question") or payload
        oem_question_service.publish_question(target, q)
        return {"ok": True}
    except Exception:
        return {"ok": False, "error": "server_error"}


@router.post("/disable")
def disable_question(payload: Dict = Body(...)):
    try:
        qid = payload.get("question_id") or payload.get("id")
        if not qid:
            return {"ok": False, "detail": "missing_question_id"}
        done = oem_question_service.disable_question(str(qid))
        return {"ok": True, "disabled": done}
    except Exception:
        return {"ok": False, "disabled": False, "error": "server_error"}
