from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session

from ..db_models import WarrantyTermsCacheDB
from ..scrapers import get_scraper


@dataclass
class TermsResult:
    duration_months: Optional[int]
    terms: List[str]
    exclusions: List[str]
    claim_steps: List[str]
    source_url: Optional[str]
    raw_text: Optional[str]


DEFAULT_RULES = {
    "general": 12,
    "appliance": 24,
    "electronics": 12,
    "mobile": 12,
    "ev": 36,
}

_SCRAPE_ENABLED = os.getenv("TERMS_SCRAPE_ENABLED", "1").strip().lower() in ("1", "true", "yes")

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
    return TermsResult(duration_months, terms, exclusions, claim_steps, None, None)


def _cache_is_fresh(item: WarrantyTermsCacheDB, max_age_days: int = 30) -> bool:
    return (datetime.utcnow() - item.fetched_at) <= timedelta(days=max_age_days)


def lookup_terms(
    db: Session,
    *,
    brand: Optional[str],
    category: Optional[str],
    region: Optional[str],
    model_code: Optional[str] = None,
) -> TermsResult:
    norm_category = _normalize_category(category)
    cache_q = db.query(WarrantyTermsCacheDB).filter(
        WarrantyTermsCacheDB.brand == brand,
        WarrantyTermsCacheDB.category == norm_category,
        WarrantyTermsCacheDB.region == region,
    )
    cached = cache_q.order_by(WarrantyTermsCacheDB.fetched_at.desc()).first()
    if cached and _cache_is_fresh(cached):
        return TermsResult(
            cached.duration_months,
            cached.terms or [],
            cached.exclusions or [],
            cached.claim_steps or [],
            cached.source_url,
            cached.raw_text,
        )

    scraper = get_scraper(brand) if _SCRAPE_ENABLED else None
    if scraper:
        try:
            result = scraper(
                brand=brand,
                model_code=model_code,
                category=norm_category,
                region=region,
            )
            if result:
                parsed = TermsResult(
                    result.get("duration_months"),
                    result.get("terms", []) or [],
                    result.get("exclusions", []) or [],
                    result.get("claim_steps", []) or [],
                    result.get("source_url"),
                    result.get("raw_text"),
                )
                cached = WarrantyTermsCacheDB(
                    brand=brand,
                    category=norm_category,
                    region=region,
                    source_url=parsed.source_url,
                    fetched_at=datetime.utcnow(),
                    duration_months=parsed.duration_months,
                    raw_text=parsed.raw_text,
                    terms=parsed.terms,
                    exclusions=parsed.exclusions,
                    claim_steps=parsed.claim_steps,
                )
                db.add(cached)
                db.commit()
                return parsed
        except Exception:
            pass

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
    return result
