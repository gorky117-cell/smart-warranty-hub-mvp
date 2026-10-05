"""Product-specific care advice (v1): researched once per brand + model (or product line) and saved.

Design (docs/PRODUCT_CARE_DESIGN.md):
- Sources: only the brand's own user manual or official FAQ page, on the brand's verified official domain
  (same rule as the knowledge base). No crawler in v1: an admin saves what they read; nothing is fetched.
- Every tip keeps the exact sentence it came from (`quote`). The tip text may shorten the quote but may not
  add words of substance: every content word of the tip must appear in the quote (`grounded_tip`).
- Lookup: model first, then the product line; never brand-wide. A guide can link to the knowledge-base
  entry for the same product (`knowledge_base_id`).
- Customers see each tip with "From <Brand>'s user manual" / "From <Brand>'s FAQ" and a link to the page,
  next to the tips taken from the product's own exclusions.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db_models import CareGuideDB
from . import terms_cache

SOURCE_KINDS = {"manual": "user manual", "faq": "FAQ"}
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "it", "its", "is", "are", "be", "your", "you",
    "this", "that", "with", "from", "at", "by", "as", "do", "not", "never", "always", "keep", "use", "make", "sure",
    "should", "can", "may", "if", "when", "only", "any", "all", "into", "than", "then", "them", "they",
}


def _content_words(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {re.sub(r"(ing|ed|es|s)$", "", w) for w in words if w not in _STOP and len(w) > 2}


_NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                 "once", "twice", "half", "daily", "weekly", "monthly", "yearly"}


def _numbers(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w.isdigit() or w in _NUMBER_WORDS}


def grounded_tip(text: str, quote: str) -> bool:
    """The tip says nothing the quote does not: all its content words appear in the quote, and numbers and
    intervals are kept exactly ("every two weeks" may not become "every week")."""
    words = _content_words(text)
    return bool(words) and words <= _content_words(quote) and _numbers(text) == _numbers(quote)


def scope_keys(model_code: Optional[str], product_name: Optional[str]) -> List[str]:
    keys = []
    model = terms_cache.model_key(model_code)
    if model:
        keys.append(f"model:{model}")
    line = terms_cache.product_line(model_code, product_name)
    if line:
        keys.append(f"line:{line}")
    return keys


def validate(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Clean tips; raises ValueError naming the first problem."""
    tips = payload.get("tips")
    if not isinstance(tips, list) or not tips:
        raise ValueError("tips must be a non-empty list")
    cleaned = []
    for i, tip in enumerate(tips):
        if not isinstance(tip, dict):
            raise ValueError(f"tip {i + 1} must be an object with text and quote")
        text = " ".join(str(tip.get("text") or "").split())
        quote = " ".join(str(tip.get("quote") or "").split())
        if not text or not quote:
            raise ValueError(f"tip {i + 1} needs text and the exact quote from the page")
        if len(quote) > 400 or len(text) > 200:
            raise ValueError(f"tip {i + 1} is too long (text 200, quote 400 characters)")
        if not grounded_tip(text, quote):
            extra = sorted(_content_words(text) - _content_words(quote))
            raise ValueError(f"tip {i + 1} says more than its quote: {', '.join(extra)}")
        cleaned.append({"text": text, "quote": quote, "page": " ".join(str(tip.get("page") or "").split())[:20]})
    return cleaned


def save(db: Session, *, company: str, scope: str, source_kind: str, source_url: str, source_title: Optional[str],
         tips: List[Dict[str, str]], admin: str, region: Optional[str] = None,
         knowledge_base_id: Optional[int] = None) -> CareGuideDB:
    """One guide per company + scope + page: saving the same page again replaces its tips (researched once)."""
    row = (
        db.query(CareGuideDB)
        .filter(func.lower(CareGuideDB.company) == company.lower(), CareGuideDB.product_scope == scope,
                CareGuideDB.source_url == source_url)
        .first()
    )
    if row is None:
        row = CareGuideDB(company=company, product_scope=scope, source_url=source_url, checked_by=admin)
        db.add(row)
    row.region, row.source_kind, row.source_title = region, source_kind, source_title
    row.tips, row.checked_by, row.checked_at, row.knowledge_base_id = tips, admin, datetime.utcnow(), knowledge_base_id
    db.commit()
    db.refresh(row)
    return row


def find(db: Session, *, company: Optional[str], model_code: Optional[str], product_name: Optional[str]) -> List[CareGuideDB]:
    """Guides for the model, else for the product line; never brand-wide."""
    keys = scope_keys(model_code, product_name)
    if not company or not keys:
        return []
    try:
        rows = (
            db.query(CareGuideDB)
            .filter(func.lower(CareGuideDB.company) == company.strip().lower(), CareGuideDB.product_scope.in_(keys))
            .all()
        )
    except Exception:
        db.rollback()
        return []
    if not rows:
        return []
    best = min(keys.index(r.product_scope) for r in rows)
    return [r for r in rows if keys.index(r.product_scope) == best]


def customer_tips(guides: List[CareGuideDB], *, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tips in the shape of the care list ("How to look after it"), each with its source and link."""
    out = []
    for guide in guides:
        kind = SOURCE_KINDS.get(guide.source_kind, "user manual")
        for i, tip in enumerate(guide.tips or []):
            out.append({
                "product_id": f"care_guide_{guide.id}_{i}",
                "title": tip["text"],
                "why": f"“{tip['quote']}”",
                "reason": tip["quote"],
                "description": tip["quote"],
                "source_label": f"From {guide.company}'s {kind}" + (f", page {tip['page']}" if tip.get("page") else ""),
                "source_url": guide.source_url,
                "action": "oem_derived_care",
                "category": category,
                "risk_band": "MEDIUM",
                "priority": 5,
                "cta_label": "Open the source",
                "cta_url": guide.source_url,
            })
    return out


def to_dict(guide: CareGuideDB) -> Dict[str, Any]:
    return {
        "id": guide.id, "company": guide.company, "product_scope": guide.product_scope, "region": guide.region,
        "source_kind": guide.source_kind, "source_title": guide.source_title, "source_url": guide.source_url,
        "knowledge_base_id": guide.knowledge_base_id, "tips": guide.tips or [], "checked_by": guide.checked_by,
        "checked_at": guide.checked_at.isoformat() if guide.checked_at else None,
    }
