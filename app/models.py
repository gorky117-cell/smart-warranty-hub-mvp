from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    invoice = "invoice"
    manual = "manual"
    label = "label"
    portal = "portal"
    other = "other"


class Artifact(BaseModel):
    id: str
    type: ArtifactType
    content: str
    source: Optional[str] = None
    received_at: datetime = Field(default_factory=datetime.utcnow)


class CanonicalWarranty(BaseModel):
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
    alternatives: Dict[str, List[str]] = Field(default_factory=dict)
    source_artifact_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BehaviourEvent(BaseModel):
    user_id: str
    warranty_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)


class RiskScore(BaseModel):
    warranty_id: str
    user_id: str
    value: float
    band: str
    contributors: Dict[str, float] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Nudge(BaseModel):
    id: str
    warranty_id: str
    user_id: str
    title: str
    message: str
    reason: str
    suggested_actions: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=lambda: ["in-app"])


class ServiceTicket(BaseModel):
    id: str
    warranty_id: str
    user_id: str
    symptom: str
    evidence: List[str] = Field(default_factory=list)
    recommended_parts: List[str] = Field(default_factory=list)
    status: str = "draft"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TelemetryEvent(BaseModel):
    id: str
    warranty_id: str
    user_id: str
    model_code: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    event_type: str  # e.g., usage, error, maintenance, failure
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PredictiveScore(BaseModel):
    warranty_id: str
    user_id: str
    model_code: Optional[str]
    region: Optional[str]
    score: float
    band: str
    reasons: List[str] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)


class ReviewItem(BaseModel):
    id: str
    action: str  # e.g., oem_fetch, device_actuation, claim_submit
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending | approved | rejected
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
