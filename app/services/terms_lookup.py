from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import urlparse

from ..models import TermsResult

from sqlalchemy.orm import Session

from ..db_models import WarrantyTermsCacheDB, WarrantyDB
from .warranty_discovery import discover_sources
from .warranty_parser import parse_terms_from_url, ParsedTerms, sanitize_base_terms
from . import regional_policy as regional_policy_service
from . import oem_source_policy
from . import oem_product_knowledge





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
_AUTO_MAX_SOURCES = int(os.getenv("TERMS_AUTO_MAX_SOURCES", "4"))


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


def _cache_has_real_source(item: WarrantyTermsCacheDB) -> bool:
    src = (item.source_url or "").strip()
    return bool(src) and not src.startswith("internal://")


def _to_terms_result(parsed: ParsedTerms, source_url: Optional[str]) -> TermsResult:
    return TermsResult(
        duration_months=parsed.duration_months,
        terms=sanitize_base_terms(parsed.terms or []),
        exclusions=parsed.exclusions or [],
        claim_steps=parsed.claim_steps or [],
        source_url=source_url,
        source_urls=[source_url] if source_url else [],
        raw_text=parsed.raw_text,
    )


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items or []:
        clean = " ".join(str(item).split()).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _host(source_url: Optional[str]) -> str:
    try:
        return (urlparse(source_url or "").netloc or "").lower()
    except Exception:
        return ""


def _looks_like_samsung_mobile_context(
    *,
    brand: Optional[str],
    norm_category: str,
    source_url: Optional[str],
    result: TermsResult,
) -> bool:
    brand_l = (brand or "").strip().lower()
    if not brand_l.startswith("samsung") or norm_category != "mobile":
        return False
    if "samsung.com" not in _host(source_url):
        return False
    corpus = " ".join(
        [
            *(result.terms or []),
            *(result.exclusions or []),
            *(result.claim_steps or []),
            result.raw_text or "",
        ]
    ).lower()
    return (
        "limited international one year warranty" in corpus
        or "limited warranty period of 1 year" in corpus
        or "mobile phone" in corpus
        or "batteries or displays" in corpus
    )


def _normalize_result_for_context(
    result: TermsResult,
    *,
    brand: Optional[str],
    norm_category: str,
    source_url: Optional[str],
) -> TermsResult:
    if not _looks_like_samsung_mobile_context(
        brand=brand,
        norm_category=norm_category,
        source_url=source_url,
        result=result,
    ):
        return result

    result.duration_months = 12
    blocked_fragments = (
        "60 months",
        "5 years",
        "coverplus",
        "extended warranty",
        "extended service",
        "service plan",
    )
    preferred_fragments = (
        "one year",
        "1 year",
        "12 months",
        "warranty does not cover",
        "normal wear and tear",
        "batteries or displays",
        "repair",
        "replacement",
    )
    terms = []
    for term in result.terms or []:
        lower = term.lower()
        if any(fragment in lower for fragment in blocked_fragments):
            continue
        if any(fragment in lower for fragment in preferred_fragments):
            terms.append(term)
    if not any("one year" in term.lower() or "1 year" in term.lower() for term in terms):
        terms.insert(0, "Limited international one year warranty.")

    claim_steps = []
    blocked_claims = {"news", "alerts", "community", "additional support"}
    for step in result.claim_steps or []:
        lower = step.lower()
        if any(fragment in lower for fragment in blocked_claims):
            continue
        claim_steps.append(step)
    if not claim_steps:
        claim_steps = [
            "Use Samsung warranty check or product registration.",
            "Check repair status or locate a Samsung service center.",
            "Keep invoice, model and serial details ready for support.",
        ]

    result.terms = sanitize_base_terms(_dedupe(terms))[:6]
    result.claim_steps = _dedupe(claim_steps)[:8]
    return result


def _merge_terms_results(results: List[TermsResult]) -> Optional[TermsResult]:
    usable = [r for r in results if r and (r.duration_months or r.terms or r.exclusions or r.claim_steps)]
    if not usable:
        return None
    durations = [r.duration_months for r in usable if r.duration_months]
    source_urls = _dedupe([url for r in usable for url in (r.source_urls or ([r.source_url] if r.source_url else []))])
    raw_chunks = [r.raw_text for r in usable if r.raw_text]
    return TermsResult(
        duration_months=max(durations) if durations else None,
        terms=sanitize_base_terms(_dedupe([item for r in usable for item in (r.terms or [])])),
        exclusions=_dedupe([item for r in usable for item in (r.exclusions or [])]),
        claim_steps=_dedupe([item for r in usable for item in (r.claim_steps or [])]),
        source_url=source_urls[0] if source_urls else None,
        source_urls=source_urls,
        raw_text="\n\n--- SOURCE ---\n\n".join(raw_chunks)[:12000] if raw_chunks else None,
    )


def classify_terms_source_url(source_url: Optional[str], brand: Optional[str] = None) -> str:
    src = source_url or ""
    if src.startswith(("http://", "https://")):
        if oem_source_policy.is_approved_oem_url(src, brand):
            return "approved_oem_source"
        return "scraped"
    if src.startswith(("test_data/", "file://")):
        return "synthetic_approved"
    if src.endswith("manual_url_blocked_by_oem_policy"):
        return "blocked_by_oem_policy"
    if src.endswith("default_rules"):
        return "default_rules"
    if src.endswith("warranty_db"):
        return "internal_warranty_db"
    if src.endswith("terms_cache"):
        return "internal_terms_cache"
    return "internal"


def _upsert_oem_product_knowledge(
    db: Session,
    result: TermsResult,
    *,
    brand: Optional[str],
    category: Optional[str],
    region: Optional[str],
    model_code: Optional[str],
    product_name: Optional[str],
) -> None:
    try:
        source_type = classify_terms_source_url(result.source_url, brand)
        oem_product_knowledge.upsert_product_knowledge_card(
            db,
            brand=brand,
            model_code=model_code,
            product_name=product_name,
            category=category,
            region=region,
            result=result,
            source_type=source_type,
        )
    except Exception:
        pass


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
            if rec and (rec.terms or rec.exclusions or rec.coverage_months):
                result = TermsResult(
                    duration_months=rec.coverage_months,
                    terms=sanitize_base_terms(rec.terms or []),
                    exclusions=rec.exclusions or [],
                    claim_steps=rec.claim_steps or [],
                    source_url=_SOURCE_INTERNAL_WARRANTY,
                    source_urls=[_SOURCE_INTERNAL_WARRANTY],
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
        if cached and _cache_is_fresh(cached) and _cache_has_real_source(cached):
            result = TermsResult(
                duration_months=cached.duration_months,
                terms=sanitize_base_terms(cached.terms or []),
                exclusions=cached.exclusions or [],
                claim_steps=cached.claim_steps or [],
                source_url=cached.source_url or _SOURCE_INTERNAL_CACHE,
                source_urls=[cached.source_url or _SOURCE_INTERNAL_CACHE],
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
            if not oem_source_policy.manual_url_allowed(url_override, brand):
                result = _default_terms(DEFAULT_RULES.get(norm_category, 12))
                result.source_url = "internal://manual_url_blocked_by_oem_policy"
                return _apply_region_policy(
                    db,
                    result,
                    region=region,
                    brand=brand,
                    model_code=model_code,
                    product_type=category,
                )
            parsed, err = parse_terms_from_url(url_override)
            if parsed and not err:
                result = _to_terms_result(parsed, url_override)
                result = _normalize_result_for_context(
                    result,
                    brand=brand,
                    norm_category=norm_category,
                    source_url=url_override,
                )
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
                _upsert_oem_product_knowledge(
                    db,
                    result,
                    brand=brand,
                    category=category,
                    region=region,
                    model_code=model_code,
                    product_name=product_name,
                )
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
            parsed_results: List[TermsResult] = []
            for src in sources:
                if len(parsed_results) >= max(1, _AUTO_MAX_SOURCES):
                    break
                parsed, err = parse_terms_from_url(src.url)
                if not parsed or err:
                    continue
                result = _to_terms_result(parsed, src.url)
                result = _normalize_result_for_context(
                    result,
                    brand=brand,
                    norm_category=norm_category,
                    source_url=src.url,
                )
                parsed_results.append(result)
                if result.duration_months and result.exclusions and result.claim_steps:
                    break
            merged = _merge_terms_results(parsed_results)
            if merged:
                cached = WarrantyTermsCacheDB(
                    brand=brand,
                    category=norm_category,
                    region=region,
                    source_url=merged.source_url,
                    fetched_at=datetime.utcnow(),
                    duration_months=merged.duration_months,
                    raw_text=merged.raw_text,
                    terms=merged.terms,
                    exclusions=merged.exclusions,
                    claim_steps=merged.claim_steps,
                )
                db.add(cached)
                db.commit()
                _upsert_oem_product_knowledge(
                    db,
                    merged,
                    brand=brand,
                    category=category,
                    region=region,
                    model_code=model_code,
                    product_name=product_name,
                )
                return _apply_region_policy(
                    db,
                    merged,
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
