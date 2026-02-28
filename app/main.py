import os
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
from urllib.parse import quote, urlencode
from html import escape

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, Form, Response, status, Body, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import Session


class BaseModel(PydanticBaseModel):
    # Allow fields like model_code without protected namespace warnings
    model_config = {"protected_namespaces": ()}

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
from .services.oem_domains import load_verified_domains, save_verified_domains
from .services.oem_domain_verify import verify_or_suggest
from .services.review_crawler import crawl_reviews
from .services import notifications as notification_service
from .services import product_recommendations as prod_recs_service
from .services import regional_policy as regional_policy_service
from .services import oem_issue_signals as oem_issue_service
from .services import oem_question_service
from .services import ollama_questions
from .services import oem_recommendation_service
from .services import oem_communication as oem_communication_service
from .services import oem_dispatch as oem_dispatch_service
from .services import kpi_watchdog as kpi_watchdog_service
from .services import kpi_remediation as kpi_remediation_service
from .services import kpi_execution as kpi_execution_service
from .services import invoice_pipeline
from .services import summary_engine
from .services import terms_lookup
from .services import rag as rag_service
from .services import remote_diagnostics as remote_diag_service
from .services import diagnostics_capability as diag_cap_service
from .services import emailer as emailer_service
from .services.warranty_status import compute_warranty_status
from .services.notifications import run_initial_analysis_and_notifications
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
    ParsedFieldDB,
    PipelineJobDB,
    WarrantySummaryDB,
    RegionalPolicyDB,
    OemIssueSignalDB,
    RiskSnapshotDB,
    NotificationDB,
    ProductReviewDB,
    ReviewPageDB,
    WarrantyOwnerDB,
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


class ConsentRequest(BaseModel):
    user_id: str
    consent_analytics: bool


class OemVerifyRequest(BaseModel):
    brand: str
    domain: str
    region: str | None = None


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


class TermsRefreshRequest(BaseModel):
    warranty_id: str
    force: bool = False
    url_override: str | None = None


class RegionRuleRequest(BaseModel):
    region: str
    rule_json: dict
    brand: str | None = None
    model_code: str | None = None
    product_type: str | None = None
    active: bool = True


class OemIssueSignalRequest(BaseModel):
    brand: str | None = None
    model_code: str | None = None
    product_type: str | None = None
    region: str | None = None
    issue_type: str | None = None
    severity: float | None = None
    count: int | None = None
    source_url: str | None = None


class RemoteAssistRequest(BaseModel):
    warranty_id: str
    command_type: str = "health_check"


class OemCommunicationSendRequest(BaseModel):
    recipient_user_id: str
    kind: str = "important_update"  # important_update | product_recommendation
    title: str
    message: str
    warranty_id: str | None = None
    brand: str | None = None
    model_code: str | None = None
    product_type: str | None = None
    region: str | None = None
    channel: str = "in_app"
    send_if_ineligible: bool = False
    metadata: dict | None = None


class OemDispatchRunRequest(BaseModel):
    dry_run: bool = True


class KpiWatchdogRunRequest(BaseModel):
    report_file: str | None = None
    notify: bool = True


class KpiRemediationRunRequest(BaseModel):
    report_file: str | None = None
    notify: bool = True
    source: str = "manual"


class KpiTaskUpdateRequest(BaseModel):
    status: str
    notes: str | None = None
    owner: str | None = None


class SignupRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "user"  # user | oem | tpa | admin (admin only via existing admin)


class LoginRequest(BaseModel):
    username: str  # username or email
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    interval = int(os.getenv("OEM_REFRESH_MINUTES", "120"))
    start_scheduler(interval)
    yield


app = FastAPI(
    title="Smart Warranty Hub MVP",
    description="Warranty ingestion, canonicalisation, risk, nudges, predictive care, OEM fetch, and service orchestration.",
    version="0.2.0",
    lifespan=lifespan,
)

# Optional host and HTTPS hardening (recommended for Railway production).
_allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
if _allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


# Reviews Router
from .routes import reviews
app.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
from .routes import remote_diagnostics
app.include_router(
    remote_diagnostics.router,
    prefix="/remote-diagnostics",
    tags=["Remote Diagnostics"],
)
from .routes import guided_diagnostics
app.include_router(
    guided_diagnostics.router,
    prefix="/guided-diagnostics",
    tags=["Guided Diagnostics"],
)


dist_path = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dist_path), html=True), name="dashboard")


@app.get("/dashboard-dev", dependencies=[Depends(require_user)])
def dashboard_dev():
    dev_url = os.getenv("VITE_DEV_URL")
    if not dev_url:
        raise HTTPException(status_code=404, detail="Set VITE_DEV_URL to use the dev dashboard.")
    return RedirectResponse(dev_url)


@app.middleware("http")
async def cache_dashboard(request: Request, call_next):
    # Proxy-aware HTTPS redirect: avoids self-loop behind Railway/edge proxies.
    force_https = os.getenv("FORCE_HTTPS_REDIRECT", "0").strip().lower() in ("1", "true", "yes")
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
    # Redirect only when proxy explicitly reports HTTP.
    # This avoids self-loop when upstream omits forwarded proto.
    if force_https and forwarded_proto == "http":
        return RedirectResponse(url=str(request.url.replace(scheme="https")), status_code=307)

    response = await call_next(request)
    path = request.url.path
    if path.startswith("/dashboard"):
        # Cache static assets aggressively; index less so
        if "." in path:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
    # Security headers suitable for app + API responses.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'",
    )
    if request.headers.get("x-forwarded-proto", "").lower() == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/robots.txt")
def robots_txt(request: Request):
    base = str(request.base_url).rstrip("/")
    body = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml")
def sitemap_xml(request: Request):
    base = str(request.base_url).rstrip("/")
    urls = [
        f"{base}/",
        f"{base}/api/health",
        f"{base}/health/full",
        f"{base}/ui/neo-dashboard",
        f"{base}/auth/login",
        f"{base}/login",
    ]
    now = datetime.utcnow().strftime("%Y-%m-%d")
    rows = []
    for u in urls:
        rows.append(
            f"<url><loc>{escape(u)}</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(rows)
        + "</urlset>"
    )
    return Response(content=xml, media_type="application/xml; charset=utf-8")


@app.get("/")
def root(request: Request):
    """
    Browser users should land on a public SEO page that links into app flows.
    API/CLI callers can still use the JSON health at /api/health (or /health/full).
    """
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept or "*/*" in accept:
        return templates.TemplateResponse("public_site.html", {"request": request})
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
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


@app.get("/health/rag")
def health_rag(db=Depends(get_db)):
    return rag_service.health(db)


@app.get("/health/full")
def health_full():
    ocr_ok, ocr_detail = ocr_service.health()
    llm_ok, llm_detail, llm_model = summary_engine.health()
    pred_ok, pred_detail = predictive_service.health()
    rag = rag_service.health()
    status = "ok" if (ocr_ok and llm_ok and pred_ok) else "degraded"
    return {
        "status": status,
        "checks": {
            "ocr": {"ok": ocr_ok, "detail": ocr_detail},
            "llm": {"ok": llm_ok, "detail": llm_detail, "model": llm_model},
            "predictive": {"ok": pred_ok, "detail": pred_detail},
            "rag": rag,
        },
    }


def _require_consent(user_id: str) -> None:
    if os.getenv("REQUIRE_USER_CONSENT", "false").lower() != "true":
        return
    with SessionLocal() as db:
        user = db.query(UserDB).filter_by(username=user_id).first()
        if not user or not getattr(user, "consent_analytics", 0):
            raise HTTPException(status_code=403, detail="User consent required")


def _demo_public_ui_enabled() -> bool:
    return os.getenv("DEMO_PUBLIC_UI", "0").strip().lower() in ("1", "true", "yes")


def _public_signup_enabled() -> bool:
    return os.getenv("PUBLIC_SIGNUP_ENABLED", "1").strip().lower() in ("1", "true", "yes")


_INVOICE_NON_WARRANTY_HINTS = (
    "sweet",
    "sweets",
    "bakery",
    "restaurant",
    "cafe",
    "grocery",
    "vegetable",
    "fruit",
    "milk",
    "snack",
    "food",
    "pharmacy",
)


def _invoice_guardrail(content: str) -> Dict[str, object]:
    """
    Soft classifier for invoice relevance.
    - clear: looks like warranty-related invoice
    - warn: uncertain, still process
    - needs_review: strongly non-warranty, require explicit continue
    """
    text = (content or "").strip()
    low = text.lower()
    if not low:
        return {
            "decision": "warn",
            "message": "We could not read enough invoice text. If this is a warranty invoice, continue and add product details manually.",
        }

    positive = 0
    for token in ("warranty", "serial", "imei", "model", "invoice", "purchase date", "product", "device"):
        if token in low:
            positive += 1
    if re.search(r"\b\d{1,2}\s*(month|months|year|years|yr|yrs)\s*warranty\b", low):
        positive += 2
    if re.search(r"\b(imei|serial|s\/n|sn)\b", low):
        positive += 1

    negative_hits = [token for token in _INVOICE_NON_WARRANTY_HINTS if token in low]

    if len(negative_hits) >= 2 and positive == 0:
        return {
            "decision": "needs_review",
            "message": "This looks like a non-warranty bill. Continue only if this is actually a product warranty invoice.",
            "negative_hints": negative_hits[:3],
        }
    if len(negative_hits) >= 1 and positive <= 1:
        return {
            "decision": "warn",
            "message": "This bill may be outside warranty scope. We will still process it, and you can correct product details if needed.",
            "negative_hints": negative_hits[:3],
        }
    return {"decision": "clear", "message": None}


def _build_ui_login_redirect(request: Request) -> RedirectResponse:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return RedirectResponse(
        url=f"/login?next={quote(next_path, safe='')}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _ensure_ui_user(request: Request, current: Optional[UserDB]) -> Optional[RedirectResponse]:
    if _demo_public_ui_enabled():
        return None
    if not current:
        return _build_ui_login_redirect(request)
    return None


def _ensure_ui_oem_or_admin(request: Request, current: Optional[UserDB]) -> Optional[RedirectResponse]:
    if _demo_public_ui_enabled():
        return None
    if not current:
        return _build_ui_login_redirect(request)
    if current.role not in ("admin", "oem", "tpa"):
        # UI-friendly behavior: send normal users back to their dashboard instead of a JSON 403.
        return RedirectResponse(
            url="/ui/neo-dashboard?notice=oem_admin_only",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return None


def _user_can_access_warranty(db: Session, *, user: UserDB, warranty_id: str) -> bool:
    if user.role in ("admin", "oem"):
        return True
    rec = (
        db.query(WarrantyOwnerDB)
        .filter_by(user_id=user.username, warranty_id=warranty_id)
        .first()
    )
    return rec is not None


def _require_warranty_access(db: Session, *, user: UserDB, warranty_id: str) -> None:
    if _user_can_access_warranty(db, user=user, warranty_id=warranty_id):
        return

    # Backward-compatibility + resilience: if a warranty has no owners recorded yet,
    # allow the first authenticated user who already has the ID to claim it.
    # This avoids users getting stuck if ownership link creation failed on upload.
    if user.role == "user":
        try:
            any_owner = (
                db.query(WarrantyOwnerDB)
                .filter_by(warranty_id=warranty_id)
                .first()
            )
            if any_owner is None:
                exists = db.query(WarrantyDB.id).filter_by(id=warranty_id).first()
                if exists:
                    db.merge(WarrantyOwnerDB(user_id=user.username, warranty_id=warranty_id))
                    db.commit()
                    return
        except Exception:
            db.rollback()

    raise HTTPException(status_code=403, detail="forbidden")


def _build_warranty_status_info(warranty) -> Dict[str, object]:
    st = compute_warranty_status(
        purchase_date=getattr(warranty, "purchase_date", None),
        coverage_months=getattr(warranty, "coverage_months", None),
        expiry_date=getattr(warranty, "expiry_date", None),
    )
    return {
        "warranty_status": st.get("status"),
        "claim_eligibility": st.get("claim_eligibility"),
        "claim_message": st.get("claim_message"),
        "days_left": st.get("days_left"),
        "days_lapsed": st.get("days_lapsed"),
        "lapsed_text": st.get("lapsed_text"),
        "expiry_date_used": st.get("expiry_date_used"),
        "expiry_source": st.get("expiry_source"),
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
        _require_consent(payload.user_id)
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


@app.post("/oem/recommendations/publish", dependencies=[Depends(require_oem_or_admin)])
@app.post("/api/oem/recommendations/publish", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_publish(payload: Dict = Body(...)):
    try:
        rec = payload.get("recommendation") or {}
        saved = oem_recommendation_service.publish_recommendation(rec)
        return {"ok": True, "id": saved.get("id")}
    except Exception as e:
        logger.exception("oem recommendations publish failed", exc_info=e)
        return {"ok": False, "id": None, "error": "server_error"}


@app.get("/oem/recommendations/active", dependencies=[Depends(require_oem_or_admin)])
@app.get("/api/oem/recommendations/active", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_active(product_type: str | None = None, brand: str | None = None, model: str | None = None, region: str | None = None):
    try:
        items = oem_recommendation_service.list_active({"product_type": product_type, "brand": brand, "model": model, "region": region})
        return {"ok": True, "items": items}
    except Exception as e:
        logger.exception("oem recommendations active failed", exc_info=e)
        return {"ok": False, "items": [], "error": "server_error"}


@app.post("/oem/recommendations/disable", dependencies=[Depends(require_oem_or_admin)])
@app.post("/api/oem/recommendations/disable", dependencies=[Depends(require_oem_or_admin)])
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
@app.get("/api/oem/recommendations/preview", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_preview(
    product_type: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    region: str | None = None,
    db=Depends(get_db),
):
    try:
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        snapshots = db.query(RiskSnapshotDB).all()
        for snap in snapshots:
            w = store.get_warranty_db(snap.warranty_id)
            if brand and w and (w.brand or "").lower() != brand.lower():
                continue
            if model and w and (w.model_code or "").lower() != model.lower():
                continue
            if region and w and (w.region_code or "").lower() != region.lower():
                continue
            label = (snap.risk_label or "").upper()
            if label == "HIGH":
                risk_distribution["high"] += 1
            elif label == "MEDIUM":
                risk_distribution["medium"] += 1
            else:
                risk_distribution["low"] += 1

        issue_query = db.query(OemIssueSignalDB)
        if brand:
            issue_query = issue_query.filter_by(brand=brand)
        if model:
            issue_query = issue_query.filter_by(model_code=model)
        if region:
            issue_query = issue_query.filter_by(region=region)
        issues = issue_query.order_by(OemIssueSignalDB.last_seen_at.desc()).limit(25).all()
        top_risks = []
        for row in issues[:5]:
            issue = row.issue_type or "unknown_issue"
            sev = row.severity if row.severity is not None else 0.0
            cnt = row.count or 0
            top_risks.append(f"{issue}: severity {sev:.2f}, reports {cnt}")
        if not top_risks:
            top_risks = ["No major OEM issue spikes in current window."]

        symptoms = search_log_service.get_symptom_trends(product_type, brand, model, region)
        likely_user_needs = symptoms.get("top_keywords") or symptoms.get("top_components") or ["General preventive care guidance"]

        suggested_oem_actions = []
        if risk_distribution["high"] > 0:
            suggested_oem_actions.append("Send targeted preventive tips to high-risk segments.")
        if any("overheat" in s.lower() or "heating" in s.lower() for s in top_risks):
            suggested_oem_actions.append("Issue temperature and ventilation advisory.")
        if any("voltage" in s.lower() for s in likely_user_needs):
            suggested_oem_actions.append("Recommend stabilizer usage for affected regions.")
        if not suggested_oem_actions:
            suggested_oem_actions.append("Continue weekly monitoring and trend validation.")

        product_interest = prod_recs_service.aggregate_product_interest(region=region, limit=5)
        suggested_products = [item.get("title") or item.get("product_id") for item in product_interest] or ["No strong product demand signal yet."]
        recommendation_message = (
            f"Live recommendation for {brand or 'your brand'}: prioritize preventive care for high-risk users and act on top issue trends."
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


@app.post("/oem/recommendations/generate", dependencies=[Depends(require_oem_or_admin)])
@app.post("/api/oem/recommendations/generate", dependencies=[Depends(require_oem_or_admin)])
def oem_recommendations_generate(payload: Dict = Body(None), db=Depends(get_db)):
    try:
        payload = payload or {}
        preview = oem_recommendations_preview(
            product_type=payload.get("product_type"),
            brand=payload.get("brand"),
            model=payload.get("model") or payload.get("model_code"),
            region=payload.get("region"),
            db=db,
        )
        if not preview.get("ok"):
            return {"ok": False, "recommendations": [], "error": preview.get("error", "server_error")}
        rec = {
            "product_type": payload.get("product_type"),
            "brand": payload.get("brand"),
            "model": payload.get("model") or payload.get("model_code"),
            "region": payload.get("region"),
            "title": "Preventive care recommendation",
            "message": preview.get("recommendation_message"),
            "tags": preview.get("top_risks", [])[:3],
            "risk_hint": preview.get("risk_distribution"),
            "source": "swh_generated",
            "status": "draft",
        }
        return {"ok": True, "recommendations": [rec], "preview": preview}
    except Exception as e:
        logger.exception("oem recommendations generate failed", exc_info=e)
        return {"ok": False, "recommendations": [], "error": "server_error"}
def _ensure_users_table_and_admin(db) -> None:
    """Safety fallback for partially initialized production DBs."""
    try:
        UserDB.__table__.create(bind=db.get_bind(), checkfirst=True)
    except Exception:
        return
    try:
        allow_insecure = os.getenv("ALLOW_INSECURE_DEFAULTS", "true").strip().lower() in ("1", "true", "yes", "on")
        admin_user = os.getenv("ADMIN_USER")
        admin_pass = os.getenv("ADMIN_PASS")
        if not admin_user or not admin_pass:
            if allow_insecure:
                admin_user = "admin"
                admin_pass = "admin123"
            else:
                return
        existing = db.query(UserDB).filter_by(username=admin_user).first()
        if not existing:
            db.add(
                UserDB(
                    username=admin_user,
                    role="admin",
                    hashed_password=hash_password(admin_pass),
                    email=None,
                )
            )
            db.commit()
    except Exception:
        db.rollback()


@app.post("/auth/signup")
def signup(payload: SignupRequest, db=Depends(get_db), current=Depends(get_current_user_optional)):
    if payload.role not in ("user", "oem", "tpa", "admin"):
        raise HTTPException(status_code=400, detail="Role must be user, oem, tpa, or admin")
    try:
        existing = db.query(UserDB).filter_by(username=payload.username).first()
    except (ProgrammingError, OperationalError):
        db.rollback()
        _ensure_users_table_and_admin(db)
        existing = db.query(UserDB).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    try:
        user_count = db.query(UserDB).count()
    except (ProgrammingError, OperationalError):
        db.rollback()
        _ensure_users_table_and_admin(db)
        user_count = db.query(UserDB).count()
    if user_count > 0 and (not current or current.role != "admin"):
        raise HTTPException(status_code=403, detail="Only admin can create users")
    if payload.role == "admin" and (not current or current.role != "admin") and user_count > 0:
        raise HTTPException(status_code=403, detail="Only admin can create admin users")
    # Fresh-account safety: if this username existed historically and was deleted,
    # remove any stale ownership links so the new account starts clean.
    db.query(WarrantyOwnerDB).filter_by(user_id=payload.username).delete(synchronize_session=False)
    user = UserDB(
        username=payload.username,
        role=payload.role if current and current.role == "admin" else "user",
        hashed_password=hash_password(payload.password),
        email=payload.email,
    )
    db.add(user)
    db.commit()
    try:
        emailer_service.send_welcome_email(
            to_email=user.email,
            username=user.username,
            role=user.role,
        )
    except Exception:
        pass
    return {"username": user.username, "role": user.role}


@app.post("/auth/signup/form")
def signup_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str | None = Form(None),
    next_url: str | None = Form(None),
    db=Depends(get_db),
):
    login_params = {"next": next_url or "/ui/neo-dashboard"}
    if not _public_signup_enabled():
        login_params["signup"] = "disabled"
        return RedirectResponse(
            url=f"/login?{urlencode(login_params)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    username = username.strip()
    email = (email or "").strip() or None
    if len(username) < 3 or len(password) < 6:
        login_params["signup"] = "invalid"
        return RedirectResponse(
            url=f"/login?{urlencode(login_params)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        existing = db.query(UserDB).filter_by(username=username).first()
    except (ProgrammingError, OperationalError):
        db.rollback()
        _ensure_users_table_and_admin(db)
        existing = db.query(UserDB).filter_by(username=username).first()
    if existing:
        login_params["signup"] = "exists"
        return RedirectResponse(
            url=f"/login?{urlencode(login_params)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    # Fresh-account safety: clear stale ownership links for recycled usernames.
    db.query(WarrantyOwnerDB).filter_by(user_id=username).delete(synchronize_session=False)
    db.add(
        UserDB(
            username=username,
            role="user",
            hashed_password=hash_password(password),
            email=email,
        )
    )
    db.commit()
    try:
        emailer_service.send_welcome_email(
            to_email=email,
            username=username,
            role="user",
        )
    except Exception:
        pass

    # Auto-login new user and route to Neo UI (smoother UX for MVP demos).
    cookie_opts = _cookie_options(request)
    token = create_access_token(username, "user")
    target = next_url or "/ui/neo-dashboard"
    resp = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="access_token",
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        **cookie_opts,
    )
    return resp


def _cookie_secure_flag(request: Request) -> bool:
    explicit = os.getenv("COOKIE_SECURE")
    if explicit is not None:
        return explicit.strip().lower() in ("1", "true", "yes", "on")
    forwarded = (request.headers.get("x-forwarded-proto") or "").lower()
    return request.url.scheme == "https" or forwarded == "https"


def _cookie_options(request: Request) -> dict:
    secure_cookie = _cookie_secure_flag(request)
    samesite = (os.getenv("COOKIE_SAMESITE", "lax") or "lax").strip().lower()
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    domain = (os.getenv("COOKIE_DOMAIN") or "").strip() or None
    path = (os.getenv("COOKIE_PATH") or "/").strip() or "/"
    return {
        "httponly": True,
        "samesite": samesite,
        "secure": secure_cookie,
        "path": path,
        "domain": domain,
    }


@app.post("/auth/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db),
    next_url: str | None = Form(None),
):
    login_id = (username or "").strip()
    accepts_json = "application/json" in (request.headers.get("accept") or "")
    cookie_opts = _cookie_options(request)
    try:
        user = db.query(UserDB).filter(UserDB.username == login_id).first()
        if not user and "@" in login_id:
            user = db.query(UserDB).filter(UserDB.email == login_id).first()
    except (ProgrammingError, OperationalError):
        db.rollback()
        _ensure_users_table_and_admin(db)
        user = db.query(UserDB).filter(UserDB.username == login_id).first()
        if not user and "@" in login_id:
            user = db.query(UserDB).filter(UserDB.email == login_id).first()
    if not user or not verify_password(password, user.hashed_password):
        if accepts_json:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        params = {"error": "invalid"}
        if next_url:
            params["next"] = next_url
        return RedirectResponse(url=f"/login?{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER)
    token = create_access_token(user.username, user.role)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        **cookie_opts,
    )
    target = next_url or (
        "/ui/admin-hub"
        if user.role == "admin"
        else ("/ui/oem-dashboard" if user.role in ("oem", "tpa") else "/ui/neo-dashboard")
    )
    try:
        emailer_service.send_login_alert_email(to_email=user.email, username=user.username)
    except Exception:
        pass
    if accepts_json:
        response.status_code = status.HTTP_200_OK
        return {"access_token": token, "token_type": "bearer", "role": user.role, "redirect": target}
    resp = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="access_token",
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        **cookie_opts,
    )
    return resp


@app.get("/auth/login")
def login_redirect():
    return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.post("/auth/logout")
def logout(response: Response, request: Request):
    cookie_opts = _cookie_options(request)
    response.delete_cookie(
        "access_token",
        path=cookie_opts.get("path") or "/",
        domain=cookie_opts.get("domain"),
    )
    return {"status": "logged_out"}


@app.post("/auth/password/change", dependencies=[Depends(require_user)])
def change_password(payload: PasswordChangeRequest, db=Depends(get_db), current: UserDB = Depends(require_user)):
    if len(payload.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    user = db.query(UserDB).filter_by(username=current.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"status": "ok", "message": "Password updated"}


@app.get("/auth/session")
def auth_session(current: Optional[UserDB] = Depends(get_current_user_optional)):
    if not current:
        return {"authenticated": False, "username": None, "role": None}
    return {"authenticated": True, "username": current.username, "role": current.role}


@app.get("/login")
def login_form():
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "login.html"
    html = html_path.read_text(encoding="utf-8")
    verification = (os.getenv("GOOGLE_SITE_VERIFICATION") or "").strip()
    meta = ""
    if verification:
        meta = f'<meta name="google-site-verification" content="{escape(verification)}" />'
    html = html.replace("__GOOGLE_SITE_VERIFICATION_META__", meta)
    return HTMLResponse(content=html, status_code=200)


@app.get("/google{token}.html")
def google_site_verification_file(token: str):
    """
    Supports Google Search Console HTML-file verification.
    Set GOOGLE_SITE_VERIFICATION_FILE_TOKEN to the token part only (without "google" / ".html").
    """
    expected = (os.getenv("GOOGLE_SITE_VERIFICATION_FILE_TOKEN") or "").strip()
    if not expected or token != expected:
        raise HTTPException(status_code=404, detail="Not found")
    body = f"google-site-verification: google{expected}.html"
    return Response(content=body, media_type="text/plain; charset=utf-8")


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
    warranty_id: Optional[str] = Form(default=None),  # NEW: Optional existing warranty ID
    force_process: bool = Form(default=False),
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

    guardrail = {"decision": "clear", "message": None}
    if type == ArtifactType.invoice:
        guardrail = _invoice_guardrail(artifact.content)
    if guardrail.get("decision") == "needs_review" and not force_process:
        return {
            "artifact": artifact,
            "saved_path": str(dest),
            "status": "needs_review",
            "guardrail": guardrail,
        }
    
    # Use existing warranty if provided, otherwise create new one
    if warranty_id:
        warranty = store.get_warranty_db(warranty_id)
        if not warranty:
            # Create new if specified ID doesn't exist
            warranty = canonicalize_artifact(artifact, None)
    else:
        warranty = canonicalize_artifact(artifact, None)

    # Ownership link for per-user data isolation in the UI.
    # Use a separate DB session so it still succeeds even if the job pipeline transaction fails.
    try:
        with SessionLocal() as owner_db:
            owner_db.merge(WarrantyOwnerDB(user_id=current.username, warranty_id=warranty.id))
            owner_db.commit()
    except Exception:
        pass
    
    job = invoice_pipeline.create_job(
        db,
        warranty_id=warranty.id,
        artifact_id=artifact.id,
        source_path=str(dest),
    )
    
    # CRITICAL FIX: Always run the job, either async or sync
    job_error = None
    if background_tasks is not None:
        background_tasks.add_task(invoice_pipeline.run_job, job.id)
    else:
        # Fallback: Run synchronously if no background task runner
        try:
            invoice_pipeline.run_job(job.id)
        except Exception as e:
            job_error = str(e)
    
    try:
        run_initial_analysis_and_notifications(db, current.username, warranty.id)
    except Exception:
        pass
    try:
        emailer_service.send_product_registered_email(
            to_email=getattr(current, "email", None),
            username=current.username,
            warranty_id=warranty.id,
        )
    except Exception:
        pass
    return {
        "artifact": artifact,
        "warranty_id": warranty.id,
        "saved_path": str(dest),
        "job_id": job.id,
        "status": job.status,
        "job_error": job_error,
        "guardrail": guardrail if type == ArtifactType.invoice else None,
        "forced_process": bool(force_process),
    }


@app.get("/warranties/list", dependencies=[Depends(require_user)])
def list_warranties_sorted(
    user_id: str | None = None,
    db=Depends(get_db),
    current: UserDB = Depends(require_user),
):
    """List all warranties sorted by expiry date (soonest first)."""
    if current.role != "admin":
        uid = current.username
    else:
        uid = user_id or current.username

    query = db.query(WarrantyDB)
    if current.role != "admin":
        query = (
            query.join(WarrantyOwnerDB, WarrantyOwnerDB.warranty_id == WarrantyDB.id)
            .filter(WarrantyOwnerDB.user_id == uid)
        )
    # Sort by expiry_date ascending (soonest first), nulls last
    warranties = query.order_by(
        WarrantyDB.expiry_date.asc().nullslast()
    ).limit(100).all()

    latest_risk_by_warranty: Dict[str, Dict[str, object]] = {}
    unread_alert_count: Dict[str, int] = {}
    if uid:
        snaps = (
            db.query(RiskSnapshotDB)
            .filter_by(user_id=uid)
            .order_by(RiskSnapshotDB.created_at.desc())
            .all()
        )
        for snap in snaps:
            if snap.warranty_id and snap.warranty_id not in latest_risk_by_warranty:
                latest_risk_by_warranty[snap.warranty_id] = {
                    "risk_label": snap.risk_label,
                    "risk_score": float(snap.risk_score) if snap.risk_score is not None else None,
                }
        unread = (
            db.query(NotificationDB)
            .filter_by(user_id=uid, is_read=0)
            .all()
        )
        for n in unread:
            if n.warranty_id:
                unread_alert_count[n.warranty_id] = unread_alert_count.get(n.warranty_id, 0) + 1

    result = []
    for w in warranties:
        risk_meta = latest_risk_by_warranty.get(w.id, {})
        st = compute_warranty_status(
            purchase_date=w.purchase_date,
            coverage_months=w.coverage_months,
            expiry_date=w.expiry_date,
        )
        result.append({
            "id": w.id,
            "brand": w.brand,
            "product_name": w.product_name,
            "model_code": w.model_code,
            "serial_no": w.serial_no,
            "purchase_date": w.purchase_date.isoformat() if w.purchase_date else None,
            "expiry_date": w.expiry_date.isoformat() if w.expiry_date else None,
            "coverage_months": w.coverage_months,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "risk_label": risk_meta.get("risk_label"),
            "risk_score": risk_meta.get("risk_score"),
            "alert_count": unread_alert_count.get(w.id, 0),
            "warranty_status": st.get("status"),
            "claim_eligibility": st.get("claim_eligibility"),
            "days_left": st.get("days_left"),
            "lapsed_text": st.get("lapsed_text"),
        })
    return {"warranties": result, "count": len(result)}


@app.post("/warranties/from-artifact", dependencies=[Depends(rbac_dependency)])
def create_warranty(payload: CanonicalRequest, db=Depends(get_db), current=Depends(require_user)):
    artifact = store.artifacts.get(payload.artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    warranty = canonicalize_artifact(artifact, payload.overrides)
    # Auto terms lookup if duration is missing
    if not warranty.coverage_months:
        try:
            parsed = (
                db.query(ParsedFieldDB)
                .filter_by(warranty_id=warranty.id)
                .order_by(ParsedFieldDB.created_at.desc())
                .first()
            )
            result = terms_lookup.lookup_terms(
                db,
                brand=warranty.brand,
                category=getattr(parsed, "product_category", None) if parsed else None,
                region=getattr(warranty, "region_code", None),
                model_code=warranty.model_code,
                product_name=warranty.product_name,
            )
            wdb = db.query(WarrantyDB).filter_by(id=warranty.id).first()
            if wdb and result:
                if result.duration_months and not wdb.coverage_months:
                    wdb.coverage_months = result.duration_months
                if result.terms:
                    wdb.terms = result.terms
                if result.exclusions:
                    wdb.exclusions = result.exclusions
                if result.claim_steps:
                    wdb.claim_steps = result.claim_steps
                if wdb.purchase_date and wdb.coverage_months and not wdb.expiry_date:
                    exp = wdb.purchase_date.date()
                    year = exp.year + (exp.month - 1 + wdb.coverage_months) // 12
                    month = (exp.month - 1 + wdb.coverage_months) % 12 + 1
                    day = min(exp.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
                    wdb.expiry_date = datetime(year, month, day)
                db.add(wdb)
                db.commit()
                store.warranties.pop(warranty.id, None)
                warranty = store.get_warranty_db(warranty.id) or warranty
        except Exception:
            pass
    try:
        run_initial_analysis_and_notifications(db, current.username, warranty.id)
    except Exception:
        pass
    try:
        emailer_service.send_product_registered_email(
            to_email=getattr(current, "email", None),
            username=current.username,
            warranty_id=warranty.id,
        )
    except Exception:
        pass
    try:
        with SessionLocal() as owner_db:
            owner_db.merge(WarrantyOwnerDB(user_id=current.username, warranty_id=warranty.id))
            owner_db.commit()
    except Exception:
        pass
    return warranty

@app.get("/warranties/{warranty_id}", dependencies=[Depends(rbac_dependency)])
def get_warranty(warranty_id: str, db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=warranty_id)
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    payload = warranty.model_dump()
    payload.update(_build_warranty_status_info(warranty))
    return payload


@app.post("/warranties/{warranty_id}/process", dependencies=[Depends(rbac_dependency)])
def process_warranty(
    warranty_id: str,
    payload: ProcessWarrantyRequest | None = Body(default=None),
    db=Depends(get_db),
    background_tasks: BackgroundTasks = None,
    current: UserDB = Depends(require_user),
):
    _require_warranty_access(db, user=current, warranty_id=warranty_id)
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


@app.post("/warranty/terms/refresh", dependencies=[Depends(rbac_dependency)])
def refresh_warranty_terms(payload: TermsRefreshRequest, db=Depends(get_db)):
    warranty = db.query(WarrantyDB).filter_by(id=payload.warranty_id).first()
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    parsed = (
        db.query(ParsedFieldDB)
        .filter_by(warranty_id=payload.warranty_id)
        .order_by(ParsedFieldDB.created_at.desc())
        .first()
    )
    result = terms_lookup.lookup_terms(
        db,
        brand=warranty.brand,
        category=getattr(parsed, "product_category", None) if parsed else None,
        region=getattr(warranty, "region_code", None),
        model_code=warranty.model_code,
        product_name=warranty.product_name,
        url_override=payload.url_override,
        force_refresh=payload.force,
    )
    if result.duration_months and not warranty.coverage_months:
        warranty.coverage_months = result.duration_months
    if result.terms:
        warranty.terms = result.terms
    if result.exclusions:
        warranty.exclusions = result.exclusions
    if result.claim_steps:
        warranty.claim_steps = result.claim_steps
    # Persist terms source hints for UI transparency.
    alt = dict(getattr(warranty, "alternatives", None) or {})
    src = result.source_url or ""
    src_type = "internal"
    if src.startswith(("http://", "https://")):
        src_type = "scraped"
    elif src.endswith("default_rules"):
        src_type = "default_rules"
    elif src.endswith("warranty_db"):
        src_type = "internal_warranty_db"
    elif src.endswith("terms_cache"):
        src_type = "internal_terms_cache"
    alt["terms_source_url"] = src or None
    alt["terms_source_type"] = src_type
    alt["terms_last_refreshed_at"] = datetime.utcnow().isoformat()
    warranty.alternatives = alt
    if warranty.purchase_date and warranty.coverage_months and not warranty.expiry_date:
        exp = warranty.purchase_date.date()
        year = exp.year + (exp.month - 1 + warranty.coverage_months) // 12
        month = (exp.month - 1 + warranty.coverage_months) % 12 + 1
        day = min(exp.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        warranty.expiry_date = datetime(year, month, day)
    db.add(warranty)
    db.commit()
    store.warranties.pop(warranty.id, None)
    summary_text, source = summary_engine.summarize_warranty(store.get_warranty_db(warranty.id) or warranty)
    structured = summary_engine.build_structured_summary(store.get_warranty_db(warranty.id) or warranty)
    db.add(
        WarrantySummaryDB(
            warranty_id=warranty.id,
            summary_text=summary_text,
            source=source,
            summary_points=structured.get("points"),
            summary_tags=structured.get("tags"),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    try:
        from .services.rag import upsert_document, rag_enabled
        if rag_enabled():
            upsert_document(
                db,
                doc_type="warranty_summary",
                doc_id=warranty.id,
                content=summary_text,
                metadata={"brand": warranty.brand, "model_code": warranty.model_code, "region": warranty.region_code},
            )
    except Exception:
        pass
    return {"status": "ok", "warranty_id": warranty.id, "source_url": result.source_url}


@app.get("/warranties/{warranty_id}/summary", dependencies=[Depends(rbac_dependency)])
def get_warranty_summary(warranty_id: str, db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=warranty_id)
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    parsed = (
        db.query(ParsedFieldDB)
        .filter_by(warranty_id=warranty_id)
        .order_by(ParsedFieldDB.created_at.desc())
        .first()
    )
    latest_job = (
        db.query(PipelineJobDB)
        .filter_by(warranty_id=warranty_id)
        .order_by(PipelineJobDB.updated_at.desc())
        .first()
    )
    parsed_fields = None
    if parsed:
        parsed_fields = {
            "brand": parsed.brand,
            "model_code": parsed.model_code,
            "product_name": parsed.product_name,
            "product_category": parsed.product_category,
            "serial_no": parsed.serial_no,
            "invoice_no": parsed.invoice_no,
            "purchase_date": parsed.purchase_date.isoformat() if parsed.purchase_date else None,
        }
    evidence = {
        "source_artifact_ids": getattr(warranty, "source_artifact_ids", None) or [],
    }
    terms_source_url = ((getattr(warranty, "alternatives", None) or {}).get("terms_source_url"))
    terms_source_type = ((getattr(warranty, "alternatives", None) or {}).get("terms_source_type"))
    status_info = _build_warranty_status_info(warranty)
    layman = summary_engine.build_layman_summary(warranty)
    summary_row = invoice_pipeline.get_latest_summary(db, warranty_id)
    if summary_row:
        return {
            "warranty_id": warranty_id,
            "summary": summary_row.summary_text,
            "source": summary_row.source,
            "summary_points": summary_row.summary_points or [],
            "summary_tags": summary_row.summary_tags or [],
            "parsed_fields": parsed_fields,
            "confidence": parsed.confidence if parsed else {},
            "terms": warranty.terms or [],
            "exclusions": warranty.exclusions or [],
            "claim_steps": warranty.claim_steps or [],
            "layman_summary": layman,
            "evidence": evidence,
            "processing_status": latest_job.status if latest_job else None,
            "terms_source_url": terms_source_url,
            "terms_source_type": terms_source_type,
            "warranty_status_info": status_info,
        }
    summary_text, source = summary_engine.summarize_warranty(warranty)
    structured = summary_engine.build_structured_summary(warranty)
    return {
        "warranty_id": warranty_id,
        "summary": summary_text,
        "source": source,
        "summary_points": structured.get("points"),
        "summary_tags": structured.get("tags"),
        "parsed_fields": parsed_fields,
        "confidence": parsed.confidence if parsed else {},
        "terms": warranty.terms or [],
        "exclusions": warranty.exclusions or [],
        "claim_steps": warranty.claim_steps or [],
        "layman_summary": layman,
        "evidence": evidence,
        "processing_status": latest_job.status if latest_job else None,
        "terms_source_url": terms_source_url,
        "terms_source_type": terms_source_type,
        "warranty_status_info": status_info,
    }


@app.post("/behaviour-events", dependencies=[Depends(rbac_dependency)])
def push_behaviour_event(payload: BehaviourEventRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    _require_consent(payload.user_id)
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
    status_info = _build_warranty_status_info(warranty)
    variant = policy.assign_variant(user_id, warranty_id, experiment="fogg_nudge", variants=("A", "B"))
    nudges = generate_nudges(risk, variant)
    band_map = {"high": "critical", "medium": "warning", "low": "info"}
    severity = band_map.get(getattr(risk, "band", "low"), "info")
    if status_info.get("warranty_status") == "expired":
        severity = "critical"
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
        "warranty_status_info": status_info,
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
    try:
        emailer_service.send_product_registered_email(
            to_email=getattr(current, "email", None),
            username=current.username,
            warranty_id=warranty.id,
        )
    except Exception:
        pass
    return {"artifact": artifact, "warranty_id": warranty.id, "saved_path": str(dest), "job_id": job.id}


@app.get("/ui/warranty/{warranty_id}")
def warranty_ui(
    request: Request,
    warranty_id: str,
    user_id: str,
    current: Optional[UserDB] = Depends(get_current_user_optional),
):
    ui_redirect = _ensure_ui_user(request, current)
    if ui_redirect:
        return ui_redirect
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


@app.get("/ui/scheduler")
def scheduler_ui(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_user(request, current)
    if ui_redirect:
        return ui_redirect
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


@app.get("/ui/react-dashboard")
def react_dashboard(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_user(request, current)
    if ui_redirect:
        return ui_redirect
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "react_dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/console")
def console_ui(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_user(request, current)
    if ui_redirect:
        return ui_redirect
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "console.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/admin-hub")
def admin_hub_ui(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_oem_or_admin(request, current)
    if ui_redirect:
        return ui_redirect
    if not current or current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    from fastapi.responses import HTMLResponse

    html_path = Path(__file__).resolve().parents[1] / "templates" / "admin_hub.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("__SWH_CURRENT_USER__", escape(current.username))
    html = html.replace("__SWH_CURRENT_ROLE__", escape(current.role))
    return HTMLResponse(content=html, status_code=200)


@app.get("/ui/neo-dashboard")
def neo_dashboard(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_user(request, current)
    if ui_redirect:
        return ui_redirect
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "neo_dashboard.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("__SWH_CURRENT_USER__", escape(current.username if current else ""))
    html = html.replace("__SWH_CURRENT_ROLE__", escape(current.role if current else ""))
    return HTMLResponse(content=html, status_code=200)



@app.get("/ui/warranty-tabs")
def warranty_tabs_ui():
    """Multi-invoice tabbed dashboard with Details/Predictive/OEM/Nudges tabs."""
    from fastapi.responses import HTMLResponse
    html_path = Path(__file__).resolve().parents[1] / "templates" / "warranty_tabs.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/ui/oem-dashboard")
def oem_dashboard(request: Request, current: Optional[UserDB] = Depends(get_current_user_optional)):
    ui_redirect = _ensure_ui_oem_or_admin(request, current)
    if ui_redirect:
        return ui_redirect
    from fastapi.responses import HTMLResponse

    html_path = Path(__file__).resolve().parents[1] / "templates" / "oem_dashboard.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace("__SWH_CURRENT_USER__", escape(current.username if current else ""))
    html = html.replace("__SWH_CURRENT_ROLE__", escape(current.role if current else ""))
    return HTMLResponse(content=html, status_code=200)


@app.post("/telemetry", dependencies=[Depends(rbac_dependency)])
def push_telemetry(payload: TelemetryRequest):
    if payload.warranty_id not in store.warranties:
        raise HTTPException(status_code=404, detail="Warranty not found")
    _require_consent(payload.user_id)
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


@app.post("/consent", dependencies=[Depends(require_user)])
def update_consent(payload: ConsentRequest, current=Depends(require_user)):
    if current.username != payload.user_id and current.role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    with SessionLocal() as db:
        user = db.query(UserDB).filter_by(username=payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")
        user.consent_analytics = 1 if payload.consent_analytics else 0
        db.add(user)
        db.commit()
    return {"ok": True, "user_id": payload.user_id, "consent_analytics": payload.consent_analytics}


@app.get("/diagnostics/capability/{warranty_id}", dependencies=[Depends(require_user)])
def diagnostics_capability(warranty_id: str, db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=warranty_id)
    w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="warranty_not_found")
    data = diag_cap_service.infer_capability(
        product_name=w.product_name,
        brand=w.brand,
        model_code=w.model_code,
        alternatives=getattr(w, "alternatives", None) or {},
    )
    return {"ok": True, "warranty_id": warranty_id, **data}


@app.post("/diagnostics/request-remote-check", dependencies=[Depends(require_user)])
def diagnostics_request_remote_check(payload: RemoteAssistRequest, db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=payload.warranty_id)
    w = db.query(WarrantyDB).filter_by(id=payload.warranty_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="warranty_not_found")
    cap = diag_cap_service.infer_capability(
        product_name=w.product_name,
        brand=w.brand,
        model_code=w.model_code,
        alternatives=getattr(w, "alternatives", None) or {},
    )
    if not cap.get("is_iot"):
        return {
            "ok": False,
            "detail": "non_iot_product",
            "message": "This product appears non-IoT. Use guided diagnostics.",
        }
    try:
        sess = remote_diag_service.create_session(
            db,
            user_id=current.username,
            warranty_id=payload.warranty_id,
            requested_by=current.username,
            connector_name=None,
            device_id=None,
            context={"source": "neo_dashboard_user_request"},
        )
        cmd = remote_diag_service.request_command(
            db,
            session_id=sess.id,
            command_type=(payload.command_type or "health_check"),
            command_payload={"source": "user_request", "note": "Customer requested remote check"},
            requested_by=current.username,
            require_review=True,
            review_reason="User requested remote diagnostics from dashboard",
            connector_name=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "session_id": sess.id,
        "command_id": cmd.id,
        "status": cmd.status,
        "message": "Remote check requested. OEM team will review and run diagnostics shortly.",
    }


@app.get("/oem/domains/verified", dependencies=[Depends(require_oem_or_admin)])
def list_verified_domains():
    return {"ok": True, "verified": load_verified_domains()}


@app.post("/oem/domains/verified", dependencies=[Depends(require_oem_or_admin)])
def add_verified_domain(payload: OemVerifyRequest):
    data = load_verified_domains()
    brand = payload.brand.strip()
    domain = payload.domain.strip().lower()
    if not brand or not domain:
        raise HTTPException(status_code=400, detail="missing_brand_or_domain")
    arr = data.get(brand, [])
    if domain not in arr:
        arr.append(domain)
    data[brand] = arr
    save_verified_domains(data)
    return {"ok": True, "verified": data.get(brand, [])}


@app.post("/oem/domains/verify", dependencies=[Depends(require_oem_or_admin)])
def verify_domain(payload: OemVerifyRequest):
    return verify_or_suggest(brand=payload.brand, domain=payload.domain, region=payload.region)


@app.post("/predictive/score", dependencies=[Depends(rbac_dependency)])
def predictive_score(payload: PredictiveRequest, db=Depends(get_db)):
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
        warranty = db.query(WarrantyDB).filter(WarrantyDB.id == payload.warranty_id).first()
        if warranty:
            notification_service.create_expiry_notifications(
                db=db,
                user_id=payload.user_id,
                warranty_id=payload.warranty_id,
                warranty=warranty,
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

    model_config = {"from_attributes": True}


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


@app.post("/oem/communications/send", dependencies=[Depends(require_oem_or_admin)])
def oem_send_communication(
    payload: OemCommunicationSendRequest,
    db=Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    result = oem_communication_service.send_oem_message(
        db,
        sender_user_id=current.username,
        sender_role=current.role,
        recipient_user_id=payload.recipient_user_id,
        kind=payload.kind,
        title=payload.title,
        message=payload.message,
        channel=payload.channel,
        warranty_id=payload.warranty_id,
        brand=payload.brand,
        model_code=payload.model_code,
        product_type=payload.product_type,
        region=payload.region,
        send_if_ineligible=payload.send_if_ineligible,
        metadata=payload.metadata,
    )
    return result


@app.get("/oem/communications/traces", dependencies=[Depends(require_oem_or_admin)])
def oem_list_communication_traces(
    recipient_user_id: str | None = None,
    warranty_id: str | None = None,
    decision: str | None = None,
    limit: int = 100,
    db=Depends(get_db),
):
    return oem_communication_service.list_traces(
        db,
        recipient_user_id=recipient_user_id,
        warranty_id=warranty_id,
        decision=decision,
        limit=limit,
    )


@app.get("/admin/oem-dispatch/policy", dependencies=[Depends(require_admin)])
def admin_get_oem_dispatch_policy():
    return oem_dispatch_service.get_dispatch_policy()


@app.post("/admin/oem-dispatch/policy", dependencies=[Depends(require_admin)])
def admin_set_oem_dispatch_policy(payload: Dict = Body(...)):
    return oem_dispatch_service.set_dispatch_policy(payload or {})


@app.post("/admin/oem-dispatch/run", dependencies=[Depends(require_admin)])
def admin_run_oem_dispatch(payload: OemDispatchRunRequest, db=Depends(get_db)):
    return oem_dispatch_service.run_weekly_dispatch(db, dry_run=bool(payload.dry_run))


@app.get("/admin/kpi-watchdog/policy", dependencies=[Depends(require_admin)])
def admin_get_kpi_watchdog_policy():
    return kpi_watchdog_service.get_watchdog_policy()


@app.post("/admin/kpi-watchdog/policy", dependencies=[Depends(require_admin)])
def admin_set_kpi_watchdog_policy(payload: Dict = Body(...)):
    return kpi_watchdog_service.set_watchdog_policy(payload or {})


@app.get("/admin/kpi/report", dependencies=[Depends(require_admin)])
def admin_get_kpi_report(report_file: str | None = None):
    report = kpi_watchdog_service.load_kpi_report(report_file=report_file)
    health = kpi_watchdog_service.evaluate_kpi_health(report)
    return {"report": report, "health": health}


@app.post("/admin/kpi/watchdog/run", dependencies=[Depends(require_admin)])
def admin_run_kpi_watchdog(payload: KpiWatchdogRunRequest, db=Depends(get_db)):
    return kpi_watchdog_service.run_kpi_watchdog(
        db,
        report_file=payload.report_file,
        notify=bool(payload.notify),
    )


@app.post("/admin/rag/smoke", dependencies=[Depends(require_admin)])
def admin_rag_smoke(db=Depends(get_db)):
    return rag_service.smoke_test(db)


@app.get("/admin/kpi/history", dependencies=[Depends(require_admin)])
def admin_get_kpi_history(limit: int = 30):
    return {"history": kpi_remediation_service.get_history(limit=max(1, min(365, int(limit or 30))))}


@app.get("/admin/kpi/remediation/latest", dependencies=[Depends(require_admin)])
def admin_get_kpi_remediation_latest():
    return kpi_remediation_service.load_latest_plan()


@app.post("/admin/kpi/remediation/run", dependencies=[Depends(require_admin)])
def admin_run_kpi_remediation(payload: KpiRemediationRunRequest, db=Depends(get_db)):
    return kpi_remediation_service.run_kpi_remediation_cycle(
        db,
        report_file=payload.report_file,
        notify=bool(payload.notify),
        source=payload.source or "manual",
    )


@app.get("/admin/kpi/tasks", dependencies=[Depends(require_admin)])
def admin_list_kpi_tasks(status: str | None = None, limit: int = 200):
    return {
        "tasks": kpi_execution_service.list_tasks(status=status, limit=max(1, min(1000, int(limit or 200))))
    }


@app.post("/admin/kpi/tasks/{task_key}", dependencies=[Depends(require_admin)])
def admin_update_kpi_task(task_key: str, payload: KpiTaskUpdateRequest):
    return kpi_execution_service.update_task_status(
        task_key=task_key,
        status=payload.status,
        notes=payload.notes,
        owner=payload.owner,
    )


@app.get("/admin/kpi/execution/metrics", dependencies=[Depends(require_admin)])
def admin_kpi_execution_metrics():
    return kpi_execution_service.execution_metrics()


@app.post("/admin/kpi/execution/run", dependencies=[Depends(require_admin)])
def admin_kpi_execution_run(db=Depends(get_db)):
    return kpi_execution_service.run_execution_cycle(db, notify=True, source="manual")


@app.post("/region-rules", dependencies=[Depends(require_admin)])
def upsert_region_rule(payload: RegionRuleRequest, db=Depends(get_db)):
    rec = regional_policy_service.upsert_region_policy(
        db,
        region=payload.region,
        rule_json=payload.rule_json,
        brand=payload.brand,
        model_code=payload.model_code,
        product_type=payload.product_type,
        active=payload.active,
    )
    return {"id": rec.id, "region": rec.region, "active": bool(rec.active)}


@app.get("/region-rules", dependencies=[Depends(require_admin)])
def list_region_rules(region: str | None = None, db=Depends(get_db)):
    q = db.query(RegionalPolicyDB)
    if region:
        q = q.filter_by(region=region)
    items = q.order_by(RegionalPolicyDB.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "region": r.region,
            "brand": r.brand,
            "model_code": r.model_code,
            "product_type": r.product_type,
            "rule_json": r.rule_json,
            "active": bool(r.active),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in items
    ]


@app.post("/oem/issues", dependencies=[Depends(require_oem_or_admin)])
def record_oem_issue(payload: OemIssueSignalRequest, db=Depends(get_db)):
    rec = oem_issue_service.record_issue_signal(
        db,
        brand=payload.brand,
        model_code=payload.model_code,
        product_type=payload.product_type,
        region=payload.region,
        issue_type=payload.issue_type,
        severity=payload.severity,
        count=payload.count,
        source_url=payload.source_url,
    )
    return {"id": rec.id}


@app.get("/oem/issues/summary", dependencies=[Depends(require_oem_or_admin)])
def oem_issue_summary(
    brand: str | None = None,
    model_code: str | None = None,
    product_type: str | None = None,
    region: str | None = None,
    db=Depends(get_db),
):
    res = oem_issue_service.summarize_issue_signals(
        db,
        brand=brand,
        model_code=model_code,
        product_type=product_type,
        region=region,
    )
    return {"risk_delta": res.risk_delta, "reasons": res.reasons}


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
        name = (w.product_name or "").lower() if w else ""
        pt_lower = p.product_type.lower() if getattr(p, "product_type", None) else ""
        if "ev" in name or ("ev" in pt_lower):
            ev_payload = {
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
            try:
                latest_ev = (
                    db.query(EVTelemetryDB)
                    .filter_by(warranty_id=p.warranty_id)
                    .order_by(EVTelemetryDB.created_at.desc())
                    .first()
                )
                if latest_ev:
                    ev_payload.update(
                        {
                            "daily_km": float(latest_ev.daily_km or ev_payload["daily_km"]),
                            "fast_charge_sessions": int(latest_ev.fast_charge_sessions or ev_payload["fast_charge_sessions"]),
                            "deep_discharge_events": int(latest_ev.deep_discharge_events or ev_payload["deep_discharge_events"]),
                            "max_temp_seen": float(latest_ev.max_temp_seen or ev_payload["max_temp_seen"]),
                            "region_climate_band": int(latest_ev.region_climate_band or ev_payload["region_climate_band"]),
                        }
                    )
            except Exception:
                pass
            ev_score = ev_battery_service.score_ev_battery(
                ev_payload
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


@app.get("/oem/forecast", dependencies=[Depends(require_oem_or_admin)])
def oem_forecast(
    brand: str | None = None,
    model: str | None = None,
    product_type: str | None = None,
    region: str | None = None,
    weeks: int = 12,
    horizon_weeks: int = 4,
    current=Depends(require_oem_or_admin),
    db=Depends(get_db),
):
    """
    Lightweight OEM forecast endpoint.
    Additive only: uses existing risk snapshots and issue signals.
    """
    weeks = max(4, min(52, int(weeks or 12)))
    horizon_weeks = max(1, min(12, int(horizon_weeks or 4)))
    now = datetime.utcnow()
    start = now - timedelta(days=weeks * 7)

    warranty_q = db.query(WarrantyDB.id)
    if brand:
        warranty_q = warranty_q.filter(WarrantyDB.brand == brand)
    if model:
        warranty_q = warranty_q.filter(WarrantyDB.model_code == model)
    if region:
        warranty_q = warranty_q.filter(WarrantyDB.region_code == region)
    if product_type:
        warranty_q = warranty_q.filter(WarrantyDB.product_name.ilike(f"%{product_type}%"))
    warranty_ids = [row[0] for row in warranty_q.all()]
    if not warranty_ids:
        return {
            "ok": True,
            "history": [],
            "forecast": [],
            "insights": ["No matching warranty data for this filter yet."],
            "confidence": "low",
        }

    snaps = (
        db.query(RiskSnapshotDB)
        .filter(RiskSnapshotDB.warranty_id.in_(warranty_ids), RiskSnapshotDB.created_at >= start)
        .all()
    )

    def _week_start(dt: datetime) -> datetime:
        base = dt - timedelta(days=dt.weekday())
        return base.replace(hour=0, minute=0, second=0, microsecond=0)

    current_week = _week_start(now)
    week_points = [current_week - timedelta(days=7 * i) for i in reversed(range(weeks))]
    by_week: Dict[str, Dict[str, int]] = {
        p.date().isoformat(): {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
        for p in week_points
    }

    for s in snaps:
        key = _week_start(s.created_at).date().isoformat()
        if key not in by_week:
            continue
        label = (s.risk_label or "UNKNOWN").upper()
        if label not in by_week[key]:
            label = "UNKNOWN"
        by_week[key][label] += 1

    history = []
    for p in week_points:
        key = p.date().isoformat()
        c = by_week[key]
        history.append(
            {
                "week_start": key,
                "low": c["LOW"],
                "medium": c["MEDIUM"],
                "high": c["HIGH"],
                "unknown": c["UNKNOWN"],
                "total": c["LOW"] + c["MEDIUM"] + c["HIGH"] + c["UNKNOWN"],
            }
        )

    def _forecast(series: List[int], n: int) -> List[int]:
        if not series:
            return [0] * n
        if len(series) == 1:
            return [max(0, int(round(series[0])))] * n
        slope = (series[-1] - series[0]) / max(1, (len(series) - 1))
        last = series[-1]
        out = []
        for i in range(1, n + 1):
            out.append(max(0, int(round(last + slope * i))))
        return out

    low_series = [h["low"] for h in history]
    med_series = [h["medium"] for h in history]
    high_series = [h["high"] for h in history]

    f_low = _forecast(low_series, horizon_weeks)
    f_med = _forecast(med_series, horizon_weeks)
    f_high = _forecast(high_series, horizon_weeks)

    forecast = []
    for i in range(horizon_weeks):
        wk = (current_week + timedelta(days=7 * (i + 1))).date().isoformat()
        failure_pressure = f_high[i] + max(0, round(f_med[i] * 0.6))
        forecast.append(
            {
                "week_start": wk,
                "low": f_low[i],
                "medium": f_med[i],
                "high": f_high[i],
                "failure_pressure": int(failure_pressure),
            }
        )

    issue_q = db.query(OemIssueSignalDB)
    if brand:
        issue_q = issue_q.filter(OemIssueSignalDB.brand == brand)
    if model:
        issue_q = issue_q.filter(OemIssueSignalDB.model_code == model)
    if region:
        issue_q = issue_q.filter(OemIssueSignalDB.region == region)
    issue_rows = issue_q.filter(OemIssueSignalDB.created_at >= start).all()
    issue_load = sum(int(r.count or 0) for r in issue_rows)

    trend = "stable"
    if len(high_series) >= 2:
        if high_series[-1] > high_series[0]:
            trend = "rising"
        elif high_series[-1] < high_series[0]:
            trend = "falling"

    avg_future_pressure = (sum(x["failure_pressure"] for x in forecast) / len(forecast)) if forecast else 0.0
    insights = [
        f"High-risk trend is {trend}.",
        f"Estimated average failure pressure for next {horizon_weeks} weeks: {avg_future_pressure:.1f}.",
        f"Recent OEM issue volume in selected window: {issue_load}.",
    ]
    if avg_future_pressure >= 8:
        insights.append("Recommend proactive spares/service slot planning for this model segment.")
    elif avg_future_pressure >= 3:
        insights.append("Recommend moderate readiness: monitor parts and service capacity weekly.")
    else:
        insights.append("Current projected pressure is low; continue weekly monitoring.")

    confidence = "high" if len(history) >= 12 else ("medium" if len(history) >= 8 else "low")
    return {
        "ok": True,
        "history": history,
        "forecast": forecast,
        "insights": insights,
        "confidence": confidence,
    }


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
def warranty_summary(payload: SummaryRequest, db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=payload.warranty_id)
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
    source = "llm"
    if err or not text:
        source = "template"
        lines = [
            f"Brand: {warranty.brand or 'N/A'} Model: {warranty.model_code or 'N/A'}",
            f"Expiry: {warranty.expiry_date or 'N/A'} Coverage months: {warranty.coverage_months or 'N/A'}",
            "Terms: " + "; ".join(warranty.terms),
            "Exclusions: " + "; ".join(warranty.exclusions),
            "Claim steps: " + "; ".join(warranty.claim_steps),
        ]
        text = "\n".join(lines)
    structured = summary_engine.build_structured_summary(warranty)
    layman = summary_engine.build_layman_summary(warranty)
    terms_source_url = ((getattr(warranty, "alternatives", None) or {}).get("terms_source_url"))
    terms_source_type = ((getattr(warranty, "alternatives", None) or {}).get("terms_source_type"))
    log_action("warranty_summary", f"warranty_id={payload.warranty_id} prompt_len={len(prompt)}")
    return {
        "summary": text,
        "source": source,
        "summary_points": structured.get("points", []),
        "summary_tags": structured.get("tags", []),
        "layman_summary": layman,
        "terms_source_url": terms_source_url,
        "terms_source_type": terms_source_type,
    }


@app.get("/warranties/{warranty_id}/export", dependencies=[Depends(rbac_dependency)])
def warranty_export(warranty_id: str, format: str = "txt", db=Depends(get_db), current: UserDB = Depends(require_user)):
    _require_warranty_access(db, user=current, warranty_id=warranty_id)
    warranty = store.get_warranty_db(warranty_id)
    if not warranty:
        raise HTTPException(status_code=404, detail="Warranty not found")
    summary = warranty_summary(SummaryRequest(warranty_id=warranty_id), db=db, current=current).get("summary", "")
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


@app.post("/reviews/crawl", dependencies=[Depends(require_admin)])
def reviews_crawl(region: str | None = None):
    with SessionLocal() as db:
        stats = crawl_reviews(db, region=region or os.getenv("REVIEW_REGION", "IN"))
        return {"ok": True, "stats": stats}


@app.get("/reviews/stats", dependencies=[Depends(require_admin)])
def reviews_stats(brand: str | None = None, model: str | None = None, region: str | None = None):
    with SessionLocal() as db:
        q = db.query(ProductReviewDB)
        if brand:
            q = q.filter_by(brand=brand)
        if model:
            q = q.filter_by(model_code=model)
        if region:
            q = q.filter_by(region=region)
        rows = q.all()
        pages = db.query(ReviewPageDB).count()
        count = len(rows)
        avg_rating = float(sum(r.rating or 0.0 for r in rows) / count) if count else None
        avg_sent = float(sum(r.sentiment or 0.0 for r in rows) / count) if count else None
        return {
            "ok": True,
            "pages": pages,
            "reviews": count,
            "avg_rating": avg_rating,
            "avg_sentiment": avg_sent,
        }


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
