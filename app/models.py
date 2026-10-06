from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AppBaseModel(BaseModel):
    # Allow fields like model_code without protected namespace warnings
    model_config = {"protected_namespaces": ()}


class ArtifactType(str, Enum):
    invoice = "invoice"
    manual = "manual"
    label = "label"
    portal = "portal"
    other = "other"


class Artifact(AppBaseModel):
    id: str
    type: ArtifactType
    content: str
    source: Optional[str] = None
    received_at: datetime = Field(default_factory=datetime.utcnow)
    # Which extractor produced `content` (method/engine/paddle_failed); in memory only, not persisted.
    ocr_meta: Optional[Dict[str, Any]] = None


class CanonicalWarranty(AppBaseModel):
    id: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    model_code: Optional[str] = None
    serial_no: Optional[str] = None
    purchase_date: Optional[date] = None
    coverage_months: Optional[int] = None
    expiry_date: Optional[date] = None
    terms: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    claim_steps: List[str] = Field(default_factory=list)
    confidence: Dict[str, float] = Field(default_factory=dict)
    alternatives: Dict[str, Any] = Field(default_factory=dict)
    source_artifact_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BehaviourEvent(AppBaseModel):
    user_id: str
    warranty_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)


class RiskScore(AppBaseModel):
    warranty_id: str
    user_id: str
    value: float
    band: str
    contributors: Dict[str, float] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    # "predictive" (ML scorer) or "heuristic_fallback" (fix run B9: one scorer for every endpoint)
    source: str = "heuristic"
    reasons: List[str] = Field(default_factory=list)


class Nudge(AppBaseModel):
    id: str
    warranty_id: str
    user_id: str
    title: str
    message: str
    reason: str
    suggested_actions: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=lambda: ["in-app"])


class ServiceTicket(AppBaseModel):
    id: str
    warranty_id: str
    user_id: str
    symptom: str
    evidence: List[str] = Field(default_factory=list)
    recommended_parts: List[str] = Field(default_factory=list)
    status: str = "draft"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TelemetryEvent(AppBaseModel):
    id: str
    warranty_id: str
    user_id: str
    model_code: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    event_type: str  # e.g., usage, error, maintenance, failure
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PredictiveScore(AppBaseModel):
    warranty_id: str
    user_id: str
    model_code: Optional[str]
    region: Optional[str]
    score: float
    band: str
    reasons: List[str] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)



class ReviewItem(AppBaseModel):
    id: str
    action: str  # e.g., oem_fetch, device_actuation, claim_submit
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending | approved | rejected
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class TermsResult(AppBaseModel):
    duration_months: Optional[int] = None
    terms: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    claim_steps: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    # Sentence (and source) the selected duration came from; extended/optional plan statements kept apart.
    duration_evidence: Optional[str] = None
    optional_plan_terms: List[str] = Field(default_factory=list)
    # Parser duration statements for product-scoped selection; internal, not serialised.
    duration_candidates: List[Dict[str, Any]] = Field(default_factory=list, exclude=True)
    # Cache fixes 4-5: parser confidence; whether the duration was traced to a sentence on the page;
    # when the source was last checked; and whether that check is older than the freshness window.
    confidence: Optional[float] = None
    grounded: Optional[bool] = None
    checked_at: Optional[str] = None
    needs_refresh: bool = False
    # "knowledge_base" when the terms are a hand-checked entry (knowledge base v1).
    source_kind: Optional[str] = None
    # Optional secondary citation an admin added to a knowledge-base entry (Right to Repair portal page).
    also_listed_url: Optional[str] = None
