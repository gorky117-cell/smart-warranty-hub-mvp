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

# Brand pages often cover several product types. A term that names a part or wording only some product
# types have belongs to another product on the page, so it is dropped for product lines that do not have it
# (run 3 global check: was phones only). Nothing is dropped when the product line is unknown.
_APPLIANCES = {"fridge", "air_conditioner", "washing_machine", "microwave", "water_heater", "heater", "fan", "cooler",
               "purifier", "kitchen_appliance", "appliance", "tv", "inverter"}
PART_LINES = [
    (re.compile(r"\bcompressor\b|\brefrigerant\b|\bgas (?:charging|leak)", re.I), {"fridge", "air_conditioner", "appliance"}),
    (re.compile(r"\boutdoor unit\b|\bindoor unit\b", re.I), {"air_conditioner"}),
    (re.compile(r"\bmachine or cabinet\b|\bcabinet\b|\bmachine/unit\b|\bsite \(premises\b|\binstallation\b", re.I), _APPLIANCES),
    (re.compile(r"\bhard dis[kc]\b", re.I), {"laptop"}),
    (re.compile(r"\bdrum\b", re.I), {"washing_machine", "printer"}),
    (re.compile(r"\bmagnetron\b", re.I), {"microwave"}),
    (re.compile(r"\bprint ?head\b|\bink (?:cartridge|tank|bottle)s?\b", re.I), {"printer"}),
]
# The international/overseas clause is about products bought in another country, not the buyer's local
# warranty (any product line).
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


def product_line_of(warranty) -> Optional[str]:
    from .terms_cache import product_line

    return product_line(getattr(warranty, "model_code", None), getattr(warranty, "product_name", None))


def belongs_to_other_products(text: str, line: Optional[str]) -> bool:
    if not line:
        return False
    return any(pattern.search(text) and line not in lines for pattern, lines in PART_LINES)


def clean_terms(items: List[str], *, line: Optional[str] = None, phone: Optional[bool] = None) -> List[str]:
    """Drop garbled fragments, the bought-abroad clause, terms about other product types, near-duplicates.
    `phone=True` is the older call form for line="smartphone"."""
    if phone:
        line = line or "smartphone"
    out = []
    for raw in items or []:
        text = _clean(raw)
        if not text or _GARBLED.search(text) or _INTERNATIONAL.search(text):
            continue
        if belongs_to_other_products(text, line):
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
    line = product_line_of(warranty)
    coverage = getattr(warranty, "coverage_months", None)
    terms = [
        t for t in (warranty.terms or [])
        # A generated "Standard coverage for N months" line must agree with the coverage shown.
        if not (m := re.match(r"^\s*standard coverage for (\d+) months", str(t), re.IGNORECASE)) or not coverage
        or int(m.group(1)) == int(coverage)
    ]
    warranty.terms = clean_terms(terms, line=line)
    warranty.exclusions = clean_terms(list(warranty.exclusions or []), line=line)
    return in_own_words(warranty)


def in_own_words(warranty):
    """Replace the brand's wording with SWH-written facts (source link + checked date kept in
    alternatives["facts"]), unless the brand allows its full text (reuse_policy full_text_ok)."""
    from . import reuse_policy, warranty_facts
    from .brand_families import resolve_oem_entity

    brand = getattr(warranty, "brand", None)
    company = resolve_oem_entity(brand, product_name=getattr(warranty, "product_name", None),
                                 model_code=getattr(warranty, "model_code", None)).company or brand
    alternatives = dict(getattr(warranty, "alternatives", None) or {})
    facts = warranty_facts.build(
        brand=company or brand,
        coverage_months=getattr(warranty, "coverage_months", None),
        terms=list(warranty.terms or []),
        exclusions=list(warranty.exclusions or []),
        claim_steps=list(warranty.claim_steps or []),
        source_url=alternatives.get("terms_source_url"),
        checked_on=str(alternatives.get("terms_last_refreshed_at") or "")[:10] or None,
    )
    alternatives["facts"] = facts
    warranty.alternatives = alternatives
    if reuse_policy.allows(company, reuse_policy.FULL_TEXT_OK):
        return warranty
    lists = warranty_facts.customer_lists(facts, company or brand)
    warranty.terms, warranty.exclusions, warranty.claim_steps = lists["terms"], lists["exclusions"], lists["claim_steps"]
    return warranty


# --- claim wording (item 7) ------------------------------------------------------------------------------------


def friendly_date(value) -> str:
    """"12 Mar 2025" (no leading zero); "" when unknown."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value[:10])
        except ValueError:
            return ""
    return f"{value.day} {value.strftime('%b %Y')}"


def serial_confirmed(warranty) -> bool:
    """A serial is stored (labelled on the invoice or confirmed by the customer)."""
    return bool((getattr(warranty, "serial_no", None) or "").strip())


def claim_wording(status: dict, warranty) -> dict:
    """Never tell the customer "eligible" on our own: with no confirmed serial, the brand decides."""
    status = dict(status or {})
    if status.get("status") == "expired":
        when = friendly_date(status.get("expiry_date_used"))
        status["claim_eligibility"] = "expired"
        status["claim_message"] = f"Expired on {when}" if when else "The warranty period has ended"
        return status
    if status.get("status") == "unknown":
        status["claim_message"] = "Please check the purchase date on your invoice"
        return status
    if status.get("claim_eligibility") == "eligible" and not serial_confirmed(warranty):
        brand = (getattr(warranty, "brand", None) or "").strip() or "The brand"
        status["claim_eligibility"] = "within_period"
        status["claim_message"] = f"Within warranty period - {brand} decides eligibility"
    elif status.get("claim_eligibility") == "eligible":
        brand = (getattr(warranty, "brand", None) or "").strip() or "the brand"
        status["claim_message"] = f"Within warranty period - {brand} confirms each claim"
    return status


# --- export (item 9) -----------------------------------------------------------------------------------------

EXPORT_DISCLAIMER = (
    "Smart Warranty Hub is not the warranty provider. This summary is for information; the terms on the "
    "brand's official warranty page and the brand's decision on each claim apply."
)


def support_ref(warranty_id) -> str:
    from .product_naming import support_ref as ref

    return ref(warranty_id)


def _product_title(warranty) -> str:
    from .product_naming import short_name

    return short_name(getattr(warranty, "brand", None), getattr(warranty, "product_name", None),
                      getattr(warranty, "model_code", None))


def export_title(warranty) -> str:
    return f"Warranty summary - {_product_title(warranty)}"


def export_filename(warranty, fmt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _product_title(warranty).lower()).strip("-")[:60] or "product"
    return f"warranty-summary-{slug}-{datetime.utcnow().date().isoformat()}.{fmt}"


def export_text(warranty, evidence: dict) -> str:
    """The downloaded summary: key facts, where the terms came from and when they were checked, then the
    cleaned terms, exclusions and claim steps, and a disclaimer."""
    def fmt_date(value) -> str:
        if not value:
            return "not known"
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)[:10]

    from .warranty_status import compute_warranty_status

    from .warranty_card import CHECK_CARD_TEXT, confirmed_end_date

    # Only a CONFIRMED end date (brand's terms, or the card/invoice) goes into the claim pack; never an estimate.
    confirmed = confirmed_end_date(warranty, evidence)
    if confirmed:
        status = claim_wording(compute_warranty_status(
            purchase_date=getattr(warranty, "purchase_date", None),
            coverage_months=getattr(warranty, "coverage_months", None),
            expiry_date=confirmed,
        ), warranty)
        coverage = f"{getattr(warranty, 'coverage_months', None)} months" if getattr(warranty, "coverage_months", None) else "see end date"
        dates = f"Coverage: {coverage}    Expiry: {fmt_date(confirmed)}"
        claim = status.get("claim_message") or "Please check the dates on your invoice"
    else:
        dates = f"Coverage: {CHECK_CARD_TEXT.lower()}    Expiry: {CHECK_CARD_TEXT.lower()}"
        claim = f"{CHECK_CARD_TEXT} for how long the warranty lasts before you claim."
    lines = [
        f"Product: {_product_title(warranty)}",
        f"Brand: {getattr(warranty, 'brand', None) or 'not known'}    Model: {getattr(warranty, 'model_code', None) or 'not known'}",
        f"Serial: {getattr(warranty, 'serial_no', None) or 'not confirmed'}",
        f"Purchase date: {fmt_date(getattr(warranty, 'purchase_date', None))}",
        dates,
        f"Claim: {claim}",
        f"Support reference: Ref {support_ref(getattr(warranty, 'id', None))}",
        "",
        f"Evidence: {evidence.get('status_label') or evidence.get('status') or 'not confirmed'}",
        f"Checked on: {evidence.get('checked_on') or 'not recorded'}",
        f"Source: {evidence.get('source_url') or 'no official page recorded'}",
    ]
    for title, items in (("Coverage / terms", warranty.terms), ("Not covered", warranty.exclusions), ("How to claim", warranty.claim_steps)):
        items = [i for i in (items or []) if str(i).strip()]
        if not confirmed and title == "Coverage / terms":
            items = [i for i in items if not re.search(r"\d+\s*(?:months?|years?|yrs?)", str(i), re.IGNORECASE)]
        if items:
            lines += ["", f"{title}:"] + [f"- {i}" for i in items]
    lines += ["", EXPORT_DISCLAIMER]
    return "\n".join(lines)
