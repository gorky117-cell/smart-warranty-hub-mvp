"""Knowledge base v1: hand-checked warranty terms (table `verified_terms`).

- Lookups check it first, including on forced refreshes, scoped by company, region, category and model
  or product line (an entry never answers another product line).
- A re-check never overwrites a locked entry: if the official page now disagrees, the new reading is
  saved for review (`verified_terms_reviews`) and every admin is notified. Unlocked entries are updated.
- Lock / unlock / create / review decisions are written to the audit log.
- Customers see "Checked on <date>".
Empty until an admin adds entries; nothing is filled in automatically.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db_models import UserDB, VerifiedTermsDB, VerifiedTermsReviewDB
from . import terms_cache

SOURCE_KIND = "knowledge_base"
# Secondary source only: an admin may cite the government's Right to Repair portal page for the same product.
# Stored in the entry's note (no database change); never fetched or looked up automatically.
PORTAL_LABEL = "Also listed on the Government of India's Right to Repair portal"
_PORTAL_RE = re.compile(r"https://righttorepairindia\.gov\.in/(?:product-details|product)/\d+/?")


def valid_portal_url(url) -> bool:
    return bool(url) and bool(_PORTAL_RE.fullmatch(str(url).strip()))


def portal_url_of(entry) -> Optional[str]:
    match = _PORTAL_RE.search(entry.note or "") if entry is not None else None
    return match.group(0) if match else None


def ready() -> bool:
    from ..schema_upgrade import knowledge_base_ready

    return knowledge_base_ready()


def scope_keys(model_code: Optional[str], line: Optional[str]) -> List[str]:
    keys = []
    model = terms_cache.model_key(model_code)
    if model:
        keys.append(f"model:{model}")
    if line:
        keys.append(f"line:{line}")
    return keys


def page_fingerprint(text: Optional[str]) -> Optional[str]:
    """SHA-256 of the page text with whitespace and case normalised."""
    norm = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else None


def find_entry(
    db: Session,
    *,
    company: Optional[str],
    region: Optional[str],
    category: Optional[str],
    model_code: Optional[str],
    product_name: Optional[str],
) -> Optional[VerifiedTermsDB]:
    if not company or not ready():
        return None
    keys = scope_keys(model_code, terms_cache.product_line(model_code, product_name))
    if not keys:
        return None  # never brand-wide
    try:
        rows = (
            db.query(VerifiedTermsDB)
            .filter(func.lower(VerifiedTermsDB.company) == company.strip().lower())
            .filter(VerifiedTermsDB.product_scope.in_(keys))
            .filter(or_(VerifiedTermsDB.region.is_(None), VerifiedTermsDB.region == region))
            .filter(or_(VerifiedTermsDB.category.is_(None), VerifiedTermsDB.category == category))
            .all()
        )
    except Exception:
        db.rollback()
        return None
    if not rows:
        return None
    # Most specific first: model over product line, then a named region, then a named category, then newest.
    rows.sort(key=lambda r: (keys.index(r.product_scope), r.region is None, r.category is None, -r.verified_at.timestamp()))
    return rows[0]


def result_from_entry(entry: VerifiedTermsDB):
    from ..models import TermsResult

    return TermsResult(
        duration_months=entry.duration_months,
        terms=list(entry.terms or []),
        exclusions=list(entry.exclusions or []),
        claim_steps=list(entry.claim_steps or []),
        source_url=entry.source_url,
        source_urls=[entry.source_url],
        confidence=1.0,
        grounded=True,
        checked_at=entry.verified_at.isoformat(timespec="seconds"),
        needs_refresh=False,
        source_kind=SOURCE_KIND,
        also_listed_url=portal_url_of(entry),
    )


def to_dict(entry: VerifiedTermsDB) -> Dict[str, Any]:
    return {
        "id": entry.id, "company": entry.company, "region": entry.region, "category": entry.category,
        "product_scope": entry.product_scope, "source_url": entry.source_url, "page_fingerprint": entry.page_fingerprint,
        "duration_months": entry.duration_months, "terms": entry.terms or [], "exclusions": entry.exclusions or [],
        "claim_steps": entry.claim_steps or [], "verified_by": entry.verified_by,
        "verified_at": entry.verified_at.isoformat(timespec="seconds") if entry.verified_at else None,
        "locked": bool(entry.locked), "note": entry.note, "portal_url": portal_url_of(entry),
    }


def review_to_dict(review: VerifiedTermsReviewDB) -> Dict[str, Any]:
    return {
        "id": review.id, "entry_id": review.entry_id, "status": review.status,
        "found_at": review.found_at.isoformat(timespec="seconds") if review.found_at else None,
        "source_url": review.source_url, "page_fingerprint": review.page_fingerprint,
        "duration_months": review.duration_months, "terms": review.terms or [], "exclusions": review.exclusions or [],
        "claim_steps": review.claim_steps or [], "differences": review.differences or [],
        "resolved_by": review.resolved_by,
    }


def _audit(action: str, detail: str) -> None:
    from .audit import log_action

    log_action(action, detail)


def _notify_admins(db: Session, entry: VerifiedTermsDB, differences: List[str]) -> int:
    from .notifications import create_notification

    admins = [u.username for u in db.query(UserDB).filter(UserDB.role == "admin").all()]
    for username in admins:
        create_notification(
            user_id=username,
            warranty_id=f"kb:{entry.id}",
            type="knowledge_base_review",
            title=f"Hand-checked terms changed: {entry.company} {entry.product_scope}",
            message="The official page no longer matches the checked entry: " + "; ".join(differences)[:400],
            severity="warning",
            db=db,
            audience="admin",
            brand=entry.company,
            region=entry.region,
        )
    return len(admins)


def create_entry(db: Session, payload: Dict[str, Any], *, admin: str) -> VerifiedTermsDB:
    """Validated by the caller (endpoint); source_url must be an official page of the company."""
    now = datetime.utcnow()
    entry = VerifiedTermsDB(
        company=payload["company"], region=payload.get("region"), category=payload.get("category"),
        product_scope=payload["product_scope"], source_url=payload["source_url"],
        page_fingerprint=payload.get("page_fingerprint"), duration_months=payload.get("duration_months"),
        terms=payload.get("terms") or [], exclusions=payload.get("exclusions") or [],
        claim_steps=payload.get("claim_steps") or [], verified_by=admin, verified_at=now,
        locked=bool(payload.get("locked", True)), note=payload.get("note"), created_at=now, updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _audit("kb_create", f"entry={entry.id} company={entry.company} scope={entry.product_scope} by={admin}")
    return entry


def set_lock(db: Session, entry: VerifiedTermsDB, locked: bool, *, admin: str) -> VerifiedTermsDB:
    entry.locked = locked
    entry.updated_at = datetime.utcnow()
    db.commit()
    _audit("kb_lock" if locked else "kb_unlock", f"entry={entry.id} by={admin}")
    return entry


def compare(entry: VerifiedTermsDB, *, duration_months, terms, exclusions, claim_steps, fingerprint) -> List[str]:
    differences = []
    if fingerprint and entry.page_fingerprint and fingerprint != entry.page_fingerprint:
        differences.append("page text changed")
    if duration_months != entry.duration_months:
        differences.append(f"duration {entry.duration_months} -> {duration_months} months")
    norm = lambda items: {re.sub(r"\s+", " ", str(i)).strip().lower() for i in (items or [])}  # noqa: E731
    if norm(exclusions) != norm(entry.exclusions):
        differences.append("exclusions changed")
    if norm(claim_steps) != norm(entry.claim_steps):
        differences.append("claim steps changed")
    if norm(terms) != norm(entry.terms):
        differences.append("terms changed")
    return differences


def recheck(db: Session, entry: VerifiedTermsDB, *, admin: str, parse=None) -> Dict[str, Any]:
    """Read the official page again. Locked + different -> review + admin notification (entry untouched).
    Unlocked + different -> entry updated. Same -> only the fingerprint is recorded if it was missing."""
    from .warranty_parser import parse_terms_from_url

    parsed, err = (parse or parse_terms_from_url)(entry.source_url)
    if err or parsed is None:
        _audit("kb_recheck_failed", f"entry={entry.id} by={admin} error={str(err)[:120]}")
        return {"outcome": "fetch_failed", "error": str(err or "no result")[:200]}
    fingerprint = page_fingerprint(getattr(parsed, "raw_text", None))
    found = {
        "duration_months": parsed.duration_months, "terms": list(parsed.terms or []),
        "exclusions": list(parsed.exclusions or []), "claim_steps": list(parsed.claim_steps or []),
    }
    differences = compare(entry, fingerprint=fingerprint, **found)
    if not differences:
        if fingerprint and not entry.page_fingerprint:
            entry.page_fingerprint = fingerprint
            db.commit()
        _audit("kb_recheck_same", f"entry={entry.id} by={admin}")
        return {"outcome": "unchanged"}
    if entry.locked:
        review = VerifiedTermsReviewDB(
            entry_id=entry.id, found_at=datetime.utcnow(), source_url=entry.source_url, page_fingerprint=fingerprint,
            differences=differences, status="pending", **found,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        notified = _notify_admins(db, entry, differences)
        _audit("kb_recheck_review", f"entry={entry.id} review={review.id} by={admin} differences={differences}")
        return {"outcome": "review_created", "review_id": review.id, "differences": differences, "admins_notified": notified}
    for key, value in found.items():
        setattr(entry, key, value)
    entry.page_fingerprint = fingerprint
    entry.verified_by, entry.verified_at, entry.updated_at = admin, datetime.utcnow(), datetime.utcnow()
    db.commit()
    _audit("kb_recheck_updated", f"entry={entry.id} by={admin} differences={differences}")
    return {"outcome": "updated", "differences": differences}


def resolve_review(db: Session, review: VerifiedTermsReviewDB, accept: bool, *, admin: str) -> Dict[str, Any]:
    entry = db.query(VerifiedTermsDB).filter_by(id=review.entry_id).first()
    if accept:
        if entry is None:
            raise ValueError("entry_missing")
        if entry.locked:
            raise PermissionError("entry_locked")
        for key in ("duration_months", "terms", "exclusions", "claim_steps", "page_fingerprint"):
            setattr(entry, key, getattr(review, key))
        entry.verified_by, entry.verified_at, entry.updated_at = admin, datetime.utcnow(), datetime.utcnow()
    review.status = "accepted" if accept else "dismissed"
    review.resolved_by, review.resolved_at = admin, datetime.utcnow()
    db.commit()
    _audit("kb_review_accepted" if accept else "kb_review_dismissed", f"review={review.id} entry={review.entry_id} by={admin}")
    return review_to_dict(review)


def counts(db: Session) -> Dict[str, Any]:
    if not ready():
        return {"available": False}
    return {
        "entries": db.query(VerifiedTermsDB).count(),
        "locked_entries": db.query(VerifiedTermsDB).filter(VerifiedTermsDB.locked.is_(True)).count(),
        "pending_reviews": db.query(VerifiedTermsReviewDB).filter_by(status="pending").count(),
    }
