import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, Form, Response, status, Body, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .models import ArtifactType, BehaviourEvent
from .services.canonical import canonicalize_artifact
from .services.ingestion import ingest_artifact
from .services.llm import generate_text
from .services.nudge import generate_nudges
from .services.predictive import compute_predictive_score, predictive_model, build_feature_vector, score_warranty
from .services.oem import fetch_oem_page
from .services.risk import compute_risk
from .services.service import create_ticket
from .storage import store, generate_id
from .services.connection_registry import registry, Connector
from .models import TelemetryEvent
from .services.review import create_review, approve_review, reject_review
from .services import policy
from .services.oem_parsers import parse_oem_text
from .services.audit import log_action
from .services import behaviour as behaviour_service
from .services import behaviour_questions
from .services import peer_review as peer_review_service
from .services import search_log as search_log_service
from .services import recommendation as recommendation_service
from .services import ev_battery as ev_battery_service
from .services import notifications as notification_service
from .services import product_recommendations as prod_recs_service
from .services import oem_question_service
from .services import ollama_questions
from .services import oem_recommendation_service
from .services import invoice_pipeline
from .services import summary_engine
from .services.notifications import run_initial_analysis_and_notifications
from .routes import oem_questions, oem_recommendations
logger = logging.getLogger(__name__)
from .deps import (
    rbac_dependency,
    require_user,
    require_admin,
    get_db,
    get_current_user_optional,
    create_access_token,
    verify_password,
    hash_password,
    init_db,
    ACCESS_TOKEN_EXPIRE_HOURS,
    require_oem_or_admin,
)
from .services.exporter import export_warranty_txt, export_warranty_html, export_warranty_pdf
from .services.scheduler import start_scheduler
from .services import ocr as ocr_service
from .services import llm as llm_service
from .services import predictive as predictive_service
from .db import SessionLocal
from .db_models import (
    UserDB,
    BehaviourProfile,
    BehaviourQuestion,
    BehaviourAnswer,
    NudgeEvents,
    PeerReviewSignals,
    SymptomSearch,
    WarrantyDB,
    OEMFetchDB,
    RecommendationRule,
    RecommendationEvent,
    EVTelemetryDB,
)


class ArtifactRequest(BaseModel):
    type: ArtifactType
    content: str | None = None
    file_path: str | None = None
    use_ocr: bool = False
    source: str | None = None


class CanonicalRequest(BaseModel):
    artifact_id: str
    overrides: dict[str, str] | None = None


class BehaviourEventRequest(BaseModel):
    user_id: str
    warranty_id: str
    event_type: str
    details: dict | None = None


class RiskRequest(BaseModel):
    user_id: str
    warranty_id: str


class ServiceTicketRequest(BaseModel):
    user_id: str
    warranty_id: str
    symptom: str
    evidence: list[str] | None = None


class LLMRequest(BaseModel):
    prompt: str
    model: str | None = None


class ConnectorRequest(BaseModel):
    name: str
    kind: str
    endpoint: str
    auth_token: str | None = None
    metadata: dict | None = None


class TelemetryRequest(BaseModel):
    user_id: str
    warranty_id: str
    model_code: str | None = None
    region: str | None = None
    timezone: str | None = None
    event_type: str
    payload: dict | None = None


class PredictiveRequest(BaseModel):
    user_id: str
    warranty_id: str
    model_code: str | None = None
    region: str | None = None
    timezone: str | None = None


class OemFetchRequest(BaseModel):
    brand: str
    model: str
    region: str | None = None
    url: str
    immediate: bool = False  # if false, create review; if true, fetch now


class SummaryRequest(BaseModel):
    warranty_id: str
    max_tokens: int | None = 256


class ProcessWarrantyRequest(BaseModel):
    artifact_id: str | None = None
    source_path: str | None = None


class SignupRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "user"  # user | oem | admin (admin only via existing admin)


class LoginRequest(BaseModel):
    username: str
    password: str


class BehaviourAnswerRequest(BaseModel):
    user_id: str
    question_id: str | int
    answer_value: str
    product_type: str | None = None
    warranty_id: str | None = None


class NudgeEventRequest(BaseModel):
    user_id: str
    warranty_id: str | None = None
    nudge_type: str
    outcome: str | None = None  # acted | ignored | dismissed
    variant: str | None = None


class PeerReviewUpdate(BaseModel):
    product_type: str | None = None
    brand: str | None = None
    model: str | None = None
    symptom_keyword: str | None = None
    severity_hint: str | None = None
    source: str | None = None
    avg_rating: float | None = None
    review_sentiment: float | None = None
    warranty_id: str | None = None
    failure_keywords: List[str] | None = None


class SymptomSearchLogRequest(BaseModel):
    user_id: str
    product_type: str | None = None
    brand: str | None = None
    model: str | None = None
    query_text: str
    region: str | None = None
    matched_component: str | None = None
    warranty_id: str | None = None


class RecommendationOut(BaseModel):
    segment: str
    title: str
    message: str
    priority: int


class RecommendationsResponse(BaseModel):
    recommendations: List[RecommendationOut]
    product_recommendations: Optional[List[dict]] = None


class EVBatteryRequest(BaseModel):
    warranty_id: str | None = None
    product_type: int = 3  # 3 = EV car, 4 = EV 2W
    age_months: float = 0
    daily_km: float = 0
    fast_charge_sessions: int = 0
    deep_discharge_events: int = 0
    max_temp_seen: float = 25
    behaviour_score: float = 0.5
    care_score: float = 0.5
    responsiveness_score: float = 0.5
    region_climate_band: int = 0


app = FastAPI(
    title="Smart Warranty Hub MVP",
    description="Warranty ingestion, canonicalisation, risk, nudges, predictive care, OEM fetch, and service orchestration.",
    version="0.2.0",
)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# OEM routers (and /api aliases)
app.include_router(oem_questions.router, prefix="/oem/questions", tags=["OEM Questions"])
app.include_router(oem_questions.router, prefix="/api/oem/questions", tags=["OEM Questions"])
app.include_router(oem_recommendations.router, prefix="/oem/recommendations", tags=["OEM Recommendations"])
app.include_router(oem_recommendations.router, prefix="/api/oem/recommendations", tags=["OEM Recommendations"])


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

# Router includes for OEM questions/recommendations
app.include_router(oem_questions.router, prefix="/oem/questions", tags=["OEM Questions"])
app.include_router(oem_questions.router, prefix="/api/oem/questions", tags=["OEM Questions"])
app.include_router(oem_recommendations.router, prefix="/oem/recommendations", tags=["OEM Recommendations"])
app.include_router(oem_recommendations.router, prefix="/api/oem/recommendations", tags=["OEM Recommendations"])

# Router includes
app.include_router(oem_questions.router, prefix="/oem/questions", tags=["OEM Questions"])
app.include_router(oem_questions.router, prefix="/api/oem/questions", tags=["OEM Questions"])
app.include_router(oem_recommendations.router, prefix="/oem/recommendations", tags=["OEM Recommendations"])
app.include_router(oem_recommendations.router, prefix="/api/oem/recommendations", tags=["OEM Recommendations"])

dist_path = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dist_path), html=True), name="dashboard")


@app.get("/dashboard-dev", dependencies=[Depends(require_user)])
def dashboard_dev():
    dev_url = os.getenv("VITE_DEV_URL")
    if not dev_url:
        raise HTTPException(status_code=404, detail="Set VITE_DEV_URL to use the dev dashboard.")
    return RedirectResponse(dev_url)


@app.on_event("startup")
async def startup_event():
    import os
    init_db()
    interval = int(os.getenv("OEM_REFRESH_MINUTES", "120"))
    start_scheduler(interval)


@app.middleware("http")
async def cache_dashboard(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/dashboard"):
        # Cache static assets aggressively; index less so
        if "." in path:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.get("/")
def health():
    return {"status": "ok", "warranties": len(store.warranties), "connectors": len(registry.list())}


@app.get("/health/ocr")
def health_ocr():
    ok, detail = ocr_service.health()
    return {"ok": ok, "detail": detail}


@app.get("/health/llm")
def health_llm():
    ok, detail, model = summary_engine.health()
    return {"ok": ok, "detail": detail, "model": model}


@app.get("/health/predictive")
def health_predictive():
    ok, detail = predictive_service.health()
    return {"ok": ok, "detail": detail}


@app.get("/health/full")
def health_full():
    ocr_ok, ocr_detail = ocr_service.health()
    llm_ok, llm_detail, llm_model = summary_engine.health()
    pred_ok, pred_detail = predictive_service.health()
    status = "ok" if (ocr_ok and llm_ok and pred_ok) else "degraded"
    return {
        "status": status,
        "checks": {
            "ocr": {"ok": ocr_ok, "detail": ocr_detail},
            "llm": {"ok": llm_ok, "detail": llm_detail, "model": llm_model},
            "predictive": {"ok": pred_ok, "detail": pred_detail},
        },
    }


@app.get("/behaviour/next-question", dependencies=[Depends(require_user)])
def behaviour_next_question(
    user_id: str,
    warranty_id: str | None = None,
    product_type: str | None = None,
    brand: str | None = None,
    model_code: str | None = None,
):
    try:
        logger.info("BEHAVIOUR_NEXT_QUESTION_V2 HIT", extra={"user_id": user_id, "warranty_id": warranty_id})
        if not user_id or not warranty_id:
            return {
                "ok": False,
                "question": None,
                "done": True,
                "reason": "missing_params",
                "question_id": None,
                "text": None,
                "answer_type": None,
                "options": [],
            }
        # Try OEM question first
        warranty_ctx = {"brand": brand, "model_code": model_code, "product_type": product_type, "region": None}
        oem_q = oem_question_service.get_next_oem_question(user_id, warranty_id, warranty_ctx)
        if oem_q:
            return {
                "ok": True,
                "question": oem_q,
                "done": False,
                "reason": "oem_question_available",
                "question_id": oem_q.get("id"),
                "text": oem_q.get("text"),
                "answer_type": oem_q.get("answer_type"),
                "options": oem_q.get("options") or [],
                "source": "oem",
            }
        q, done = behaviour_questions.get_next_question(user_id=user_id, warranty_id=warranty_id or "")
        if not q:
            return {
                "ok": True,
                "question": None,
                "done": True,
                "reason": "no_question_available",
            }
        return {
            "ok": True,
            "done": done,
            "reason": "question_available",
            "question": q,
            # backward-compatibility fields for existing JS
            "question_id": q.get("id"),
            "text": q.get("text"),
            "answer_type": q.get("answer_type"),
            "options": q.get("options") or [],
        }
    except Exception as e:
        logger.exception("behaviour next-question failed", exc_info=e)
        return {
            "ok": False,
            "question": None,
            "done": True,
            "reason": "server_error",
            "question_id": None,
            "text": None,
            "answer_type": None,
            "options": [],
        }


@app.post("/behaviour/answer", dependencies=[Depends(require_user)])
def behaviour_answer(payload: BehaviourAnswerRequest):
    try:
        if not payload.user_id or not payload.warranty_id or payload.question_id is None or payload.answer_value is None:
            return {"ok": False, "detail": "missing_params"}
        # OEM answer if it looks like OEM question id prefix
        if str(payload.question_id).startswith("oemq_"):
            try:
                oem_question_service.record_oem_answer(
                    user_id=payload.user_id,
                    warranty_id=payload.warranty_id,
                    question_id=str(payload.question_id),
                    answer=str(payload.answer_value),
                    meta={},
                )
            except Exception as e:
                logger.warning("record_oem_answer failed (ignored)", exc_info=e)
        else:
            behaviour_questions.record_answer(
                user_id=payload.user_id,
                warranty_id=payload.warranty_id,
                question_id=str(payload.question_id),
                answer=str(payload.answer_value),
            )
            # best-effort call to existing behaviour_service (does not fail API)
            try:
                behaviour_service.record_answer(
                    payload.user_id,
                    payload.product_type,
                    payload.warranty_id,
                    payload.question_id,
                    payload.answer_value,
                )
            except Exception as e:
                logger.warning("behaviour_service.record_answer failed (ignored)", exc_info=e)
        return {"ok": True}
    except Exception as e:
        logger.exception("behaviour answer failed", exc_info=e)
        return {"ok": False, "detail": "server_error"}


def _llm_status_payload():
    st = ollama_questions.status()
    return {
        "ok": True,
        "enabled": bool(st.get("enabled")),
        "available": bool(st.get("reachable")),
        "provider": "ollama",
        "base_url": st.get("base_url"),
        "model": st.get("model"),
        "reachable": bool(st.get("reachable")),
        "error": st.get("error"),
        "detail": st.get("error") or ("reachable" if st.get("reachable") else "unreachable"),
    }


@app.get("/llm/status", dependencies=[Depends(require_user)])
def llm_status():
    try:
        return _llm_status_payload()
    except Exception as e:
        logger.warning("llm status failed", exc_info=e)
        return {"ok": False, "enabled": False, "available": False, "provider": "ollama", "error": "server_error", "detail": str(e)}


@app.get("/api/llm/status")
def llm_status_alias():
    return llm_status()


@app.get("/oem/questions/llm-status", dependencies=[Depends(require_oem_or_admin)])
def oem_llm_status():
    try:
        return _llm_status_payload()
    except Exception as e:
        logger.warning("oem llm status failed", exc_info=e)
        return {"ok": False, "enabled": False, "available": False, "provider": "ollama", "error": "server_error", "detail": str(e)}


@app.post("/oem/questions/generate", dependencies=[Depends(require_oem_or_admin)])
def oem_questions_generate(payload: Dict = Body(None)):
    try:
        payload = payload or {}
        ctx = {
            "brand": payload.get("brand"),
            "model_code": payload.get("model_code") or payload.get("model"),
            "product_type": payload.get("product_type"),
            "region": payload.get("region"),
        }
        n = payload.get("max_questions", 5)
        qs = ollama_questions.generate_questions(ctx, n=n)
        return {"ok": True, "questions": qs, "source": "ollama" if os.environ.get("ENABLE_LLM_QUESTIONS", "0") == "1" else "fallback"}
    except Exception as e:
        logger.exception("oem generate failed", exc_info=e)
        return {"ok": False, "questions": [], "error": "server_error"}


@app.post("/api/oem/questions/generate")
def oem_questions_generate_alias(payload: Dict = Body(None), current=Depends(require_oem_or_admin)):
    return oem_questions_generate(payload)


@app.post("/oem/questions/publish", dependencies=[Depends(require_oem_or_admin)])
def oem_questions_publish(payload: Dict = Body(...)):
    try:
        target = {
            "brand": payload.get("brand"),
            "model_code": payload.get("model_code") or payload.get("model"),
            "product_type": payload.get("product_type"),
            "region": payload.get("region"),
        }
        q = payload.get("question") or {}
        rec = oem_question_service.publish_question(target, q)
        return {"ok": True, "question_id": rec.get("id")}
    except Exception as e:
        logger.exception("oem publish failed", exc_info=e)
        return {"ok": False, "question_id": None, "error": "server_error"}


@app.post("/api/oem/questions/publish")
def oem_questions_publish_alias(payload: Dict = Body(...), current=Depends(require_oem_or_admin)):
    return oem_questions_publish(payload)


@app.get("/oem/questions/active", dependencies=[Depends(require_oem_or_admin)])
def oem_questions_active(brand: str | None = None, model_code: str | None = None, product_type: str | None = None, region: str | None = None, model: str | None = None):
    try:
        items = oem_question_service.list_active({"brand": brand, "model_code": model_code or model, "product_type": product_type, "region": region})
        return {"ok": True, "items": items}
    except Exception as e:
        logger.exception("oem active failed", exc_info=e)
        return {"ok": False, "items": [], "error": "server_error"}


@app.get("/api/oem/questions/active")
def oem_questions_active_alias(brand: str | None = None, model_code: str | None = None, product_type: str | None = None, region: str | None = None, current=Depends(require_oem_or_admin)):
    return oem_questions_active(brand=brand, model_code=model_code, product_type=product_type, region=region)


@app.post("/oem/questions/disable", dependencies=[Depends(require_oem_or_admin)])
def oem_questions_disable(payload: Dict = Body(...)):
    try:
        qid = payload.get("question_id")
        if not qid:
            return {"ok": False, "detail": "missing_question_id"}
        done = oem_question_service.disable_question(qid)
        return {"ok": True, "disabled": done}
    except Exception as e:
        logger.exception("oem disable failed", exc_info=e)
        return {"ok": False, "disabled": False, "error": "server_error"}


@app.post("/api/oem/questions/disable")
def oem_questions_disable_alias(payload: Dict = Body(...), current=Depends(require_oem_or_admin)):
    return oem_questions_disable(payload)


@app.post("/oem/recommendations/generate", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_generate(payload: Dict = Body(None)):
    try:
        payload = payload or {}
        brand = payload.get("brand")
        model = payload.get("model")
        product_type = payload.get("product_type")
        region = payload.get("region")
        count = int(payload.get("count", 3))
        # simple heuristic recs
        base_recs = [
            {"title": "Voltage protection", "message": "Offer a surge protector for regions with fluctuations.", "cta_label": "View surge protectors"},
            {"title": "Maintenance kit", "message": "Recommend a cleaning/maintenance kit for heavy usage.", "cta_label": "View kit"},
            {"title": "Extended coverage", "message": "Suggest extended warranty before expiry.", "cta_label": "Explore coverage"},
        ]
        out = []
        for i in range(min(count, len(base_recs))):
            rec = base_recs[i].copy()
            rec.update({"brand": brand, "model": model, "product_type": product_type, "region": region, "source": "oem_manual"})
            out.append(rec)
        return {"ok": True, "recommendations": out}
    except Exception as e:
        logger.exception("oem recommendations generate failed", exc_info=e)
        return {"ok": False, "recommendations": [], "error": "server_error"}


@app.post("/oem/recommendations/publish", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_publish(payload: Dict = Body(...)):
    try:
        rec = payload.get("recommendation") or {}
        saved = oem_recommendation_service.publish_recommendation(rec)
        return {"ok": True, "id": saved.get("id")}
    except Exception as e:
        logger.exception("oem recommendations publish failed", exc_info=e)
        return {"ok": False, "id": None, "error": "server_error"}


@app.get("/oem/recommendations/active", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_active(product_type: str | None = None, brand: str | None = None, model: str | None = None, region: str | None = None):
    try:
        items = oem_recommendation_service.list_active({"product_type": product_type, "brand": brand, "model": model, "region": region})
        return {"ok": True, "items": items}
    except Exception as e:
        logger.exception("oem recommendations active failed", exc_info=e)
        return {"ok": False, "items": [], "error": "server_error"}


@app.post("/oem/recommendations/disable", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_disable(payload: Dict = Body(...)):
    try:
        rec_id = payload.get("id")
        if not rec_id:
            return {"ok": False, "detail": "missing_id"}
        done = oem_recommendation_service.disable_rec(rec_id)
        return {"ok": True, "disabled": done}
    except Exception as e:
        logger.exception("oem recommendations disable failed", exc_info=e)
        return {"ok": False, "disabled": False, "error": "server_error"}
@app.get("/oem/recommendations/preview", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_preview(product_type: str | None = None, brand: str | None = None, model: str | None = None, region: str | None = None):
    try:
        # simple heuristic placeholders
        risk_distribution = {"low": 5, "medium": 3, "high": 2}
        top_risks = ["Potential high wear in humid regions", "Users reporting installation by non-authorized techs"]
        likely_user_needs = ["Clear maintenance steps", "Voltage stabilizer guidance"]
        suggested_oem_actions = ["Push care tips to affected regions", "Offer discounted check-up coupon"]
        suggested_products = ["Extended warranty offer", "Protective accessory kit"]
        recommendation_message = (
            f"Based on current signals for {brand or 'your brand'}, focus on preventive care and voltage protection."
        )
        return {
            "ok": True,
            "risk_distribution": risk_distribution,
            "top_risks": top_risks,
            "likely_user_needs": likely_user_needs,
            "suggested_oem_actions": suggested_oem_actions,
            "suggested_products": suggested_products,
            "recommendation_message": recommendation_message,
        }
    except Exception as e:
        logger.exception("oem recommendation preview failed", exc_info=e)
        return {
            "ok": False,
            "risk_distribution": {},
            "top_risks": [],
            "likely_user_needs": [],
            "suggested_oem_actions": [],
            "suggested_products": [],
            "recommendation_message": "",
            "error": "server_error",
        }
@app.post("/auth/signup")
def signup(payload: SignupRequest, db=Depends(get_db), current=Depends(get_current_user_optional)):
    if payload.role not in ("user", "oem", "admin"):
        raise HTTPException(status_code=400, detail="Role must be user, oem, or admin")
    existing = db.query(UserDB).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    user_count = db.query(UserDB).count()
    if user_count > 0 and (not current or current.role != "admin"):
        raise HTTPException(status_code=403, detail="Only admin can create users")
    if payload.role == "admin" and (not current or current.role != "admin") and user_count > 0:
        raise HTTPException(status_code=403, detail="Only admin can create admin users")
    user = UserDB(
        username=payload.username,
        role=payload.role if current and current.role == "admin" else "user",
        hashed_password=hash_password(payload.password),
        email=payload.email,
    )
    db.add(user)
    db.commit()
    return {"username": user.username, "role": user.role}


@app.post("/auth/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db),
    next_url: str | None = Form(None),
):
    user = db.query(UserDB).filter_by(username=username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.username, user.role)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )
    target = next_url or "/ui/neo-dashboard"
    accepts_json = "application/json" in (request.headers.get("accept") or "")
    if accepts_json:
        response.status_code = status.HTTP_200_OK
        return {"access_token": token, "token_type": "bearer", "role": user.role, "redirect": target}
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )
    return resp


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"status": "logged_out"}


@app.get("/login")
def login_form():
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "login.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.post("/artifacts", dependencies=[Depends(rbac_dependency)])
def create_artifact(payload: ArtifactRequest):
    artifact = ingest_artifact(
        payload.type,
        payload.content,
        payload.source,
        payload.file_path,
        payload.use_ocr,
    )
    return artifact


@app.post("/artifacts/upload", dependencies=[Depends(rbac_dependency)])
async def upload_artifact(
    file: UploadFile = File(...),
    type: ArtifactType = ArtifactType.invoice,
    db=Depends(get_db),
    current=Depends(require_user),
    background_tasks: BackgroundTasks = None,
):
    # Save uploaded file to data/uploads
    uploads_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / file.filename
    with dest.open("wb") as f:
        f.write(await file.read())
    artifact = ingest_artifact(type, file_path=str(dest), use_ocr=True)
    warranty = canonicalize_artifact(artifact, None)
    job = invoice_pipeline.create_job(
        db,
        warranty_id=warranty.id,
        artifact_id=artifact.id,
        source_path=str(dest),
    )
    if background_tasks is not None:
        background_tasks.add_task(invoice_pipeline.run_job, job.id)
    try:
        run_initial_analysis_and_notifications(db, current.username, warranty.id)
    except Exception:
        pass
    return {"artifact": artifact, "warranty_id": warranty.id, "saved_path": str(dest), "job_id": job.id}


@app.post("/warranties/from-artifact", dependencies=[Depends(rbac_dependency)])
def create_warranty(payload: CanonicalRequest, db=Depends(get_db), current=Depends(require_user)):
    artifact = store.artifacts.get(payload.artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    warranty = canonicalize_artifact(artifact, payload.overrides)
    try:
        run_initial_analysis_and_notifications(db, current.username, warranty.id)
    except Exception:
        pass
    return warranty


@app.get("/warranties/{warranty_id}", dependencies=[Depends(rbac_dependency)])
def get_warranty(warranty_id: str):
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    return warranty


@app.post("/warranties/{warranty_id}/process", dependencies=[Depends(rbac_dependency)])
def process_warranty(
    warranty_id: str,
    payload: ProcessWarrantyRequest | None = Body(default=None),
    db=Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    artifact_id = payload.artifact_id if payload else None
    source_path = payload.source_path if payload else None
    if not artifact_id:
        warranty = store.get_warranty_db(warranty_id)
        if warranty and warranty.source_artifact_ids:
            artifact_id = warranty.source_artifact_ids[-1]
    job = invoice_pipeline.create_job(
        db,
        warranty_id=warranty_id,
        artifact_id=artifact_id,
        source_path=source_path,
    )
    if background_tasks is not None:
        background_tasks.add_task(invoice_pipeline.run_job, job.id)
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}", dependencies=[Depends(rbac_dependency)])
def get_job(job_id: str, db=Depends(get_db)):
    job = invoice_pipeline.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/warranties/{warranty_id}/summary", dependencies=[Depends(rbac_dependency)])
def get_warranty_summary(warranty_id: str, db=Depends(get_db)):
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    summary_row = invoice_pipeline.get_latest_summary(db, warranty_id)
    if summary_row:
        return {"warranty_id": warranty_id, "summary": summary_row.summary_text, "source": summary_row.source}
    summary_text, source = summary_engine.summarize_warranty(warranty)
    return {"warranty_id": warranty_id, "summary": summary_text, "source": source}


@app.post("/behaviour-events", dependencies=[Depends(rbac_dependency)])
def push_behaviour_event(payload: BehaviourEventRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    event = BehaviourEvent(
        user_id=payload.user_id,
        warranty_id=payload.warranty_id,
        event_type=payload.event_type,
        details=payload.details or {},
    )
    return store.add_behaviour_event(event)


@app.post("/risk/score", dependencies=[Depends(rbac_dependency)])
def risk_score(payload: RiskRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    return compute_risk(payload.user_id, payload.warranty_id)


@app.get("/advisories/{warranty_id}", dependencies=[Depends(rbac_dependency)])
def advisories(warranty_id: str, user_id: str):
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    risk = compute_risk(user_id, warranty_id)
    variant = policy.assign_variant(user_id, warranty_id, experiment="fogg_nudge", variants=("A", "B"))
    nudges = generate_nudges(risk, variant)
    band_map = {"high": "critical", "medium": "warning", "low": "info"}
    severity = band_map.get(getattr(risk, "band", "low"), "info")
    items = [
        {
            "title": n.title,
            "body": n.message,
            "severity": severity,
            "tags": ["warranty"],
        }
        for n in nudges
    ]
    return {
        "warranty_id": warranty_id,
        "items": items,
        "risk": risk,
        "nudges": nudges,
        "experiment": "fogg_nudge",
        "variant": variant,
    }


@app.post("/advisories/nudge-event", dependencies=[Depends(require_user)])
def log_nudge_event(payload: NudgeEventRequest, db=Depends(get_db)):
    now = datetime.utcnow()
    ev = NudgeEvents(
        user_id=payload.user_id,
        warranty_id=payload.warranty_id,
        nudge_type=payload.nudge_type,
        outcome=payload.outcome,
        variant=payload.variant,
        shown_at=now,
        acted_at=now if payload.outcome == "acted" else None,
        ignored_at=now if payload.outcome == "ignored" else None,
    )
    db.add(ev)
    db.commit()
    return {"status": "recorded"}


@app.post("/service-tickets", dependencies=[Depends(rbac_dependency)])
def service_ticket(payload: ServiceTicketRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    ticket = create_ticket(
        payload.user_id,
        payload.warranty_id,
        payload.symptom,
        payload.evidence or [],
    )
    return ticket


@app.get("/service-tickets/{warranty_id}", dependencies=[Depends(rbac_dependency)])
def list_tickets(warranty_id: str):
    return store.list_tickets(warranty_id)


@app.post("/llm/generate", dependencies=[Depends(rbac_dependency)])
def llm_generate(payload: LLMRequest):
    text, err = generate_text(payload.prompt, payload.model)
    if err:
        raise HTTPException(status_code=500, detail=err)
    log_action("llm_generate", f"model={payload.model} prompt_len={len(payload.prompt)}")
    return {"response": text}


@app.get("/connectors", dependencies=[Depends(require_admin)])
def list_connectors(kind: str | None = None):
    connectors = registry.list(kind)
    return list(connectors.values())


@app.post("/connectors", dependencies=[Depends(require_admin)])
def upsert_connector(payload: ConnectorRequest):
    connector = Connector(
        name=payload.name,
        kind=payload.kind,
        endpoint=payload.endpoint,
        auth_token=payload.auth_token,
        metadata=payload.metadata or {},
    )
    registry.register(connector)
    return connector


@app.post("/connectors/reload", dependencies=[Depends(require_admin)])
def reload_connectors():
    registry.load()
    return {"status": "reloaded", "count": len(registry.list())}


@app.post("/artifacts/capture", dependencies=[Depends(rbac_dependency)])
def capture_artifact(
    type: ArtifactType = ArtifactType.invoice,
    db=Depends(get_db),
    current=Depends(require_user),
    background_tasks: BackgroundTasks = None,
):
    try:
        import cv2  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OpenCV not available: {exc}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not access camera (index 0).")

    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to capture frame from camera.")

    captures_dir = Path(__file__).resolve().parents[1] / "data" / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    dest = captures_dir / "capture.jpg"
    cv2.imwrite(str(dest), frame)

    artifact = ingest_artifact(type, file_path=str(dest), use_ocr=True, source="camera")
    warranty = canonicalize_artifact(artifact, None)
    job = invoice_pipeline.create_job(
        db,
        warranty_id=warranty.id,
        artifact_id=artifact.id,
        source_path=str(dest),
    )
    if background_tasks is not None:
        background_tasks.add_task(invoice_pipeline.run_job, job.id)
    try:
        run_initial_analysis_and_notifications(db, current.username, warranty.id)
    except Exception:
        pass
    return {"artifact": artifact, "warranty_id": warranty.id, "saved_path": str(dest), "job_id": job.id}


@app.get("/ui/warranty/{warranty_id}", dependencies=[Depends(require_user)])
def warranty_ui(request: Request, warranty_id: str, user_id: str):
    warranty = store.warranties.get(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    # Summary
    summary_resp = warranty_summary(SummaryRequest(warranty_id=warranty_id))
    summary_text = summary_resp.get("summary", "")
    # Risk & advisories
    adv = advisories(warranty_id, user_id)
    risk_data = adv["risk"]
    nudges = adv["nudges"]
    variant = adv.get("variant")
    # Predictive
    predictive = compute_predictive_score(user_id, warranty_id, warranty.model_code, None, None)
    return templates.TemplateResponse(
        "warranty.html",
        {
            "request": request,
            "warranty": warranty,
            "summary": summary_text,
            "risk": risk_data,
            "nudges": nudges,
            "variant": variant,
            "predictive": predictive,
        },
    )


@app.get("/scheduler/status", dependencies=[Depends(require_admin)])
def scheduler_status():
    with SessionLocal() as db:
        queue = db.query(OEMFetchDB).all()
        return {
            "review_required": os.getenv("OEM_REVIEW_REQUIRED", "true").lower() == "true",
            "queue": queue,
        }


@app.get("/ui/scheduler", dependencies=[Depends(require_user)])
def scheduler_ui(request: Request):
    with SessionLocal() as db:
        queue = db.query(OEMFetchDB).all()
    return templates.TemplateResponse(
        "scheduler.html",
        {
            "request": request,
            "queue": queue,
            "review_required": os.getenv("OEM_REVIEW_REQUIRED", "true").lower() == "true",
        },
    )


@app.get("/ui/react-dashboard", dependencies=[Depends(require_user)])
def react_dashboard():
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "react_dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/console", dependencies=[Depends(require_user)])
def console_ui():
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "console.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/neo-dashboard", dependencies=[Depends(require_user)])
def neo_dashboard():
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "neo_dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/oem-dashboard", dependencies=[Depends(require_oem_or_admin)])
def oem_dashboard():
    from fastapi.responses import HTMLResponse

    html_path = Path(__file__).resolve().parents[1] / "templates" / "oem_dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.post("/telemetry", dependencies=[Depends(rbac_dependency)])
def push_telemetry(payload: TelemetryRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    event = TelemetryEvent(
        id=generate_id("tel"),
        warranty_id=payload.warranty_id,
        user_id=payload.user_id,
        model_code=payload.model_code,
        region=payload.region,
        timezone=payload.timezone,
        event_type=payload.event_type,
        payload=payload.payload or {},
    )
    return store.add_telemetry(event)


@app.post("/predictive/score", dependencies=[Depends(rbac_dependency)])
def predictive_score(payload: PredictiveRequest):
    data = score_warranty(payload.user_id, payload.warranty_id)
    try:
        risk_label = (data.get("risk_label") or "LOW").upper()
        if risk_label in ("MEDIUM", "HIGH"):
            severity = "warning" if risk_label == "MEDIUM" else "critical"
            notification_service.create_notification(
                user_id=payload.user_id,
                warranty_id=payload.warranty_id,
                type=f"risk_{risk_label.lower()}",
                title=f"Risk {risk_label.title()} detected",
                message=f"Predictive model flagged {risk_label.lower()} risk for warranty {payload.warranty_id}.",
                severity=severity,
            )
        warranty = store.get_warranty_db(payload.warranty_id)
        if warranty and warranty.expiry_date:
            days_left = (warranty.expiry_date - datetime.utcnow().date()).days
            if days_left < 30:
                notification_service.create_notification(
                    user_id=payload.user_id,
                    warranty_id=payload.warranty_id,
                    type="expiry_soon",
                    title="Warranty expiring soon",
                    message=f"Warranty {payload.warranty_id} ends in {max(days_left, 0)} days.",
                    severity="warning" if days_left > 0 else "critical",
            )
    except Exception:
        pass
    if data.get("risk_label") == "UNKNOWN":
        return {
            "risk_label": "UNKNOWN",
            "risk_score": data.get("risk_score", 0.5),
            "proba": data.get("proba", {}),
            "reasons": data.get("reasons", ["Predictive engine not ready yet."]),
            "base_risk_score": data.get("base_risk_score"),
            "behaviour_delta": data.get("behaviour_delta"),
            "behaviour_reasons": data.get("behaviour_reasons", []),
        }
    return {
        "risk_label": data.get("risk_label", "LOW"),
        "risk_score": data.get("risk_score", 0.0),
        "proba": data.get("proba", {}),
        "reasons": data.get("reasons", []),
        "base_risk_score": data.get("base_risk_score"),
        "behaviour_delta": data.get("behaviour_delta"),
        "behaviour_reasons": data.get("behaviour_reasons", []),
    }


@app.get("/recommendations", dependencies=[Depends(require_user)], response_model=RecommendationsResponse)
def get_recommendations(
    user_id: str | None = None,
    warranty_id: str | None = None,
    legacy: bool | None = False,
    db=Depends(get_db),
    current=Depends(require_user),
):
    uid = user_id or current.username
    recs = recommendation_service.get_recommendations_for_user(db, uid, warranty_id)
    if legacy:
        # legacy shape: just the recommendations list
        from fastapi.responses import JSONResponse
        return JSONResponse(content=recs.get("recommendations", []))
    return recs


@app.get("/notifications", dependencies=[Depends(require_user)])
def get_notifications(user_id: str | None = None, only_unread: bool = True, current=Depends(require_user)):
    uid = user_id or current.username
    return notification_service.list_notifications(uid, only_unread)


class NotificationReadRequest(BaseModel):
    user_id: str | None = None


@app.post("/notifications/{notification_id}/read", dependencies=[Depends(require_user)])
def mark_notification_read(notification_id: str, payload: NotificationReadRequest | None = None, current=Depends(require_user)):
    uid = (payload.user_id if payload else None) or current.username
    ok = notification_service.mark_notification_read(uid, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


class NotificationOut(BaseModel):
    id: str
    user_id: str | None = None
    warranty_id: str | None = None
    audience: str = "user"
    brand: str | None = None
    region: str | None = None
    type: str
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True


@app.get("/oem/notifications", dependencies=[Depends(require_oem_or_admin)])
def get_oem_notifications(
    only_unread: bool = True,
    db=Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    items = notification_service.list_notifications_for_oem(
        db=db,
        user_id=current.username,
        only_unread=only_unread,
        limit=50,
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "is_read": bool(n.is_read),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]


@app.post("/oem/notifications/{notification_id}/read", dependencies=[Depends(require_oem_or_admin)])
def mark_oem_notification_as_read(
    notification_id: str,
    db=Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    n = notification_service.mark_notification_read_for_oem(
        db=db, notification_id=notification_id, user_id=current.username
    )
    if not n:
        raise HTTPException(status_code=404, detail="OEM notification not found")
    return {"status": "ok"}


@app.post("/ev/battery/score", dependencies=[Depends(require_user)])
def ev_battery_score(payload: EVBatteryRequest, db=Depends(get_db), current=Depends(require_user)):
    feats = payload.dict()
    # attempt to enrich from behaviour/telemetry if warranty present
    if payload.warranty_id:
        prof = (
            db.query(BehaviourProfile)
            .filter_by(user_id=current.username, warranty_id=payload.warranty_id)
            .order_by(BehaviourProfile.id.desc())
            .first()
        )
        if prof:
            feats.setdefault("behaviour_score", prof.behaviour_score or 0.5)
            feats.setdefault("care_score", prof.care_score or 0.5)
            feats.setdefault("responsiveness_score", prof.responsiveness_score or 0.5)
        ev_tel = (
            db.query(EVTelemetryDB)
            .filter_by(warranty_id=payload.warranty_id, user_id=current.username)
            .order_by(EVTelemetryDB.id.desc())
            .first()
        )
        if ev_tel:
            for key in ["daily_km", "fast_charge_sessions", "deep_discharge_events", "max_temp_seen", "region_climate_band"]:
                val = getattr(ev_tel, key)
                if val is not None:
                    feats[key] = val
    score = ev_battery_service.score_ev_battery(feats)
    return {
        "risk_label": score.risk_label,
        "risk_score": score.risk_score,
        "proba": score.proba,
        "reasons": score.reasons,
        "suggestions": score.suggestions,
    }


@app.get("/predictive/self-test", dependencies=[Depends(require_user)])
def predictive_self_test():
    samples = [
        {"user_id": "u_low", "warranty_id": "w_low", "vec": [0, 6, 1.5, 0, 0, 1, 0.9, 0.9, 0.9, 0, 0, 0]},
        {"user_id": "u_med", "warranty_id": "w_med", "vec": [0, 20, 3.0, 3, 0, 1, 0.6, 0.6, 0.5, 0, 0, 0]},
        {"user_id": "u_high", "warranty_id": "w_high", "vec": [0, 40, 6.0, 8, 2, 0, 0.25, 0.3, 0.2, 0, 0, 0]},
    ]
    preds = []
    for s in samples:
        try:
            predictive_model.load()
            if predictive_model.error:
                preds.append({"id": s["user_id"], "error": predictive_model.error})
                continue
            label, score, proba = predictive_model.predict(s["vec"])
            preds.append({"id": s["user_id"], "label": label, "score": score, "proba": proba})
        except Exception as exc:
            preds.append({"id": s["user_id"], "error": str(exc)})
    return {"predictions": preds}


@app.post("/peer-reviews/update", dependencies=[Depends(require_oem_or_admin)])
def peer_reviews_update(payload: List[PeerReviewUpdate]):
    stored = []
    with SessionLocal() as db:
        for item in payload:
            rec = peer_review_service.record_peer_signal(
                db,
                product_type=item.product_type,
                brand=item.brand,
                model=item.model,
                symptom_keyword=item.symptom_keyword,
                severity_hint=item.severity_hint,
                source=item.source,
                avg_rating=item.avg_rating,
                review_sentiment=item.review_sentiment,
                warranty_id=item.warranty_id,
                failure_keywords=item.failure_keywords or [],
            )
            stored.append({"id": rec.id})
    return {"status": "updated", "count": len(stored)}


@app.post("/symptom-search/log", dependencies=[Depends(require_user)])
def symptom_search_log(payload: SymptomSearchLogRequest):
    rec = search_log_service.log_symptom_search(
        user_id=payload.user_id,
        product_type=payload.product_type,
        brand=payload.brand,
        model=payload.model,
        query_text=payload.query_text,
        region=payload.region,
        matched_component=payload.matched_component,
        warranty_id=payload.warranty_id,
    )
    return {"status": "ok", "id": rec.id}


class ProductInterestEvent(BaseModel):
    user_id: str
    warranty_id: str
    region: str | None = None
    product_id: str
    action: str
    ts: str | None = None
    risk_band: str | None = None
    title: str | None = None


@app.post("/events/product-interest", dependencies=[Depends(require_user)])
def product_interest_event(payload: ProductInterestEvent, current=Depends(require_user)):
    event = payload.dict()
    event.setdefault("user_id", current.username)
    prod_recs_service.record_product_interest_event(event)
    return {"status": "ok"}


@app.get("/oem/risk-stats", dependencies=[Depends(require_oem_or_admin)])
def oem_risk_stats(
    brand: str | None = None, model: str | None = None, product_type: str | None = None, region: str | None = None, current=Depends(require_oem_or_admin), db=Depends(get_db)
):
    # Predictive distribution based on behaviour profiles we have
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    behaviour_snapshot = {"behaviour": 0.0, "care": 0.0, "responsiveness": 0.0, "count": 0}
    ev_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    try:
        profiles = db.query(BehaviourProfile).all()
    except Exception:
        profiles = []
    for p in profiles:
        w = store.get_warranty_db(p.warranty_id) if p.warranty_id else None
        if brand and w and w.brand != brand:
            continue
        if model and w and w.model_code != model:
            continue
        behaviour_snapshot["behaviour"] += p.behaviour_score
        behaviour_snapshot["care"] += p.care_score
        behaviour_snapshot["responsiveness"] += p.responsiveness_score
        behaviour_snapshot["count"] += 1
        try:
            pred = compute_predictive_score(p.user_id, p.warranty_id or "", getattr(w, "model_code", None), getattr(w, "region_code", None), None)
            band = (pred.band or "UNKNOWN").upper()
            risk_counts[band] = risk_counts.get(band, 0) + 1
        except Exception:
            risk_counts["UNKNOWN"] = risk_counts.get("UNKNOWN", 0) + 1
        # EV battery quick count (placeholder)
        name = (w.product_name or "").lower() if w else ""
        pt_lower = p.product_type.lower() if getattr(p, "product_type", None) else ""
        if "ev" in name or ("ev" in pt_lower):
            ev_score = ev_battery_service.score_ev_battery(
                {
                    "product_type": 3,
                    "age_months": 12,
                    "daily_km": 40,
                    "fast_charge_sessions": 4,
                    "deep_discharge_events": 1,
                    "max_temp_seen": 32,
                    "behaviour_score": p.behaviour_score,
                    "care_score": p.care_score,
                    "responsiveness_score": p.responsiveness_score,
                    "region_climate_band": 1,
                }
            )
            ev_counts[ev_score.risk_label] = ev_counts.get(ev_score.risk_label, 0) + 1

    avg_behaviour = {}
    if behaviour_snapshot["count"]:
        c = behaviour_snapshot["count"]
        avg_behaviour = {
            "behaviour_score": behaviour_snapshot["behaviour"] / c,
            "care_score": behaviour_snapshot["care"] / c,
            "responsiveness_score": behaviour_snapshot["responsiveness"] / c,
        }

    peer_stats = peer_review_service.get_issue_stats(product_type, brand, model, region)
    symptom_trends = search_log_service.get_symptom_trends(product_type, brand, model, region)
    product_interest = prod_recs_service.aggregate_product_interest(region=region)
    stats = {
        "risk_distribution": risk_counts,
        "behaviour_snapshot": avg_behaviour,
        "peer_review": peer_stats,
        "symptoms": symptom_trends,
        "ev_battery": {"risk_distribution": ev_counts},
        "product_interest": product_interest,
    }
    # OEM notification for high-risk clusters
    total = sum(risk_counts.values())
    high_count = risk_counts.get("HIGH", 0) if isinstance(risk_counts, dict) else 0
    high_ratio = (high_count / total) if total else 0.0
    try:
        if high_count >= 10 or high_ratio >= 0.3:
            notification_service.create_oem_notification(
                db=db,
                user_id=current.username,
                ntype="oem_high_risk_cluster",
                title="High-risk cluster detected",
                message=(
                    f"We’ve detected an elevated number of HIGH-risk warranties for {brand or 'your brand'} "
                    f"in region {region or 'all regions'}. Check OEM Analytics to review affected devices."
                ),
                severity="warning",
                brand=brand,
                region=region,
            )
    except Exception:
        pass
    return stats


@app.post("/oem/fetch", dependencies=[Depends(rbac_dependency)])
def oem_fetch(payload: OemFetchRequest):
    with SessionLocal() as db:
        db.merge(
            OEMFetchDB(
                id=payload.url,
                brand=payload.brand,
                model=payload.model,
                region=payload.region,
                url=payload.url,
                status="pending",
            )
        )
        db.commit()
    if not payload.immediate:
        review = create_review("oem_fetch", payload.dict())
        return {"status": "review_pending", "review_id": review.id}
    artifact = fetch_oem_page(payload.url, payload.brand, payload.model, payload.region)
    return {"status": "fetched", "artifact": artifact}


@app.post("/oem/fetch/form", dependencies=[Depends(rbac_dependency)])
def oem_fetch_form(
    brand: str = Form(...),
    model: str = Form(...),
    url: str = Form(...),
    region: str | None = Form(None),
):
    req = OemFetchRequest(brand=brand, model=model, url=url, region=region, immediate=False)
    return oem_fetch(req)


@app.post("/warranties/summary", dependencies=[Depends(rbac_dependency)])
def warranty_summary(payload: SummaryRequest):
    warranty = store.get_warranty_db(payload.warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    prompt = (
        "Summarize the warranty in under 120 words; list coverage, exclusions, expiry, and claim steps. "
        "Return plain text.\n\n"
        f"Brand: {warranty.brand}\nModel: {warranty.model_code}\nExpiry: {warranty.expiry_date}\n"
        f"Coverage months: {warranty.coverage_months}\nTerms: {warranty.terms}\nExclusions: {warranty.exclusions}\n"
        f"Claim steps: {warranty.claim_steps}\n"
    )
    text, err = generate_text(prompt, None)
    if err or not text:
        lines = [
            f"Brand: {warranty.brand or 'N/A'} Model: {warranty.model_code or 'N/A'}",
            f"Expiry: {warranty.expiry_date or 'N/A'} Coverage months: {warranty.coverage_months or 'N/A'}",
            "Terms: " + "; ".join(warranty.terms),
            "Exclusions: " + "; ".join(warranty.exclusions),
            "Claim steps: " + "; ".join(warranty.claim_steps),
        ]
        text = "\n".join(lines)
    log_action("warranty_summary", f"warranty_id={payload.warranty_id} prompt_len={len(prompt)}")
    return {"summary": text}


@app.get("/warranties/{warranty_id}/export", dependencies=[Depends(rbac_dependency)])
def warranty_export(warranty_id: str, format: str = "txt"):
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    summary = warranty_summary(SummaryRequest(warranty_id=warranty_id)).get("summary", "")
    fname = f"warranty_{warranty_id}.{format}"
    if format == "txt":
        data = export_warranty_txt(summary)
        media = "text/plain"
    elif format == "html":
        data = export_warranty_html(summary)
        media = "text/html"
    elif format == "pdf":
        data = export_warranty_pdf(summary, title=f"Warranty {warranty_id}")
        media = "application/pdf"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
    from fastapi.responses import Response

    return Response(content=data, media_type=media, headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.get("/reviews", dependencies=[Depends(require_admin)])
def list_reviews(status: str | None = None):
    return store.list_reviews(status)


@app.post("/reviews/{review_id}/approve", dependencies=[Depends(require_admin)])
def approve(review_id: str, reason: str | None = None):
    try:
        item = approve_review(review_id, reason)
        if item.action == "oem_fetch":
            data = item.payload
            artifact = fetch_oem_page(data["url"], data["brand"], data["model"], data.get("region"))
            return {"review": item, "artifact": artifact}
        return {"review": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found")


@app.post("/reviews/{review_id}/reject", dependencies=[Depends(require_admin)])
def reject(review_id: str, reason: str | None = None):
    try:
        item = reject_review(review_id, reason)
        return {"review": item}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review not found")


@app.get("/oem/behaviour-stats", dependencies=[Depends(require_oem_or_admin)])
def oem_behaviour_stats():
    aggregates = {}
    with SessionLocal() as db:
        profiles = db.query(BehaviourProfile).all()
    for p in profiles:
        warranty = store.get_warranty_db(p.warranty_id)
        if not warranty:
            continue
        key = (warranty.brand or "unknown", warranty.model_code or "unknown")
        agg = aggregates.setdefault(
            key,
            {"behaviour_sum": 0.0, "care_sum": 0.0, "resp_sum": 0.0, "risk_sum": 0.0, "count": 0},
        )
        agg["behaviour_sum"] += p.behaviour_score
        agg["care_sum"] += p.care_score
        agg["resp_sum"] += p.responsiveness_score
        try:
            risk = compute_predictive_score(p.user_id, p.warranty_id, warranty.model_code, warranty.brand, None).score
        except Exception:
            risk = 0.0
        agg["risk_sum"] += risk
        agg["count"] += 1
    results = []
    for (brand, model_code), agg in aggregates.items():
        count = agg["count"] or 1
        results.append(
            {
                "brand": brand,
                "model_code": model_code,
                "avg_behaviour": agg["behaviour_sum"] / count,
                "avg_care": agg["care_sum"] / count,
                "avg_responsiveness": agg["resp_sum"] / count,
                "avg_predictive_risk": agg["risk_sum"] / count,
                "sample_size": count,
            }
        )
    return {"items": results}
