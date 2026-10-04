"""Warranty-terms cache (`warranty_terms_cache`): what is stored, how it is keyed and what may be served.

Key: company (resolved brand) + coarse category + region + product line (from the product, e.g. "tv",
"smartphone"; None when it cannot be told). Terms cached for one product line never answer another; within
a line, an entry for the same model is preferred.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..db_models import WarrantyTermsCacheDB


def model_key(model_code: Optional[str]) -> Optional[str]:
    key = re.sub(r"[^A-Z0-9]", "", (model_code or "").upper())
    return key or None


def product_line(model_code: Optional[str], product_name: Optional[str]) -> Optional[str]:
    """Fine product line ("tv", "smartphone", "fan", ...) from the product; None when unknown."""
    if not (model_code or product_name):
        return None
    from .product_recommendations import infer_product_category

    line = infer_product_category({"product_name": product_name or "", "model_code": model_code or ""})
    return None if line in (None, "", "general") else line


def product_scope(model_code: Optional[str], product_name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    return model_key(model_code), product_line(model_code, product_name)


def scoped_query(db: Session, *, brand: Optional[str], category: str, region: Optional[str], line: Optional[str]):
    q = db.query(WarrantyTermsCacheDB).filter(
        WarrantyTermsCacheDB.brand == brand,
        WarrantyTermsCacheDB.category == category,
        WarrantyTermsCacheDB.region == region,
    )
    if line:
        return q.filter(WarrantyTermsCacheDB.product_line == line)
    return q.filter(WarrantyTermsCacheDB.product_line.is_(None))


def newest_for_scope(rows, model: Optional[str]):
    """Newest row for the same model if any, else the newest row of the product line."""
    rows = sorted(rows, key=lambda r: r.fetched_at, reverse=True)
    if model:
        same_model = [r for r in rows if r.model_code == model]
        if same_model:
            return same_model[0]
    return rows[0] if rows else None


FRESH_DAYS = 30
OFFICIAL, NON_OFFICIAL, DEFAULT = "official", "non_official", "default"


def verified_official(source_url: Optional[str], brand: Optional[str]) -> bool:
    """A real page on a verified or manually confirmed official domain of the brand."""
    if not source_url or not str(source_url).startswith(("http://", "https://")):
        return False
    from .source_trust import classify_terms_source

    return bool(classify_terms_source(brand=brand, source_url=source_url, source_type="scraped").get("verified"))


def is_official_row(row: WarrantyTermsCacheDB) -> bool:
    if row.source_type == OFFICIAL:
        return True
    # Rows written before cache fix 4 carry no source_type: official only if the URL still verifies.
    return row.source_type is None and verified_official(row.source_url, row.brand)


def latest_official(db: Session, *, brand, category, region, model, line) -> Optional[WarrantyTermsCacheDB]:
    """Newest official entry for the scope, whatever its age. Default and non-official rows never shadow it
    (cache fix 3)."""
    rows = [r for r in scoped_query(db, brand=brand, category=category, region=region, line=line).all() if is_official_row(r)]
    return newest_for_scope(rows, model)


def is_fresh(row: WarrantyTermsCacheDB, days: int = FRESH_DAYS) -> bool:
    return (datetime.utcnow() - row.fetched_at) <= timedelta(days=days)


def result_from_row(row: WarrantyTermsCacheDB):
    from ..models import TermsResult
    from .warranty_parser import sanitize_base_terms

    return TermsResult(
        duration_months=row.duration_months,
        terms=sanitize_base_terms(row.terms or []),
        exclusions=row.exclusions or [],
        claim_steps=row.claim_steps or [],
        source_url=row.source_url,
        source_urls=[row.source_url] if row.source_url else [],
        raw_text=row.raw_text,
        confidence=row.confidence,
        grounded=row.grounded,
        checked_at=row.fetched_at.isoformat(timespec="seconds"),
        needs_refresh=not is_fresh(row),
    )


def new_entry(
    *,
    brand: Optional[str],
    category: str,
    region: Optional[str],
    model: Optional[str],
    line: Optional[str],
    source_url: Optional[str],
    result,
    source_type: Optional[str] = None,
) -> WarrantyTermsCacheDB:
    if source_type is None:
        source_type = DEFAULT if not source_url else (OFFICIAL if verified_official(source_url, brand) else NON_OFFICIAL)
    return WarrantyTermsCacheDB(
        brand=brand,
        category=category,
        region=region,
        model_code=model,
        product_line=line,
        source_url=source_url,
        source_type=source_type,
        confidence=getattr(result, "confidence", None),
        grounded=getattr(result, "grounded", None),
        fetched_at=datetime.utcnow(),
        duration_months=result.duration_months,
        raw_text=result.raw_text,
        terms=result.terms,
        exclusions=result.exclusions,
        claim_steps=result.claim_steps,
    )


def cacheable(entry: WarrantyTermsCacheDB) -> bool:
    """Only results from verified official domains are cached for reuse (cache fix 4); default rows are
    kept, tagged "default", for counts only - they are never served."""
    return entry.source_type in (OFFICIAL, DEFAULT)
