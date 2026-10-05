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
    return warranty
