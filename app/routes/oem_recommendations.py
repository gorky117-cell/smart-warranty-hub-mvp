from fastapi import APIRouter, Body
from typing import Dict
from app.services import oem_recommendation_service

router = APIRouter()


def _fallback_preview(ctx: Dict):
    return {
        "risk_distribution": {"low": 5, "medium": 3, "high": 2},
        "top_risks": ["Potential wear in humid regions", "Voltage fluctuation reports"],
        "likely_user_needs": ["Maintenance guidance", "Power protection"],
        "suggested_oem_actions": ["Push care tips", "Offer discounted check-up"],
        "suggested_products": ["Surge protector", "Cleaning kit", "Extended warranty"],
        "recommendation_message": f"Focus on preventive care for {ctx.get('brand') or 'your brand'}.",
    }


@router.get("/preview")
def preview(product_type: str | None = None, brand: str | None = None, model_code: str | None = None, region: str | None = None):
    try:
        ctx = {"product_type": product_type, "brand": brand, "model": model_code, "region": region}
        return {"ok": True, "preview": _fallback_preview(ctx)}
    except Exception:
        return {"ok": False, "preview": {}, "error": "server_error"}


@router.post("/generate")
def generate(payload: Dict = Body(None)):
    try:
        payload = payload or {}
        ctx = {
            "product_type": payload.get("product_type"),
            "brand": payload.get("brand"),
            "model": payload.get("model") or payload.get("model_code"),
            "region": payload.get("region"),
        }
        return {"ok": True, "recommendations": [_fallback_preview(ctx)]}
    except Exception:
        return {"ok": False, "recommendations": [], "error": "server_error"}


@router.post("/publish")
def publish(payload: Dict = Body(...)):
    try:
        rec = payload.get("recommendation") or payload
        saved = oem_recommendation_service.publish_recommendation(rec)
        return {"ok": True, "id": saved.get("id")}
    except Exception:
        return {"ok": False, "id": None, "error": "server_error"}


@router.get("/active")
def active(product_type: str | None = None, brand: str | None = None, model_code: str | None = None, region: str | None = None):
    try:
        items = oem_recommendation_service.list_active({"product_type": product_type, "brand": brand, "model": model_code, "region": region})
        return {"ok": True, "items": items, "count": len(items)}
    except Exception:
        return {"ok": False, "items": [], "count": 0, "error": "server_error"}


@router.post("/disable")
def disable(payload: Dict = Body(...)):
    try:
        rec_id = payload.get("id") or payload.get("rec_id") or payload.get("recommendation_id")
        if not rec_id:
            return {"ok": False, "detail": "missing_id"}
        done = oem_recommendation_service.disable_rec(str(rec_id))
        return {"ok": True, "disabled": done}
    except Exception:
        return {"ok": False, "disabled": False, "error": "server_error"}
