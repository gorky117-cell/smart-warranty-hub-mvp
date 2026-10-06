"""Warranty terms as structured facts in SWH's own words (step 2 of the own-words run).

The brand's text is read to find facts; customers see only sentences written here, each fact carrying the
link to its source and the date it was checked. A fact is produced only when the brand's text (or the
customer's invoice) says it - nothing is assumed:

- period (months) and start rule (purchase or installation)
- per-part periods (compressor, motor, panel, battery, accessories, ...)
- extended or protection plans on the invoice, kept separate from the brand's warranty
- what is covered (manufacturing defects; free repairs)
- key exclusions, as SWH-worded categories
- claim route (authorized service centres, customer care, website/app, invoice needed)
- on-site or carry-in service; registration needed; pro-rata cover

Brands whose reuse policy is full_text_ok may also show their own wording (reuse_policy).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# (key, pattern in the brand's text, SWH wording). Order = order shown. Only matched keys are shown.
EXCLUSION_RULES = [
    ("power", r"lightning|voltage|surge|power fluctuation|electrical (?:supply|fault)", "Damage from power problems such as lightning, surges or voltage changes"),
    ("liquid", r"liquid|water|moisture|rain|humidity|spill", "Damage from water or other liquids"),
    ("physical", r"physical damage|accident|\bdrop(?:ped|s)?\b|breakage|broken|\bcrack(?:s|ed)?\b|\bdent(?:s|ed)?\b", "Accidental or physical damage"),
    ("unauthorized_repair", r"unauthori[sz]ed|tamper(?:ing|ed)? with the (?:product|unit|device|appliance)", "Repairs or changes by unauthorized people"),
    ("wear", r"wear and tear|wear & tear|normal wear", "Normal wear and tear"),
    ("consumables", r"consumable|filters?\b|bulbs?\b|lamps?\b|cartridges?\b|\bink\b|remote|accessor", "Consumable and replaceable parts"),
    ("misuse", r"misuse|improper use|negligen|abuse|not (?:used )?in accordance|contrary to the instructions", "Misuse, or use that does not follow the instructions"),
    ("installation", r"improper installation|incorrect installation|installation (?:by|not done)", "Problems caused by wrong installation"),
    ("commercial", r"commercial|industrial|rental|business use", "Commercial, industrial or rental use"),
    ("serial", r"serial (?:number|no)[^.]{0,60}(?:removed|altered|tampered|obliterat|illegible|defaced)"
               r"|(?:removed|altered|tampered|obliterated|defaced)[^.]{0,30}serial (?:number|no)", "Products whose serial number has been removed or changed"),
    ("natural", r"act(?:s)? of god|natural calamit|flood|fire|earthquake|riot|\bwar\b", "Fire, floods and other events beyond anyone's control"),
    ("pests", r"insect|rodent|pest|rat\b|cockroach|lizard", "Damage caused by insects or rodents"),
    ("transit", r"transit|transport|shifting|relocat", "Damage while moving or transporting the product"),
    ("cosmetic", r"cosmetic|plastic parts|glass parts|paint|scratch", "Cosmetic damage such as scratches"),
    ("software", r"software|virus|data loss|loss of data", "Software faults and data loss"),
]
_COVERS = [
    ("defects", r"defect|manufactur|faulty (?:material|workmanship)|workmanship", "Repairs or replacement of parts for manufacturing defects"),
    ("free", r"free of (?:charge|cost)|without (?:any )?charge|no charge", "Covered repairs are free of charge"),
]
_NEGATIVE = re.compile(r"not cover|does not|do not|not covered|exclud|void|not applicable|shall not|will not", re.I)
_WEAR_PARTS = [(r"camera lens", "camera lenses"), (r"batter(?:y|ies)", "batteries"), (r"display", "displays"),
               (r"screen", "screens"), (r"filters?\b", "filters"), (r"lamps?\b|bulbs?\b", "lamps and bulbs"),
               (r"gaskets?\b", "gaskets"), (r"rubber", "rubber parts"), (r"belts?\b", "belts"), (r"brush", "brushes")]
_POWER_WORDS = [(r"lightning", "lightning"), (r"surge", "power surges"),
                (r"abnormal voltage|voltage fluctuation|voltage variation|high voltage|low voltage|voltage", "voltage changes"),
                (r"power fluctuation|electrical (?:supply|fault)", "electrical supply problems")]
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "fifteen": 15, "thirty": 30}


def _months_text(months: int) -> str:
    if months and months % 12 == 0:
        years = months // 12
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{months} month{'s' if months != 1 else ''}"


def _fact(key: str, text: str, source_url: Optional[str], checked_on: Optional[str], **extra) -> Dict:
    return {"key": key, "text": text, "source_url": source_url, "checked_on": checked_on, **extra}


def build(
    *,
    brand: Optional[str],
    coverage_months: Optional[int],
    terms: List[str],
    exclusions: List[str],
    claim_steps: List[str],
    source_url: Optional[str] = None,
    checked_on: Optional[str] = None,
    invoice_text: str = "",
) -> Dict:
    """Structured facts from the brand's text (and the invoice for extended plans)."""
    from .warranty_card import detect_types

    who = (brand or "").strip() or "the brand"
    terms_text = " ".join(str(t) for t in terms or [])
    excl_text = " ".join(str(e) for e in exclusions or [])
    claim_text = " ".join(str(c) for c in claim_steps or [])
    all_low = f"{terms_text} {excl_text} {claim_text}".lower()
    types = detect_types(invoice_text, terms, exclusions + list(claim_steps or []))
    kinds = {t["type"] for t in types}
    src = dict(source_url=source_url, checked_on=checked_on)
    facts: Dict = {"source_url": source_url, "checked_on": checked_on}

    start = "installation" if "starts_at_installation" in kinds else "purchase"
    facts["start_rule"] = start
    if coverage_months:
        facts["period"] = _fact("period", f"Covered for {_months_text(int(coverage_months))} from the "
                                f"{'installation' if start == 'installation' else 'purchase'} date", **src,
                                months=int(coverage_months))
    facts["part_periods"] = []
    for t in types:
        if t["type"] == "part_period":
            part, _, period = t["text"].partition(": ")
            facts["part_periods"].append(_fact("part_period", f"{part} covered for {period}", **src, part=part))
    # Plans on the customer's own invoice: kept apart from the brand's warranty.
    facts["extended_plans"] = [
        _fact("extended_plan", "An extended warranty or protection plan is on your invoice. Its cover comes from "
              "the plan's provider, separately from the brand's warranty.", source_url=None, checked_on=None)
        for t in types if t["type"] == "extended_plan"
    ][:1]
    facts["covers"] = [_fact(key, text, **src) for key, pattern, text in _COVERS if re.search(pattern, terms_text, re.I)]
    # Exclusions: the exclusion list, plus sentences in the terms that say what is NOT covered
    # ("Warranty does not cover normal wear and tear").
    negative_terms = " ".join(t for t in terms or [] if _NEGATIVE.search(str(t)))
    scan = f"{excl_text} {negative_terms}"
    facts["exclusions"] = []
    for key, pattern, text in EXCLUSION_RULES:
        if re.search(pattern, scan, re.I):
            if key == "wear":  # name the parts the brand names, if any
                parts = [w for p, w in _WEAR_PARTS if re.search(p, scan, re.I)]
                if parts:
                    text = "Normal wear and tear of " + (", ".join(parts[:-1]) + " or " + parts[-1] if len(parts) > 1 else parts[0])
            elif key == "power":  # name only the power problems the brand names
                named = [w for p, w in _POWER_WORDS if re.search(p, scan, re.I)]
                text = "Damage from " + (", ".join(named[:-1]) + " or " + named[-1] if len(named) > 1 else named[0])
            facts["exclusions"].append(_fact(key, text, **src))
    matched = sum(1 for e in exclusions or [] if any(re.search(p, str(e), re.I) for _k, p, _t in EXCLUSION_RULES))
    facts["more_exclusions"] = bool(exclusions) and matched < len(exclusions)

    route = []
    if re.search(r"authori[sz]ed service|authori[sz]ed (?:repair|partner)", all_low):
        route.append(_fact("service_centre", f"Repairs are done at {who}'s authorized service centres", **src))
    elif re.search(r"service cent(?:er|re)|service partner", all_low):  # "authorized" only when the brand says so
        route.append(_fact("service_centre", f"Repairs are done at {who}'s service centres", **src))
    if re.search(r"call|toll[- ]free|customer care|helpline|contact centre|contact center|call cent", all_low):
        route.append(_fact("customer_care", f"Contact {who}'s customer care to raise a repair request", **src))
    if re.search(r"website|online|\bapp\b|portal|web form|e-?mail|whatsapp", all_low):
        route.append(_fact("online", f"A repair request can also be raised online through {who}", **src))
    if re.search(r"invoice|bill|proof of purchase|receipt", all_low):
        route.append(_fact("invoice_needed", "Keep your invoice - it is needed for a claim", **src))
    facts["claim_route"] = route
    facts["had_claim_text"] = bool(claim_steps)
    facts["service_mode"] = ("on_site" if "on_site" in kinds else "carry_in" if "carry_in" in kinds else None)
    facts["registration_needed"] = "registration_required" in kinds
    days = re.search(r"regist\w*[^.]{0,40}?within\s+(\d{1,3}|\w+)\s+days", all_low)
    facts["registration_days"] = (int(days.group(1)) if days and days.group(1).isdigit()
                                  else _NUMBER_WORDS.get(days.group(1)) if days else None)
    facts["pro_rata"] = "pro_rata" in kinds
    return facts


def customer_lists(facts: Dict, brand: Optional[str]) -> Dict[str, List[str]]:
    """The three lists customers see (terms / exclusions / claim steps), all in SWH's words."""
    who = (brand or "").strip() or "the brand"
    terms = []
    if facts.get("period"):
        terms.append(facts["period"]["text"] + ".")
    terms += [f["text"] + "." for f in facts.get("covers") or []]
    terms += [f["text"] + "." for f in facts.get("part_periods") or []]
    if facts.get("registration_needed"):
        days = facts.get("registration_days")
        terms.append(f"You need to register the product with {who}" + (f" within {days} days" if days else "") + ".")
    if facts.get("pro_rata"):
        terms.append("Part of the period is pro-rata: later on you may pay part of the repair cost.")
    if facts.get("service_mode") == "on_site":
        terms.append("Service is given at your home (on-site).")
    elif facts.get("service_mode") == "carry_in":
        terms.append("Take the product to a service centre for repairs (carry-in).")
    terms += [f["text"] for f in facts.get("extended_plans") or []]
    exclusions = [_not_covered(f) for f in facts.get("exclusions") or []]
    if facts.get("more_exclusions"):
        exclusions.append(f"Other limits apply - see {who}'s warranty page for the full list.")
    claim = [f["text"] + "." for f in facts.get("claim_route") or []]
    if not claim and facts.get("had_claim_text"):  # the brand gave claim steps we could not turn into facts
        claim = ["Keep your invoice and the product's serial number ready.",
                 f"Contact {who}'s customer care or an authorized service centre to raise a claim."]
    return {"terms": terms, "exclusions": exclusions, "claim_steps": claim}


_PLURAL_KEYS = {"consumables", "natural", "software"}


def _not_covered(fact: Dict) -> str:
    verb = "are" if fact["key"] in _PLURAL_KEYS or fact["text"].startswith(("Repairs", "Products", "Problems")) else "is"
    return f"{fact['text']} {verb} not covered."
