import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from ..db_models import BehaviourProfile, RiskSnapshotDB, SymptomSearch, WarrantyDB
from . import product_recommendations as prod_recs_service
from .telemetry_intelligence import build_oem_telemetry_aggregate


_MIN_COHORT = int(os.getenv("OEM_AGGREGATE_MIN_COHORT", os.getenv("OEM_TELEMETRY_MIN_COHORT", "10")))


def _parse_dt(value: Optional[str], default: datetime) -> datetime:
    if not value:
        return default
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return default


def _match_warranty(
    warranty: WarrantyDB,
    *,
    product_type: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    region: Optional[str],
) -> bool:
    if brand and (warranty.brand or "").lower() != brand.lower():
        return False
    if model and (warranty.model_code or "").lower() != model.lower():
        return False
    if region and (warranty.region_code or "").lower() != region.lower():
        return False
    if product_type and product_type.lower() not in (warranty.product_name or "").lower():
        return False
    return True


def _expiry_bucket(expiry: Optional[datetime], now: datetime) -> str:
    if not expiry:
        return "unknown"
    days = (expiry - now).days
    if days < 0:
        return "expired"
    if days <= 30:
        return "0_30_days"
    if days <= 90:
        return "31_90_days"
    return "over_90_days"


def _latest_risk_by_warranty(rows: Iterable[RiskSnapshotDB]) -> Dict[str, RiskSnapshotDB]:
    latest: Dict[str, RiskSnapshotDB] = {}
    for row in sorted(rows, key=lambda r: r.created_at or datetime.min, reverse=True):
        if row.warranty_id and row.warranty_id not in latest:
            latest[row.warranty_id] = row
    return latest


def build_privacy_safe_oem_aggregate(
    db,
    *,
    product_type: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    region: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_cohort: Optional[int] = None,
) -> Dict[str, Any]:
    threshold = _MIN_COHORT if min_cohort is None else max(1, int(min_cohort))
    now = datetime.utcnow()
    start = _parse_dt(date_from, now - timedelta(days=90))
    end = _parse_dt(date_to, now)

    warranties = [
        w for w in db.query(WarrantyDB).all()
        if _match_warranty(w, product_type=product_type, brand=brand, model=model, region=region)
        and (w.created_at or now) >= start
        and (w.created_at or now) <= end
    ]
    warranty_ids = {w.id for w in warranties}

    users = {
        row.user_id
        for row in db.query(BehaviourProfile.user_id, BehaviourProfile.warranty_id).all()
        if row.warranty_id in warranty_ids and row.user_id
    }
    cohort_size = len(users) if users else len(warranty_ids)
    if cohort_size < threshold:
        return {
            "status": "suppressed",
            "reason": "minimum cohort threshold not met",
            "min_cohort": threshold,
            "cohort_size": cohort_size,
            "filters": {
                "product_type": product_type,
                "brand": brand,
                "model": model,
                "region": region,
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
            },
        }

    risk_rows = (
        db.query(RiskSnapshotDB)
        .filter(RiskSnapshotDB.warranty_id.in_(warranty_ids), RiskSnapshotDB.created_at >= start, RiskSnapshotDB.created_at <= end)
        .all()
        if warranty_ids
        else []
    )
    latest_risk = _latest_risk_by_warranty(risk_rows)
    risk_distribution: Counter = Counter()
    for snapshot in latest_risk.values():
        risk_distribution[(snapshot.risk_label or "UNKNOWN").upper()] += 1
    if not risk_distribution:
        risk_distribution["UNKNOWN"] = len(warranty_ids)

    profiles = db.query(BehaviourProfile).filter(BehaviourProfile.warranty_id.in_(warranty_ids)).all() if warranty_ids else []
    behaviour_trends = {
        "behaviour_score": 0.0,
        "care_score": 0.0,
        "responsiveness_score": 0.0,
        "count": len(profiles),
    }
    if profiles:
        behaviour_trends.update(
            {
                "behaviour_score": sum(float(p.behaviour_score or 0) for p in profiles) / len(profiles),
                "care_score": sum(float(p.care_score or 0) for p in profiles) / len(profiles),
                "responsiveness_score": sum(float(p.responsiveness_score or 0) for p in profiles) / len(profiles),
            }
        )

    expiry_cohorts: Counter = Counter(_expiry_bucket(w.expiry_date, now) for w in warranties)

    symptoms = (
        db.query(SymptomSearch).filter(SymptomSearch.warranty_id.in_(warranty_ids), SymptomSearch.created_at >= start, SymptomSearch.created_at <= end).all()
        if warranty_ids
        else []
    )
    care_issues: Counter = Counter()
    service_demand: Counter = Counter()
    for row in symptoms:
        text = (row.matched_component or row.query_text or "unknown").strip().lower()[:80]
        if text:
            care_issues[text] += 1
            service_demand[text] += 1

    product_interest = prod_recs_service.aggregate_product_interest(region=region, limit=10)
    telemetry = build_oem_telemetry_aggregate(
        db,
        brand=brand,
        model=model,
        product_type=product_type,
        region=region,
        min_cohort=threshold,
        days=max(1, (end - start).days or 1),
    )

    recommendation_opportunities = []
    high_count = risk_distribution.get("HIGH", 0)
    if high_count:
        recommendation_opportunities.append(
            {
                "type": "preventive_care",
                "reason": f"{high_count} high-risk records in cohort",
                "action": "Create targeted preventive care recommendation.",
            }
        )
    if care_issues:
        issue, count = care_issues.most_common(1)[0]
        recommendation_opportunities.append(
            {
                "type": "care_issue",
                "reason": f"Top care/service issue: {issue} ({count})",
                "action": "Publish a product-specific care tip or service checklist.",
            }
        )
    if product_interest:
        recommendation_opportunities.append(
            {
                "type": "demand_signal",
                "reason": f"Product interest signal: {product_interest[0].get('title')}",
                "action": "Review product recommendation placement.",
            }
        )

    return {
        "status": "ok",
        "min_cohort": threshold,
        "cohort_size": cohort_size,
        "filters": {
            "product_type": product_type,
            "brand": brand,
            "model": model,
            "region": region,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
        "registered_product_count": len(warranty_ids),
        "risk_distribution": dict(risk_distribution),
        "top_care_issues": [{"issue": k, "count": v} for k, v in care_issues.most_common(5)],
        "behaviour_trends": behaviour_trends,
        "expiry_cohorts": dict(expiry_cohorts),
        "product_interest": product_interest,
        "service_demand": [{"issue": k, "count": v} for k, v in service_demand.most_common(5)],
        "recommendation_opportunities": recommendation_opportunities,
        "telemetry": telemetry,
        "privacy_note": "Aggregate cohort metrics only; individual customer data is not exposed.",
    }
