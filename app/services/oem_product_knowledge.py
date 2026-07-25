from __future__ import annotations

import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import TermsResult
from . import rag


_SAFE_SOURCE_TYPES = {"approved_oem_source", "synthetic_approved"}


def _clean_key(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "unknown").strip().lower()).strip("_") or "unknown"


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


def official_knowledge_allowed(source_type: Optional[str], source_url: Optional[str]) -> bool:
    return (source_type or "").strip().lower() in _SAFE_SOURCE_TYPES


def build_product_knowledge_card(
    *,
    brand: Optional[str],
    model_code: Optional[str],
    product_name: Optional[str],
    category: Optional[str],
    region: Optional[str],
    result: TermsResult,
    source_type: Optional[str],
) -> Optional[Dict[str, object]]:
    source_urls = _dedupe(result.source_urls or ([result.source_url] if result.source_url else []))
    source_url = source_urls[0] if source_urls else result.source_url
    if not official_knowledge_allowed(source_type, source_url):
        return None

    terms = _dedupe(result.terms or [])
    exclusions = _dedupe(result.exclusions or [])
    claim_steps = _dedupe(result.claim_steps or [])
    if not any([result.duration_months, terms, exclusions, claim_steps]):
        return None

    doc_id = "oem_product_knowledge:{brand}:{model}:{region}".format(
        brand=_clean_key(brand),
        model=_clean_key(model_code or product_name),
        region=_clean_key(region),
    )
    title = " ".join(part for part in [brand, model_code or product_name] if part).strip() or "OEM product"
    lines = [
        f"OEM product knowledge card: {title}",
        f"Region: {region or 'unknown'}",
        f"Category: {category or 'unknown'}",
        f"Source type: {source_type or 'unknown'}",
    ]
    if source_urls:
        lines.append("Sources: " + "; ".join(source_urls[:5]))
    if result.duration_months:
        lines.append(f"Base warranty duration: {result.duration_months} months")
    if terms:
        lines.append("Terms:")
        lines.extend([f"- {item}" for item in terms[:12]])
    if exclusions:
        lines.append("Exclusions:")
        lines.extend([f"- {item}" for item in exclusions[:8]])
    if claim_steps:
        lines.append("Claim/support steps:")
        lines.extend([f"- {item}" for item in claim_steps[:8]])
    lines.append("Boundary: public OEM/product evidence only; no customer invoice or behavior data.")

    metadata = {
        "brand": brand,
        "model_code": model_code,
        "product_name": product_name,
        "category": category,
        "region": region,
        "source_type": source_type,
        "source_url": source_url,
        "source_urls": source_urls,
        "public_oem_product_data": True,
    }
    return {"doc_id": doc_id, "content": "\n".join(lines), "metadata": metadata}


def upsert_product_knowledge_card(
    db: Session,
    *,
    brand: Optional[str],
    model_code: Optional[str],
    product_name: Optional[str],
    category: Optional[str],
    region: Optional[str],
    result: TermsResult,
    source_type: Optional[str],
) -> Optional[Dict[str, object]]:
    card = build_product_knowledge_card(
        brand=brand,
        model_code=model_code,
        product_name=product_name,
        category=category,
        region=region,
        result=result,
        source_type=source_type,
    )
    if not card:
        return None
    rag.add_event_documents(
        db,
        doc_type="oem_product_knowledge",
        doc_id=str(card["doc_id"]),
        content=str(card["content"]),
        metadata=card["metadata"],  # type: ignore[arg-type]
    )
    return card
