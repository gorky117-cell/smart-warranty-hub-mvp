"""What the customer sees: warranty text cleaned for display (live test 1, Samsung M17e).

The database keeps the OEM text as parsed; `tidy()` is applied when a warranty is loaded for display
(`MemoryStore._row_to_warranty`), so the dashboard, the summaries and the export all show the same cleaned
claim steps, terms and exclusions - for new and older records alike.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

# A claim step is an instruction. Site labels ("Service Center", "Digital Service Center",
# "Out of Warranty Repair Charges") have no verb and are not sentences.
_STEP_VERBS = re.compile(
    r"\b(visit|call|contact|carry|keep|register|submit|book|take|bring|share|provide|check|raise|chat|email|"
    r"e-mail|send|log|locate|find|use|go|walk|request|schedule|show|present|upload|fill|download|repaired|"
    r"carried|applicable|serviced|replace(?:d)?)\b",
    re.IGNORECASE,
)
_OUT_OF_WARRANTY = re.compile(r"\bout[\s-]+of[\s-]+warranty\b|\bpaid repair\b|\brepair charges?\b|\bchargeable\b", re.IGNORECASE)
_LABEL_PREFIX = re.compile(r"^\s*type of service\s*\([^)]*\)\s*[-:]\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" ;")


def is_label(step: str) -> bool:
    """A navigation/heading label rather than an instruction."""
    words = re.findall(r"[A-Za-z]+", step)
    if not words:
        return True
    if _STEP_VERBS.search(step):
        return False
    return len(words) <= 6 and not re.search(r"[.!?:]\s*$", step.strip())


def clean_claim_steps(steps: List[str], in_warranty: Optional[bool]) -> List[str]:
    """Drop labels; for an in-warranty product never lead with an out-of-warranty step (moved last)."""
    kept: List[str] = []
    seen = set()
    for raw in steps or []:
        step = _LABEL_PREFIX.sub("", _clean(raw))
        if not step or is_label(step):
            continue
        key = step.lower().rstrip(".")
        if key in seen:
            continue
        seen.add(key)
        kept.append(step[0].upper() + step[1:])
    if in_warranty:
        kept = [s for s in kept if not _OUT_OF_WARRANTY.search(s)] + [s for s in kept if _OUT_OF_WARRANTY.search(s)]
    return kept


# --- terms and exclusions (item 5) ---------------------------------------------------------------------------

# Wording that only fits appliances (a phone has no "machine or cabinet" and is not installed on a site).
_APPLIANCE_WORDING = re.compile(
    r"\bmachine or cabinet\b|\bcabinet\b|\bmachine/unit\b|\bcompressor\b|\binstallation\b|\boutdoor unit\b|"
    r"\bindoor unit\b|\bsite \(premises\b|\bhard disk\b",
    re.IGNORECASE,
)
# The international/overseas clause is not the buyer's local warranty.
_INTERNATIONAL = re.compile(
    r"\binternational\b[^.]{0,40}\bwarranty\b|regardless of the warranty period of the country|"
    r"country where the product was (?:first )?sold|\boverseas\b",
    re.IGNORECASE,
)
# Slash-joined word lists left by page layout ("external factors/medium/data types").
_GARBLED = re.compile(r"\b[a-z]+/[a-z]+/[a-z]+\b", re.IGNORECASE)
_WORD = re.compile(r"[a-z]+")
_STOP = {"the", "a", "an", "of", "or", "and", "to", "in", "is", "be", "by", "for", "under", "this", "which", "are", "on"}


def is_phone(warranty) -> bool:
    from .terms_cache import product_line

    return product_line(getattr(warranty, "model_code", None), getattr(warranty, "product_name", None)) == "smartphone"


def _stems(text: str) -> set:
    words = {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}
    return {re.sub(r"(ing|ed|es|s)$", "", w) for w in words}


def drop_near_duplicates(items: List[str], threshold: float = 0.55) -> List[str]:
    """Keep the more complete of two items that say nearly the same thing."""
    kept: List[str] = []
    for item in items:
        stems = _stems(item)
        clash = next((i for i, other in enumerate(kept) if stems and _jaccard(stems, _stems(other)) >= threshold), None)
        if clash is None:
            kept.append(item)
        elif len(item) > len(kept[clash]):
            kept[clash] = item
    return kept


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def clean_terms(items: List[str], *, phone: bool) -> List[str]:
    out = []
    for raw in items or []:
        text = _clean(raw)
        if not text or _GARBLED.search(text):
            continue
        if phone and (_APPLIANCE_WORDING.search(text) or _INTERNATIONAL.search(text)):
            continue
        out.append(text)
    return drop_near_duplicates(out)


def in_warranty(warranty) -> Optional[bool]:
    from .warranty_status import compute_warranty_status

    status = compute_warranty_status(
        purchase_date=getattr(warranty, "purchase_date", None),
        coverage_months=getattr(warranty, "coverage_months", None),
        expiry_date=getattr(warranty, "expiry_date", None),
    ).get("status")
    if status in ("active", "expiring_soon"):
        return True
    if status == "expired":
        return False
    return None


def tidy(warranty):
    """Customer-facing copy of a CanonicalWarranty with cleaned claim steps."""
    original = list(warranty.claim_steps or [])
    steps = clean_claim_steps(original, in_warranty(warranty))
    if original and not steps:
        brand = getattr(warranty, "brand", None) or "the brand"
        steps = [
            "Keep your invoice and the product's serial number ready.",
            f"Contact {brand} support or an authorized service center to raise a claim.",
        ]
    warranty.claim_steps = steps
    phone = is_phone(warranty)
    warranty.terms = clean_terms(list(warranty.terms or []), phone=phone)
    warranty.exclusions = clean_terms(list(warranty.exclusions or []), phone=phone)
    return warranty


# --- claim wording (item 7) ------------------------------------------------------------------------------------


def serial_confirmed(warranty) -> bool:
    """A serial is stored (labelled on the invoice or confirmed by the customer)."""
    return bool((getattr(warranty, "serial_no", None) or "").strip())


def claim_wording(status: dict, warranty) -> dict:
    """Never tell the customer "eligible" on our own: with no confirmed serial, the brand decides."""
    status = dict(status or {})
    if status.get("claim_eligibility") == "eligible" and not serial_confirmed(warranty):
        brand = (getattr(warranty, "brand", None) or "").strip() or "The brand"
        status["claim_eligibility"] = "within_period"
        status["claim_message"] = f"Within warranty period - {brand} decides eligibility"
    elif status.get("claim_eligibility") == "eligible":
        brand = (getattr(warranty, "brand", None) or "").strip() or "the brand"
        status["claim_message"] = f"Within warranty period - {brand} confirms each claim"
    return status
