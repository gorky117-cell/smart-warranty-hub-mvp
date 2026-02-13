from datetime import datetime
from typing import Optional
import os

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint, ForeignKey, JSON
from sqlalchemy.dialects.sqlite import JSON as SqliteJSON
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    role: Mapped[str] = mapped_column(String, default="user", index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    consent_analytics: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TelemetryEventDB(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload = Column(SqliteJSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EVTelemetryDB(Base):
    __tablename__ = "ev_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    daily_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fast_charge_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deep_discharge_events: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_temp_seen: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    region_climate_band: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ReviewDB(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String, index=True)
    payload = Column(SqliteJSON)
    status: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PolicyAssignmentDB(Base):
    __tablename__ = "policy_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str] = mapped_column(String)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String, index=True)
    detail = Column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BehaviourQuestion(Base):
    __tablename__ = "behaviour_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(String)
    answer_type: Mapped[str] = mapped_column(String)  # choice | scale_1_5
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Integer, default=1)
    # Optional scoping hints
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)


class BehaviourAnswer(Base):
    __tablename__ = "behaviour_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("behaviour_questions.id"), index=True)
    answer_value: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class BehaviourProfile(Base):
    __tablename__ = "behaviour_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    behaviour_score: Mapped[float] = mapped_column(Float, default=0.5)
    care_score: Mapped[float] = mapped_column(Float, default=0.5)
    responsiveness_score: Mapped[float] = mapped_column(Float, default=0.5)
    last_question_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    aqi_band: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0 good, 1 moderate, 2 poor, 3 very poor


class NudgeEvents(Base):
    __tablename__ = "nudge_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    nudge_type: Mapped[str] = mapped_column(String)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # acted | ignored | dismissed
    variant: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    shown_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ignored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RecommendationRule(Base):
    __tablename__ = "recommendation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment: Mapped[str] = mapped_column(String, index=True)
    condition_json = Column(SqliteJSON)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=10, index=True)
    active: Mapped[bool] = mapped_column(Integer, default=1, index=True)


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recommendation_rules.id"), nullable=True, index=True)
    shown_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    clicked: Mapped[bool] = mapped_column(Integer, default=0)
    dismissed: Mapped[bool] = mapped_column(Integer, default=0)


class PeerReviewSignals(Base):
    __tablename__ = "peer_review_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    avg_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_sentiment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failure_keywords = Column(SqliteJSON)
    symptom_keyword: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    severity_hint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SymptomSearch(Base):
    __tablename__ = "symptom_search"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    matched_component: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OEMFetchDB(Base):
    __tablename__ = "oem_fetch_queue"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    brand: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)  # pending | fetched | failed
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArtifactDB(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class WarrantyDB(Base):
    __tablename__ = "warranties"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    coverage_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    climate_zone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    oem_risk_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brand_reliability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    behaviour_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    care_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    response_speed_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    terms = Column(SqliteJSON)
    exclusions = Column(SqliteJSON)
    claim_steps = Column(SqliteJSON)
    confidence = Column(SqliteJSON)
    alternatives = Column(SqliteJSON)
    source_artifact_ids = Column(SqliteJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class NotificationDB(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    audience: Mapped[str] = mapped_column(String, default="user", nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String, default="info")
    is_read: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OemCommunicationTraceDB(Base):
    __tablename__ = "oem_communication_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_user_id: Mapped[str] = mapped_column(String, index=True)
    sender_role: Mapped[str] = mapped_column(String, index=True)
    recipient_user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)  # important_update | product_recommendation
    channel: Mapped[str] = mapped_column(String, default="in_app", index=True)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String, index=True)  # sent | blocked
    blocked_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    trace_json = Column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PipelineJobDB(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    artifact_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    source_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True)
    detail = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ParsedFieldDB(Base):
    __tablename__ = "parsed_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    invoice_no: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confidence = Column(SqliteJSON)
    raw_text = Column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class WarrantyTermsCacheDB(Base):
    __tablename__ = "warranty_terms_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_text = Column(Text, nullable=True)
    terms = Column(SqliteJSON)
    exclusions = Column(SqliteJSON)
    claim_steps = Column(SqliteJSON)


class WarrantySummaryDB(Base):
    __tablename__ = "warranty_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    summary_text = Column(Text)
    source: Mapped[str] = mapped_column(String, default="template", index=True)
    summary_points = Column(SqliteJSON)
    summary_tags = Column(SqliteJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RegionalPolicyDB(Base):
    __tablename__ = "regional_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    rule_json = Column(SqliteJSON)
    active: Mapped[bool] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OemIssueSignalDB(Base):
    __tablename__ = "oem_issue_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    issue_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    severity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RiskSnapshotDB(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    warranty_id: Mapped[str] = mapped_column(String, index=True)
    risk_label: Mapped[str] = mapped_column(String, index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


try:
    from pgvector.sqlalchemy import Vector  # type: ignore
except Exception:
    Vector = None  # type: ignore

_PGVECTOR_DDL_ENABLED = os.getenv("PGVECTOR_DDL_ENABLED", "0").strip().lower() in ("1", "true", "yes")


class DocumentEmbeddingDB(Base):
    __tablename__ = "document_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String, index=True)
    doc_id: Mapped[str] = mapped_column(String, index=True)
    content = Column(Text)
    meta_json = Column(JSON)
    # Use pgvector column only when explicitly enabled; fallback to text otherwise.
    if Vector and _PGVECTOR_DDL_ENABLED:
        embedding = Column(Vector(1536))
    else:
        embedding = Column(Text)
    embedding_json = Column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ProductReviewDB(Base):
    __tablename__ = "product_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    model_code: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    product_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    text = Column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ReviewPageDB(Base):
    __tablename__ = "review_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    url: Mapped[str] = mapped_column(String, unique=True, index=True)
    product_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    snapshot_uri: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text_excerpt = Column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
