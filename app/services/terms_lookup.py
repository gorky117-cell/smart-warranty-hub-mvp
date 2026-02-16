from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import datetime, timedelta
from typing import Optional, List

from ..models import TermsResult

from sqlalchemy.orm import Session

from ..db_models import WarrantyTermsCacheDB, WarrantyDB
from .warranty_discovery import discover_sources
from .warranty_parser import parse_terms_from_url, ParsedTerms
from . import regional_policy as regional_policy_service





DEFAULT_RULES = {
    "general": 12,
    "appliance": 24,
    "electronics": 12,
    "mobile": 12,
    "ev": 36,
}

_SCRAPE_ENABLED = os.getenv("TERMS_SCRAPE_ENABLED", "1").strip().lower() in ("1", "true", "yes")
_SCRAPE_MODE = os.getenv("TERMS_SCRAPE_MODE", "auto+manual").strip().lower()
_SCRAPE_ALLOW_RETAIL = os.getenv("TERMS_SCRAPE_ALLOW_RETAIL", "1").strip().lower() in ("1", "true", "yes")
_SOURCE_INTERNAL_WARRANTY = "internal://warranty_db"
_SOURCE_INTERNAL_CACHE = "internal://terms_cache"
_SOURCE_INTERNAL_DEFAULT = "internal://default_rules"


def _mode_allows_auto(mode: str) -> bool:
    return "auto" in (mode or "")


def _mode_allows_manual(mode: str) -> bool:
    return "manual" in (mode or "")

def _normalize_category(category: Optional[str]) -> str:
    if not category:
        return "general"
    cat = category.strip().lower()
    if any(k in cat for k in ("phone", "mobile")):
        return "mobile"
    if any(k in cat for k in ("ev", "battery")):
        return "ev"
    if any(k in cat for k in ("appliance", "fridge", "wash", "microwave")):
        return "appliance"
    if any(k in cat for k in ("electronic", "device")):
        return "electronics"
    return "general"


def _default_terms(duration_months: int) -> TermsResult:
    terms = [
        f"Standard coverage for {duration_months} months from purchase date.",
        "Manufacturing defects covered under normal usage.",
    ]
    exclusions = [
        "Physical, liquid, or accidental damage.",
        "Unauthorized repairs or modifications.",
        "Damage due to power surges outside recommended limits.",
    ]
    claim_steps = [
        "Keep your invoice or receipt ready.",
        "Share model/serial details with support.",
        "Provide photos or logs to speed up verification.",
    ]
    return TermsResult(
        duration_months=duration_months,
        terms=terms,
        exclusions=exclusions,
        claim_steps=claim_steps,
        source_url=_SOURCE_INTERNAL_DEFAULT,
        raw_text=None,
    )


def _cache_is_fresh(item: WarrantyTermsCacheDB, max_age_days: int = 30) -> bool:
    return (datetime.utcnow() - item.fetched_at) <= timedelta(days=max_age_days)


def _to_terms_result(parsed: ParsedTerms, source_url: Optional[str]) -> TermsResult:
    return TermsResult(
        duration_months=parsed.duration_months,
        terms=parsed.terms or [],
        exclusions=parsed.exclusions or [],
        claim_steps=parsed.claim_steps or [],
        source_url=source_url,
        raw_text=parsed.raw_text,
    )


def _apply_region_policy(
    db: Session,
    result: TermsResult,
    *,
    region: Optional[str],
    brand: Optional[str],
    model_code: Optional[str],
    product_type: Optional[str],
) -> TermsResult:
    try:
        policy = regional_policy_service.evaluate_region_policy(
            db,
            region=region,
            brand=brand,
            model_code=model_code,
            product_type=product_type,
        )
        if policy.min_coverage_months and (result.duration_months is None or result.duration_months < policy.min_coverage_months):
            result.duration_months = policy.min_coverage_months
            # Add a policy note into terms if not already present
            note = f"Minimum coverage enforced for region {region}."
            if note not in result.terms:
                result.terms.insert(0, note)
    except Exception:
        pass
    return result


def lookup_terms(
    db: Session,
    *,
    brand: Optional[str],
    category: Optional[str],
    region: Optional[str],
    model_code: Optional[str] = None,
    product_name: Optional[str] = None,
    url_override: Optional[str] = None,
    force_refresh: bool = False,
) -> TermsResult:
    norm_category = _normalize_category(category)
    # 1) Try internal warranty records first (brand + model/product_name)
    if not force_refresh:
        try:
            q = db.query(WarrantyDB)
            has_filter = False
            if brand:
                q = q.filter(WarrantyDB.brand == brand)
                has_filter = True
            if model_code:
                q = q.filter(WarrantyDB.model_code == model_code)
                has_filter = True
            elif product_name:
                q = q.filter(WarrantyDB.product_name == product_name)
                has_filter = True
            rec = q.order_by(WarrantyDB.created_at.desc()).first() if has_filter else None
            if rec and (rec.terms or rec.exclusions or rec.claim_steps or rec.coverage_months):
                result = TermsResult(
                    duration_months=rec.coverage_months,
                    terms=rec.terms or [],
                    exclusions=rec.exclusions or [],
                    claim_steps=rec.claim_steps or [],
                    source_url=_SOURCE_INTERNAL_WARRANTY,
                    raw_text=None,
                )
                return _apply_region_policy(
                    db,
                    result,
                    region=region,
                    brand=brand,
                    model_code=model_code,
                    product_type=category,
                )
        except Exception:
            pass

        # 2) fallback: brand/category/region cache
        cached = None
        if brand:
            cache_q = db.query(WarrantyTermsCacheDB).filter(
                WarrantyTermsCacheDB.brand == brand,
                WarrantyTermsCacheDB.category == norm_category,
                WarrantyTermsCacheDB.region == region,
            )
            cached = cache_q.order_by(WarrantyTermsCacheDB.fetched_at.desc()).first()
        if cached and _cache_is_fresh(cached):
            result = TermsResult(
                duration_months=cached.duration_months,
                terms=cached.terms or [],
                exclusions=cached.exclusions or [],
                claim_steps=cached.claim_steps or [],
                source_url=cached.source_url or _SOURCE_INTERNAL_CACHE,
                raw_text=cached.raw_text,
            )
            return _apply_region_policy(
                db,
                result,
                region=region,
                brand=brand,
                model_code=model_code,
                product_type=category,
            )

    # 3) If cached not found/fresh, continue to scrape or default

    if _SCRAPE_ENABLED:
        # Manual URL override path
        if url_override and _mode_allows_manual(_SCRAPE_MODE):
            parsed, err = parse_terms_from_url(url_override)
            if parsed and not err:
                result = _to_terms_result(parsed, url_override)
                cached = WarrantyTermsCacheDB(
                    brand=brand,
                    category=norm_category,
                    region=region,
                    source_url=url_override,
                    fetched_at=datetime.utcnow(),
                    duration_months=result.duration_months,
                    raw_text=result.raw_text,
                    terms=result.terms,
                    exclusions=result.exclusions,
                    claim_steps=result.claim_steps,
                )
                db.add(cached)
                db.commit()
                return _apply_region_policy(
                    db,
                    result,
                    region=region,
                    brand=brand,
                    model_code=model_code,
                    product_type=category,
                )

        # Auto discovery path
        if _mode_allows_auto(_SCRAPE_MODE):
            sources = discover_sources(
                brand=brand,
                model_code=model_code,
                product_name=product_name,
                region=region,
                mode=_SCRAPE_MODE,
                allow_retail=_SCRAPE_ALLOW_RETAIL,
            )
            for src in sources:
                parsed, err = parse_terms_from_url(src.url)
                if not parsed or err:
                    continue
                result = _to_terms_result(parsed, src.url)
                cached = WarrantyTermsCacheDB(
                    brand=brand,
                    category=norm_category,
                    region=region,
                    source_url=src.url,
                    fetched_at=datetime.utcnow(),
                    duration_months=result.duration_months,
                    raw_text=result.raw_text,
                    terms=result.terms,
                    exclusions=result.exclusions,
                    claim_steps=result.claim_steps,
                )
                db.add(cached)
                db.commit()
                return _apply_region_policy(
                    db,
                    result,
                    region=region,
                    brand=brand,
                    model_code=model_code,
                    product_type=category,
                )

    duration = DEFAULT_RULES.get(norm_category, 12)
    result = _default_terms(duration)
    cached = WarrantyTermsCacheDB(
        brand=brand,
        category=norm_category,
        region=region,
        source_url=None,
        fetched_at=datetime.utcnow(),
        duration_months=result.duration_months,
        raw_text=None,
        terms=result.terms,
        exclusions=result.exclusions,
        claim_steps=result.claim_steps,
    )
    db.add(cached)
    db.commit()
    return _apply_region_policy(
        db,
        result,
        region=region,
        brand=brand,
        model_code=model_code,
        product_type=category,
    )
