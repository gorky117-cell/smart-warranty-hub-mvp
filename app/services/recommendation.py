from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Literal
import logging

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..db_models import (
    BehaviourProfile,
    RecommendationEvent,
    RecommendationRule,
    WarrantyDB,
)
from .predictive import score_warranty
from . import product_recommendations as prod_recs

logger = logging.getLogger(__name__)


class ProductRecommendation(TypedDict):
    id: str
    title: str
    description: str
    action: Literal["upgrade", "replace", "extended_warranty", "accessory"]
    reason: str
    region: Optional[str]
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]


PRODUCT_CATALOG: List[dict] = [
    {
        "segment": "smartphone",
        "action": "upgrade",
        "title": "Upgrade to a premium smartphone",
        "description": "High-risk phones near warranty end may benefit from a newer model.",
        "regions": ["APAC", "EU", "NA"],
        "risk_bands": ["HIGH"],
    },
    {
        "segment": "smartphone",
        "action": "extended_warranty",
        "title": "Extended warranty for your phone",
        "description": "Extend coverage before your current warranty expires.",
        "regions": ["APAC", "EU", "NA"],
        "risk_bands": ["HIGH", "MEDIUM"],
    },
    {
        "segment": "generic_device",
        "action": "accessory",
        "title": "Protective accessories bundle",
        "description": "Case, screen guard, and surge protector to reduce misuse risk.",
        "regions": ["APAC", "EU", "NA"],
        "risk_bands": ["LOW", "MEDIUM"],
    },
]

DEFAULT_RULES: List[Dict] = [
    {
        "segment": "AIR_QUALITY",
        "condition": {"min_aqi_band": 2},
        "title": "Air quality is high",
        "message": "Use an air purifier at home. If you commute by car, consider a small cabin purifier.",
        "priority": 1,
    },
    {
        "segment": "CARE_ROUTINE",
        "condition": {"min_risk_label": "MEDIUM", "max_behaviour_score": 0.6, "max_care_score": 0.6},
        "title": "Give your device a quick health boost",
        "message": "Clean filters, descale, and book a preventive service to avoid surprises.",
        "priority": 2,
    },
]


def _infer_segment_from_warranty(warranty: dict) -> str:
    name = (warranty.get("product_name") or "").lower()
    model = (warranty.get("model_code") or "").lower()
    if any(token in name for token in ["phone", "galaxy", "iphone"]) or "sm-" in model:
        return "smartphone"
    return "generic_device"


def _risk_label_rank(label: str) -> int:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return order.get(label.upper(), 0)


def _load_rules(db: Session) -> List[RecommendationRule]:
    rules = db.query(RecommendationRule).filter_by(active=1).order_by(RecommendationRule.priority.asc()).all()
    if rules:
        return rules
    # fallback to defaults (in-memory)
    fallback = []
    for r in DEFAULT_RULES:
        rule = RecommendationRule(
            segment=r["segment"],
            condition_json=r["condition"],
            title=r["title"],
            message=r["message"],
            priority=r["priority"],
            active=1,
        )
        fallback.append(rule)
    return fallback


def _matches_rule(rule: RecommendationRule, context: Dict) -> bool:
    cond = rule.condition_json or {}
    aqi = context.get("aqi_band", 0)
    risk_label = context.get("risk_label", "LOW")
    behaviour_score = context.get("behaviour_score", 0.5)
    care_score = context.get("care_score", 0.5)
    product_type = context.get("product_type", "")

    min_aqi = cond.get("min_aqi_band")
    if min_aqi is not None and aqi < min_aqi:
        return False
    min_risk_label = cond.get("min_risk_label")
    if min_risk_label and _risk_label_rank(risk_label) < _risk_label_rank(min_risk_label):
        return False
    max_behaviour = cond.get("max_behaviour_score")
    if max_behaviour is not None and behaviour_score > max_behaviour:
        return False
    max_care = cond.get("max_care_score")
    if max_care is not None and care_score > max_care:
        return False
    pt_filter = cond.get("product_type_filter")
    if pt_filter and product_type and product_type.lower() not in pt_filter:
        return False
    return True


def get_recommendations_for_user(db: Session, user_id: str, warranty_id: Optional[str] = None) -> Dict[str, object]:
    # build context
    try:
        behaviour_profile = (
            db.query(BehaviourProfile)
            .filter_by(user_id=user_id, warranty_id=warranty_id)
            .order_by(BehaviourProfile.id.desc())
            .first()
        )
    except Exception:
        behaviour_profile = None
    behaviour_score = behaviour_profile.behaviour_score if behaviour_profile else 0.5
    care_score = behaviour_profile.care_score if behaviour_profile else 0.5
    resp_score = behaviour_profile.responsiveness_score if behaviour_profile else 0.5
    aqi_band = behaviour_profile.aqi_band if behaviour_profile else 0
    product_type = behaviour_profile.product_type if behaviour_profile else ""

    risk_label = "LOW"
    predictive_result: Dict[str, object] = {}
    try:
        if warranty_id:
            risk_data = score_warranty(user_id, warranty_id)
            risk_label = risk_data.get("risk_label", "LOW")
            predictive_result = risk_data
    except Exception:
        risk_label = "LOW"

    warranty = None
    if warranty_id:
        try:
            warranty = db.query(WarrantyDB).filter_by(id=warranty_id).first()
        except Exception:
            warranty = None
    warranty_dict: Dict[str, object] = {}
    if warranty:
        warranty_dict = {
            "id": warranty.id,
            "product_name": warranty.product_name,
            "brand": warranty.brand,
            "model_code": warranty.model_code,
            "coverage_months": warranty.coverage_months,
            "purchase_date": warranty.purchase_date,
            "region": getattr(warranty, "region_code", None),
        }

    context = {
        "behaviour_score": behaviour_score,
        "care_score": care_score,
        "responsiveness_score": resp_score,
        "aqi_band": aqi_band,
        "risk_label": risk_label,
        "product_type": product_type or "",
    }

    rules = _load_rules(db)
    matches: List[RecommendationRule] = [r for r in rules if _matches_rule(r, context)]
    matches = sorted(matches, key=lambda r: r.priority)[:3]

    now = datetime.utcnow()
    events = []
    for rule in matches:
        if isinstance(rule, RecommendationRule) and rule.id:
            evt = RecommendationEvent(
                user_id=user_id,
                warranty_id=warranty_id,
                rule_id=rule.id,
                shown_at=now,
            )
            db.add(evt)
            events.append(evt)
    if events:
        db.commit()

    results: List[Dict] = []
    for rule in matches:
        results.append(
            {
                "segment": rule.segment,
                "title": rule.title,
                "message": rule.message,
                "priority": rule.priority,
            }
        )
    region = warranty_dict.get("region")
    # New product recommendations (additive) using dedicated module.
    product_recs = prod_recs.build_product_recommendations(
        user_id=user_id,
        warranty_id=warranty_id or "",
        region=region,
        warranty=warranty_dict,
        predictive=predictive_result or {},
    )

    # Backward-compatible shape: map to existing fields if UI expects them.
    mapped_product_recs: List[Dict] = []
    for rec in product_recs:
        mapped_product_recs.append(
            {
                "id": rec.get("product_id", rec.get("title", "")),
                "title": rec.get("title", ""),
                "description": rec.get("why", rec.get("description", "")),
                "action": rec.get("category", ""),
                "reason": rec.get("why", rec.get("description", "")),
                "region": rec.get("region"),
                "risk_band": rec.get("risk_band", "MEDIUM"),
                # preserve new fields as well
                "product_id": rec.get("product_id"),
                "category": rec.get("category"),
                "priority": rec.get("priority"),
                "cta_label": rec.get("cta_label"),
                "cta_url": rec.get("cta_url"),
            }
        )

    return {
        "recommendations": results,
        "product_recommendations": mapped_product_recs,
    }


def log_recommendation_event(user_id: str, warranty_id: Optional[str], rule_id: Optional[int], clicked: bool = False, dismissed: bool = False):
    with SessionLocal() as db:
        evt = RecommendationEvent(
            user_id=user_id,
            warranty_id=warranty_id,
            rule_id=rule_id,
            shown_at=datetime.utcnow(),
            clicked=1 if clicked else 0,
            dismissed=1 if dismissed else 0,
        )
        db.add(evt)
        db.commit()
        return evt
