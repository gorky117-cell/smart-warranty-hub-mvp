"""Warranty-terms cache (`warranty_terms_cache`): what is stored, how it is keyed and what may be served.

Key: company (resolved brand) + coarse category + region + product line (from the product, e.g. "tv",
"smartphone"; None when it cannot be told). Terms cached for one product line never answer another; within
a line, an entry for the same model is preferred.
"""
from __future__ import annotations

import re
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


def new_entry(
    *,
    brand: Optional[str],
    category: str,
    region: Optional[str],
    model: Optional[str],
    line: Optional[str],
    source_url: Optional[str],
    result,
) -> WarrantyTermsCacheDB:
    from datetime import datetime

    return WarrantyTermsCacheDB(
        brand=brand,
        category=category,
        region=region,
        model_code=model,
        product_line=line,
        source_url=source_url,
        fetched_at=datetime.utcnow(),
        duration_months=result.duration_months,
        raw_text=result.raw_text,
        terms=result.terms,
        exclusions=result.exclusions,
        claim_steps=result.claim_steps,
    )
