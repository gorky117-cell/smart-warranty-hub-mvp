from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from ..db_models import RegionalPolicyDB


@dataclass
class RegionalPolicyResult:
    min_coverage_months: Optional[int]
    risk_delta: float
    reasons: List[str]


def _match_rule(rule: RegionalPolicyDB, *, region: str, brand: Optional[str], model_code: Optional[str], product_type: Optional[str]) -> bool:
    if rule.region and rule.region != region:
        return False
    if rule.brand and brand and rule.brand != brand:
        return False
    if rule.model_code and model_code and rule.model_code != model_code:
        return False
    if rule.product_type and product_type and rule.product_type != product_type:
        return False
    return True


def evaluate_region_policy(
    db: Session,
    *,
    region: Optional[str],
    brand: Optional[str],
    model_code: Optional[str],
    product_type: Optional[str],
) -> RegionalPolicyResult:
    if not region:
        return RegionalPolicyResult(None, 0.0, [])
    rules = (
        db.query(RegionalPolicyDB)
        .filter_by(active=1, region=region)
        .all()
    )
    min_coverage = None
    delta = 0.0
    reasons: List[str] = []
    for r in rules:
        if not _match_rule(r, region=region, brand=brand, model_code=model_code, product_type=product_type):
            continue
        payload = r.rule_json or {}
        mc = payload.get("min_coverage_months")
        if isinstance(mc, int):
            min_coverage = max(min_coverage or 0, mc)
        rd = payload.get("risk_delta")
        if isinstance(rd, (int, float)):
            delta += float(rd)
        rs = payload.get("reasons")
        if isinstance(rs, list):
            reasons.extend([str(x) for x in rs])
    return RegionalPolicyResult(min_coverage, delta, reasons)


def upsert_region_policy(
    db: Session,
    *,
    region: str,
    rule_json: Dict[str, Any],
    brand: Optional[str] = None,
    model_code: Optional[str] = None,
    product_type: Optional[str] = None,
    active: bool = True,
) -> RegionalPolicyDB:
    rec = (
        db.query(RegionalPolicyDB)
        .filter_by(region=region, brand=brand, model_code=model_code, product_type=product_type)
        .first()
    )
    if not rec:
        rec = RegionalPolicyDB(
            region=region,
            brand=brand,
            model_code=model_code,
            product_type=product_type,
            rule_json=rule_json,
            active=1 if active else 0,
        )
        db.add(rec)
    else:
        rec.rule_json = rule_json
        rec.active = 1 if active else 0
    db.commit()
    db.refresh(rec)
    return rec
