"""'Your warranty in 5 lines', shown right after an upload, and the warranty types it must recognise.

Every line comes from what is stored for the product: the dates, the cleaned terms/exclusions/claim steps
(see customer_content.tidy) and the invoice text. Nothing is invented: when a line has no source it says
"Please confirm ..." and is flagged `confirm=True` so the page can highlight it.

`detect_types` recognises the warranty types of the global rule from the invoice and terms text; each
finding carries the sentence it came from.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, List, Optional

from .customer_content import friendly_date, is_phone
from .warranty_status import compute_warranty_status

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
FIELD_NAMES = {"brand": "brand", "model_code": "model", "serial_no": "serial number", "purchase_date": "purchase date",
               "product_name": "product", "invoice_no": "invoice number", "coverage_months": "warranty period"}
_PART_WORDS = (r"compressor|motor|magnetron|panel|display panel|heating element|inner tank|tank|battery|"
               r"accessor(?:y|ies)|charger|adapter|remote|printhead|drum|condenser|sealed system|pcb")
_PERIOD = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*(?:\(\d+\)\s*)?(years?|yrs?|months?)"
_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "twelve": 12}


def _first_sentence(text: str, limit: int = 160) -> str:
    sentence = _SENTENCE.split(" ".join(str(text or "").split()))[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rsplit(" ", 1)[0] + "..."


def _months(qty: str, unit: str) -> int:
    n = int(qty) if qty.isdigit() else _NUMBERS.get(qty.lower(), 0)
    return n * 12 if unit.lower().startswith(("year", "yr")) else n


def _months_left(today: date, expiry: date) -> int:
    months = (expiry.year - today.year) * 12 + (expiry.month - today.month)
    if expiry.day < today.day:
        months -= 1
    return max(months, 0)


def _sentences(*texts: str) -> List[str]:
    out = []
    for text in texts:
        for part in re.split(r"(?<=[.!?])\s+|\n+", str(text or "")):
            part = " ".join(part.split())
            if part:
                out.append(part)
    return out


def detect_types(invoice_text: str = "", terms: Optional[List[str]] = None, exclusions: Optional[List[str]] = None) -> List[Dict]:
    """Warranty types found in the text, each {"type", "text", "source"} with the sentence it came from."""
    found: List[Dict] = []
    seen = set()

    def add(kind: str, text: str, sentence: str, source: str) -> None:
        if (kind, text) in seen:
            return
        seen.add((kind, text))
        found.append({"type": kind, "text": text, "source_sentence": sentence[:240], "source": source})

    sources = [("invoice", s) for s in _sentences(invoice_text)]
    sources += [("terms", s) for s in _sentences(*(terms or []))] + [("exclusions", s) for s in _sentences(*(exclusions or []))]
    for source, sentence in sources:
        low = sentence.lower()
        for part_first in (True, False):
            # "compressor is covered for 10 years" / "5 years on the compressor" (the period right before the
            # part, so "1 year on the product and 5 years on the compressor" gives 5 years).
            pattern = (rf"\b({_PART_WORDS})\b[^.]{{0,40}}?\b{_PERIOD}" if part_first
                       else rf"\b{_PERIOD}\s+(?:warranty\s+)?(?:on|for)\s+(?:the\s+|its\s+|all\s+)?(?:[a-z]+\s+)?({_PART_WORDS})\b")
            for m in re.finditer(pattern, low):
                part, qty, unit = (m.group(1), m.group(2), m.group(3)) if part_first else (m.group(3), m.group(1), m.group(2))
                months = _months(qty, unit)
                if months:
                    years = months // 12
                    label = (f"{years} year{'s' if years != 1 else ''}" if months % 12 == 0 and months >= 12
                             else f"{months} months")
                    add("part_period", f"{part.capitalize()}: {label}", sentence, source)
        if re.search(r"extended warranty|protection plan|complete care|care\s*\+|applecare|extended service plan|"
                     r"\bamc\b|annual maintenance contract|onsitego|accidental (?:damage )?protection plan", low):
            if not re.search(r"\bnot\b[^.]{0,20}(?:extended|protection)|available\b", low):
                add("extended_plan", "Extended warranty or protection plan bought separately", sentence, source)
            else:
                add("extended_plan_offer", "An extended plan is mentioned (offered, not shown as bought)", sentence, source)
        if re.search(r"pro[\s-]?rata|prorata|proportionate", low):
            add("pro_rata", "Pro-rata: later in the period you may pay part of the cost", sentence, source)
        if re.search(r"(?:from|after) (?:the )?date of installation|installation date|from installation", low):
            add("starts_at_installation", "The period starts from installation, not purchase", sentence, source)
        if re.search(r"regist(?:er|ration)[^.]{0,60}(?:within|mandatory|required|must|necessary|to avail)|"
                     r"(?:must|should|need to) (?:be )?regist", low):
            add("registration_required", "Registration is required", sentence, source)
        if re.search(r"\bon[\s-]?site\b|at (?:your|customer'?s?) (?:home|premises)|home service", low):
            add("on_site", "Service at your home (on-site)", sentence, source)
        if re.search(r"carry[\s-]?in|walk[\s-]?in|bring the (?:product|unit|device)|take the (?:product|unit|device) to", low):
            add("carry_in", "Take the product to a service centre (carry-in)", sentence, source)
        if re.search(r"seller warranty|warranty (?:is )?(?:provided|given|offered) by (?:the )?(?:seller|dealer|shop|store)|"
                     r"shop warranty|dealer warranty|store warranty", low):
            add("seller_warranty", "Warranty from the seller, not the brand", sentence, source)
        # Said about the whole product only on the invoice ("no warranty for consumables" in terms is a limit).
        if source == "invoice" and re.search(
            r"\bno warranty\b|without (?:any )?warranty|sold as[\s-]is|warranty\s*[:\-]\s*(?:nil|none|na|n/a)\b", low
        ):
            add("no_warranty", "No warranty", sentence, source)
        if source == "invoice" and re.search(
            r"\brefurbished\b|\brenewed\b|\bopen[\s-]box\b|\bpre[\s-]?owned\b|\bsecond[\s-]hand\b", low
        ):
            add("refurbished", "Refurbished or used product", sentence, source)
        if re.search(r"international warranty|worldwide warranty|global warranty", low):
            add("international", "International warranty mentioned", sentence, source)
    return found


def _pending_confirmations(alternatives: dict, warranty) -> List[str]:
    fields = []
    for key, field in (("brand_suggestion", "brand"), ("model_suggestion", "model_code"), ("serial_suggestion", "serial_no")):
        if ((alternatives.get(key) or {}).get("status") or "") == "pending":
            fields.append(field)
    for field, item in (alternatives.get("vision_suggestions") or {}).items():
        if (item or {}).get("status") == "pending" and field not in fields:
            fields.append(field)
    if not getattr(warranty, "purchase_date", None) and "purchase_date" not in fields:
        fields.append("purchase_date")
    return [FIELD_NAMES.get(f, f.replace("_", " ")) for f in fields]


def five_lines(warranty, evidence: Optional[dict] = None, document: Optional[dict] = None,
               invoice_text: str = "", today: Optional[date] = None) -> Dict:
    """The card: five lines (dates, covered, not covered, if it breaks, original document), extra lines for
    warranty types found in the text, and the fields to confirm."""
    from .summary_engine import limits_from_text, service_route_lines

    today = today or datetime.utcnow().date()
    evidence = evidence or {}
    alternatives = getattr(warranty, "alternatives", None) or {}
    brand = (getattr(warranty, "brand", None) or "").strip()
    estimated = evidence.get("status") in ("estimated", "not_confirmed", "needs_check", "unreadable") or not brand
    tag = "Estimated, please check" if estimated else None
    terms = list(getattr(warranty, "terms", None) or [])
    exclusions = list(getattr(warranty, "exclusions", None) or [])
    claim_steps = list(getattr(warranty, "claim_steps", None) or [])
    types = detect_types(invoice_text, terms, exclusions)
    kinds = {t["type"] for t in types}
    lines: List[Dict] = []

    # 1. Dates.
    status = compute_warranty_status(
        purchase_date=getattr(warranty, "purchase_date", None),
        coverage_months=getattr(warranty, "coverage_months", None),
        expiry_date=getattr(warranty, "expiry_date", None),
        today=today,
    )
    expiry = status.get("expiry_date_used")
    if "no_warranty" in kinds and not getattr(warranty, "coverage_months", None):
        lines.append({"key": "dates", "text": "Your invoice says there is no warranty for this product.", "confirm": False})
    elif status["status"] == "expired":
        lines.append({"key": "dates", "text": f"Expired on {friendly_date(expiry)}.", "confirm": False})
    elif expiry:
        left = _months_left(today, datetime.fromisoformat(expiry).date())
        when = "less than a month left" if left == 0 else f"{left} month{'s' if left != 1 else ''} left"
        start = " (counted from installation - please confirm the installation date)" if "starts_at_installation" in kinds else ""
        lines.append({"key": "dates", "text": f"Covered until {friendly_date(expiry)} ({when}){start}.",
                      "confirm": bool(start) or bool(tag), "tag": tag})
    else:
        lines.append({"key": "dates", "text": "Please confirm your purchase date so we can work out the end date.", "confirm": True})

    # 2. What is covered: the first term that says what is covered.
    covered = next((t for t in terms if re.search(r"defect|repair|replace|cover|free of (?:cost|charge)|manufactur", t, re.I)
                    and not re.match(r"\s*standard coverage for \d+ months", t, re.I)), None)
    if covered:
        lines.append({"key": "covered", "text": f"Covered: {_first_sentence(covered)}", "confirm": bool(tag), "tag": tag})
    else:
        lines.append({"key": "covered", "text": "Please confirm what is covered: we have not found the brand's terms yet.", "confirm": True})

    # 3. What is not covered: grounded short limits, else the first exclusion as written.
    limits = limits_from_text(" ".join(exclusions), phone=is_phone(warranty)) if exclusions else []
    if limits:
        lines.append({"key": "not_covered", "text": "Not covered: " + " ".join(limits[:2]), "confirm": bool(tag), "tag": tag})
    elif exclusions:
        lines.append({"key": "not_covered", "text": f"Not covered: {_first_sentence(exclusions[0])}", "confirm": bool(tag), "tag": tag})
    else:
        lines.append({"key": "not_covered", "text": "Please confirm what is not covered: no exclusions found yet.", "confirm": True})

    # 4. If it breaks.
    route = service_route_lines(" ".join(claim_steps), brand or None)
    step = route[0] if route else (_first_sentence(claim_steps[0]) if claim_steps else None)
    if step:
        lines.append({"key": "if_it_breaks", "text": f"If it breaks: {step}", "confirm": False})
    else:
        who = brand or "the seller"
        lines.append({"key": "if_it_breaks", "text": f"If it breaks: contact {who} with your invoice and serial number.",
                      "confirm": not brand})

    # 5. The original document.
    if document and document.get("available"):
        lines.append({"key": "document", "text": f"Your original {document.get('kind_label', 'document').lower()}: "
                      f"{document.get('filename')}", "url": f"/documents/{document['id']}/file", "confirm": False})
    else:
        lines.append({"key": "document", "text": "Your original invoice is not saved here yet - add it under My documents.",
                      "confirm": True})

    extras = [{"type": t["type"], "text": t["text"], "source": t["source"], "source_sentence": t["source_sentence"]}
              for t in types if t["type"] != "extended_plan_offer"]
    return {
        "lines": lines,
        "extras": extras,
        "please_confirm": _pending_confirmations(alternatives, warranty),
        "estimated": bool(tag),
    }
