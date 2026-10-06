"""Quick and bulk knowledge-base entry (admin screen, step 4 of the own-words run).

An admin fills in structured facts - brand, category, model(s) or product line, region, period, start rule,
part periods, key exclusions, claim route, source link and checked date. They are stored in the existing
`verified_terms` table as sentences in SWH's own words (no brand text), written so that
`warranty_facts.build` reads the same facts back; no database change is needed.
Bulk: one brand + one category -> one product-line entry and/or one entry per model listed.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db_models import VerifiedTermsDB
from . import knowledge_base, terms_cache
from .warranty_facts import EXCLUSION_RULES

PARTS = ["compressor", "motor", "display panel", "panel", "magnetron", "heating element", "inner tank", "battery",
         "accessories", "charger", "adapter", "remote", "printhead", "drum", "condenser", "sealed system", "pcb"]
PRODUCT_LINES = ["smartphone", "laptop", "tv", "fridge", "air_conditioner", "washing_machine", "water_heater",
                 "printer", "kitchen_appliance", "microwave", "fan", "cooler", "heater", "purifier", "inverter",
                 "audio", "wearable", "camera", "router", "appliance"]
EXCLUSIONS = {key: text for key, _pattern, text in EXCLUSION_RULES}
ROUTES = {
    "authorized_centre": "Repairs are done at authorized service centres.",
    "customer_care": "Contact customer care to raise a repair request.",
    "online": "A repair request can be raised online on the brand's website or app.",
    "on_site": "Service is given at your home (on-site).",
    "carry_in": "Take the product to a service centre for repairs (carry-in).",
    "invoice": "Keep your invoice - it is needed for a claim.",
}
_PLURAL = {"consumables", "natural", "software"}


def normalized_category(value) -> Optional[str]:
    """The lookup's own category names ("refrigerator" -> "appliance"), so an entry matches; empty -> any."""
    from .terms_lookup import _normalize_category

    text = str(value or "").strip()
    return _normalize_category(text) if text else None


def _period(months: int) -> str:
    if months % 12 == 0:
        years = months // 12
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{months} months"


def _int(value, name: str, low: int, high: int) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number")
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def build_lists(payload: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Optional[int]]:
    """(terms/exclusions/claim_steps in SWH's words, duration_months) from the structured form."""
    months = _int(payload.get("duration_months"), "period (months)", 1, 240)
    start = (payload.get("start_rule") or "purchase").strip().lower()
    if start not in ("purchase", "installation"):
        raise ValueError("start_rule must be purchase or installation")
    terms = [f"The warranty period starts from the date of {start}."]
    if payload.get("covers_defects", True):
        terms.append("Repairs or replacement of parts for manufacturing defects.")
    for item in payload.get("part_periods") or []:
        part = str((item or {}).get("part") or "").strip().lower()
        if part not in PARTS:
            raise ValueError(f"part must be one of: {', '.join(PARTS)}")
        part_months = _int(item.get("months"), f"{part} period (months)", 1, 360)
        if part_months is None or (part_months > 99 and part_months % 12):
            raise ValueError(f"{part} period: give whole years above 99 months")
        terms.append(f"{part.capitalize()} covered for {_period(part_months)}.")
    reg_days = _int(payload.get("registration_days"), "registration days", 1, 365)
    if payload.get("registration_required") or reg_days:
        terms.append("Product registration " + (f"within {reg_days} days " if reg_days else "") + "is required.")
    if payload.get("pro_rata"):
        terms.append("Part of the period is pro-rata.")
    exclusions = []
    for key in payload.get("exclusion_keys") or []:
        if key not in EXCLUSIONS:
            raise ValueError(f"unknown exclusion: {key}")
        verb = "are" if key in _PLURAL or EXCLUSIONS[key].startswith(("Repairs", "Products", "Problems")) else "is"
        exclusions.append(f"{EXCLUSIONS[key]} {verb} not covered.")
    claim_steps = []
    for key in payload.get("route_keys") or []:
        if key not in ROUTES:
            raise ValueError(f"unknown claim route: {key}")
        claim_steps.append(ROUTES[key])
    return {"terms": terms, "exclusions": exclusions, "claim_steps": claim_steps}, months


def _checked_at(value) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValueError("checked_on must be a date (YYYY-MM-DD)")
    if day > datetime.utcnow().date():
        raise ValueError("checked_on cannot be in the future")
    return datetime.combine(day, datetime.min.time())


def save(db: Session, payload: Dict[str, Any], *, company: str, admin: str) -> List[VerifiedTermsDB]:
    """Create or update one entry per scope (product line and/or each model). Caller validates company/source."""
    lists, months = build_lists(payload)
    checked = _checked_at(payload.get("checked_on"))
    line = (payload.get("product_line") or "").strip().lower() or None
    if line and line not in PRODUCT_LINES:
        raise ValueError(f"product_line must be one of: {', '.join(PRODUCT_LINES)}")
    raw_models = payload.get("models") or []
    if isinstance(raw_models, str):
        raw_models = re.split(r"[\n,;]+", raw_models)
    models = []
    for raw in raw_models:
        key = terms_cache.model_key(raw)
        if key and key not in models:
            models.append(key)
    if len(models) > 200:
        raise ValueError("at most 200 models in one bulk entry")
    scopes = ([f"line:{line}"] if line else []) + [f"model:{m}" for m in models]
    if not scopes:
        raise ValueError("give a product line or at least one model (never brand-wide)")
    portal = str(payload.get("portal_url") or "").strip()
    if portal and not knowledge_base.valid_portal_url(portal):
        raise ValueError("portal_url must be a product page on righttorepairindia.gov.in (/product-details/<number>)")
    note = "Entered on the admin knowledge-base screen (SWH wording)." + (f" Also listed: {portal}" if portal else "")
    region = (str(payload.get("region") or "").strip().upper() or None)
    category = normalized_category(payload.get("category"))
    saved = []
    for scope in scopes:
        entry = (
            db.query(VerifiedTermsDB)
            .filter(func.lower(VerifiedTermsDB.company) == company.lower(), VerifiedTermsDB.product_scope == scope,
                    VerifiedTermsDB.region.is_(region) if region is None else VerifiedTermsDB.region == region,
                    VerifiedTermsDB.category.is_(category) if category is None else VerifiedTermsDB.category == category)
            .first()
        )
        if entry is None:
            entry = knowledge_base.create_entry(db, {
                "company": company, "region": region, "category": category, "product_scope": scope,
                "source_url": payload["source_url"], "duration_months": months, "locked": True,
                "note": note, **lists,
            }, admin=admin)
        else:  # quick re-entry updates the same scope instead of adding a duplicate
            entry.source_url, entry.duration_months = payload["source_url"], months
            entry.terms, entry.exclusions, entry.claim_steps = lists["terms"], lists["exclusions"], lists["claim_steps"]
            entry.verified_by, entry.updated_at, entry.note = admin, datetime.utcnow(), note
        entry.verified_at = checked
        db.commit()
        db.refresh(entry)
        saved.append(entry)
    return saved
