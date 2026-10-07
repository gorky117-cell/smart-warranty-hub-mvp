"""Purchase details read from the invoice (batch 3 item 4): price, capacity/size, star rating, product type, and
the delivery region (city and state only - never the street, house, name or PIN code).

The region is used for climate and local-context care tips only after the customer agrees (consent recorded in
alternatives["delivery_region"]["consent"]); until then it is stored but not used.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# States and union territories of India -> display name.
_STATES = {
    "andhra pradesh": "Andhra Pradesh", "arunachal pradesh": "Arunachal Pradesh", "assam": "Assam", "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh", "goa": "Goa", "gujarat": "Gujarat", "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh", "jharkhand": "Jharkhand", "karnataka": "Karnataka", "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh", "maharashtra": "Maharashtra", "manipur": "Manipur", "meghalaya": "Meghalaya",
    "mizoram": "Mizoram", "nagaland": "Nagaland", "odisha": "Odisha", "orissa": "Odisha", "punjab": "Punjab",
    "rajasthan": "Rajasthan", "sikkim": "Sikkim", "tamil nadu": "Tamil Nadu", "telangana": "Telangana",
    "tripura": "Tripura", "uttar pradesh": "Uttar Pradesh", "uttarakhand": "Uttarakhand", "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal", "delhi": "Delhi", "new delhi": "Delhi", "nct of delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir", "jammu & kashmir": "Jammu and Kashmir", "ladakh": "Ladakh",
    "puducherry": "Puducherry", "pondicherry": "Puducherry", "chandigarh": "Chandigarh",
    "andaman and nicobar islands": "Andaman and Nicobar Islands", "lakshadweep": "Lakshadweep",
    "dadra and nagar haveli and daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
}
# Broad climate per state, in the bands the risk model already knows (hot, humid, dry, cold, coastal).
STATE_CLIMATE = {
    "Rajasthan": "dry", "Gujarat": "dry", "Haryana": "hot", "Delhi": "hot", "Punjab": "hot", "Uttar Pradesh": "hot",
    "Madhya Pradesh": "hot", "Bihar": "hot", "Jharkhand": "hot", "Chhattisgarh": "hot", "Telangana": "hot",
    "Andhra Pradesh": "coastal", "Tamil Nadu": "coastal", "Kerala": "humid", "Karnataka": "humid", "Goa": "coastal",
    "Maharashtra": "humid", "Odisha": "coastal", "West Bengal": "humid", "Puducherry": "coastal",
    "Andaman and Nicobar Islands": "coastal", "Lakshadweep": "coastal", "Assam": "humid", "Meghalaya": "humid",
    "Tripura": "humid", "Mizoram": "humid", "Manipur": "humid", "Nagaland": "humid", "Arunachal Pradesh": "humid",
    "Sikkim": "cold", "Himachal Pradesh": "cold", "Uttarakhand": "cold", "Jammu and Kashmir": "cold", "Ladakh": "cold",
    "Chandigarh": "hot", "Dadra and Nagar Haveli and Daman and Diu": "coastal",
}
_STATE_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(k) for k in _STATES), key=len, reverse=True)) + r")\b", re.IGNORECASE
)
# Address blocks that name where the product went (shipping first), and the "Place of supply" line.
_ADDRESS_HEADINGS = (
    re.compile(r"\b(?:ship(?:ping)?\s*(?:to|address)|deliver(?:y|ed)?\s*(?:to|address)|place\s+of\s+delivery)\b", re.I),
    re.compile(r"\b(?:bill(?:ing)?\s*(?:to|address)|buyer|customer\s+address|sold\s+to)\b", re.I),
)
_PLACE_OF_SUPPLY_RE = re.compile(r"\bplace\s+of\s+supply\b", re.I)
_STREET_WORDS = re.compile(
    r"\b(road|rd|street|st|lane|marg|nagar|sector|block|flat|house|apartment|apt|floor|plot|near|opp|colony|"
    r"society|tower|phase|village|post|tehsil|district|dist|address|buyer|customer|name)\b|\d",
    re.I,
)

_MONEY_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)", re.I)
_BARE_MONEY_RE = re.compile(r"(?<![\w.,])([0-9]{1,3}(?:,[0-9]{2,3})+\.\d{2}|[0-9]{3,7}\.\d{2})(?![\d,])")
_TOTAL_RE = re.compile(r"\b(?:grand\s+total|invoice\s+(?:value|total)|total\s+amount|amount\s+payable|net\s+payable)\b", re.I)

_CAPACITY_PATTERNS = (
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:ton|tons|tr)\b", re.I), "{} Ton"),
    (re.compile(r"\b(\d{2,4})\s*(?:l|ltr|litre|litres|liter|liters)\b", re.I), "{} L"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*kg\b", re.I), "{} kg"),
    (re.compile(r"\b(\d{2,3})\s*(?:inch|inches|in\b|\")", re.I), "{} inch"),
    (re.compile(r"\b(\d{2,4})\s*gb\s*(?:storage|rom)\b", re.I), "{} GB storage"),
    (re.compile(r"\b(\d{2,4})\s*(?:w|watt|watts)\b", re.I), "{} W"),
)
_STAR_RE = re.compile(r"\b([1-5])\s*[- ]?\s*star\b", re.I)
_TYPES = (
    (re.compile(r"\bwindow\b", re.I), "window"),
    (re.compile(r"\bsplit\b", re.I), "split"),
    (re.compile(r"\bportable\s+ac\b|\bportable\b(?=.*\bac\b)", re.I), "portable"),
    (re.compile(r"\bcassette\b", re.I), "cassette"),
    (re.compile(r"\bfront\s*load\b", re.I), "front load"),
    (re.compile(r"\btop\s*load\b", re.I), "top load"),
    (re.compile(r"\bsemi[- ]?automatic\b", re.I), "semi-automatic"),
    (re.compile(r"\bside\s+by\s+side\b", re.I), "side by side"),
    (re.compile(r"\bdouble\s+door\b", re.I), "double door"),
    (re.compile(r"\bsingle\s+door\b", re.I), "single door"),
    (re.compile(r"\bstorage\b(?=.*\b(?:geyser|water\s+heater)\b)", re.I), "storage"),
    (re.compile(r"\binstant\b(?=.*\b(?:geyser|water\s+heater)\b)", re.I), "instant"),
)


def _amount(raw: str) -> Optional[float]:
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    return value if 50 <= value <= 10_000_000 else None


def price_paid(text: str, item_line: Optional[str]) -> Optional[Dict[str, object]]:
    """The item's price from its own row (first amount on it), else the invoice total."""
    lines = (text or "").splitlines()
    if item_line:
        key = item_line[:20]
        for line in lines:
            if key and key in line:
                for regex in (_MONEY_RE, _BARE_MONEY_RE):
                    m = regex.search(line[line.find(key):])
                    value = _amount(m.group(1)) if m else None
                    if value:
                        return {"amount": value, "currency": "INR", "from": "item row"}
    for line in lines:
        if _TOTAL_RE.search(line):
            for regex in (_MONEY_RE, _BARE_MONEY_RE):
                found = [v for v in (_amount(x) for x in regex.findall(line)) if v]
                if found:
                    return {"amount": max(found), "currency": "INR", "from": "invoice total"}
    return None


def product_specs(product_text: Optional[str]) -> Dict[str, object]:
    text = product_text or ""
    out: Dict[str, object] = {}
    for regex, label in _CAPACITY_PATTERNS:
        m = regex.search(text)
        if m:
            number = m.group(1)
            out["capacity"] = label.format(number.rstrip("0").rstrip(".") if "." in number else number)
            break
    star = _STAR_RE.search(text)
    if star:
        out["star_rating"] = int(star.group(1))
    for regex, label in _TYPES:
        if regex.search(text):
            out["type"] = label
            break
    return out


def _city_before(line: str, state_start: int) -> Optional[str]:
    head = line[:state_start].rstrip(" ,-")
    parts = [p.strip() for p in re.split(r",|\s-\s", head) if p.strip()]
    if not parts:
        return None
    city = parts[-1]
    if _STREET_WORDS.search(city) or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,30}", city) or len(city.split()) > 3:
        return None
    return city.title()


def delivery_region(text: str) -> Optional[Dict[str, Optional[str]]]:
    """{"city", "state"} where the product was delivered, from the shipping (else billing) address block or
    the "Place of supply" line. Only these two values are returned; nothing else of the address is kept."""
    lines = (text or "").splitlines()
    for heading in _ADDRESS_HEADINGS:
        for idx, line in enumerate(lines):
            if not heading.search(line):
                continue
            for candidate in lines[idx: idx + 6]:
                m = _STATE_RE.search(candidate)
                if m:
                    state = _STATES[m.group(1).lower()]
                    return {"city": _city_before(candidate, m.start()), "state": state}
    for line in lines:
        if _PLACE_OF_SUPPLY_RE.search(line):
            m = _STATE_RE.search(line[_PLACE_OF_SUPPLY_RE.search(line).end():])
            if m:
                return {"city": None, "state": _STATES[m.group(1).lower()]}
    return None


def climate_for(region: Optional[Dict[str, object]]) -> Optional[str]:
    if not region:
        return None
    return STATE_CLIMATE.get(str(region.get("state") or ""))


def extract(text: str, item_line: Optional[str], product_text: Optional[str]) -> Dict[str, object]:
    """alternatives entries: "purchase_details" and "delivery_region" (when found)."""
    out: Dict[str, object] = {}
    details: Dict[str, object] = {}
    price = price_paid(text, item_line)
    if price:
        details["price"] = price
    details.update(product_specs(product_text or item_line))
    if details:
        out["purchase_details"] = details
    region = delivery_region(text)
    if region:
        out["delivery_region"] = {**region, "consent": None}
    return out


# Weather-based care tips in SWH's own words, by product line and climate band. Used only with the customer's
# consent to use their delivery city/state.
_CLIMATE_TIPS = {
    ("air_conditioner", "hot"): "Long, hot summers where you live mean heavy AC use: clean the filter every 2 weeks in summer and book a service before the hot months.",
    ("air_conditioner", "dry"): "Dust is common where you live: clean the AC filter every 2 weeks in summer and keep the outdoor unit free of dust and leaves.",
    ("air_conditioner", "humid"): "In humid weather, keep the AC's drain pipe clear so water does not drip indoors, and run it in dry mode on sticky days.",
    ("air_conditioner", "coastal"): "Salty sea air corrodes outdoor units faster: ask the technician to check the outdoor coil for rust at each service.",
    ("air_conditioner", "cold"): "Cover the outdoor unit during the cold months you do not use it, and have it checked before summer.",
    ("fridge", "hot"): "In very hot months, leave a hand's gap behind the fridge so it can release heat, and avoid opening it often.",
    ("fridge", "humid"): "In humid weather, wipe the door seal now and then so it does not grow mould and keeps closing tightly.",
    ("fridge", "coastal"): "Salty air can rust the back of a fridge: keep it a little away from the wall and wipe it down every few months.",
    ("washing_machine", "humid"): "In humid weather, leave the door open after washing so the drum dries and does not smell.",
    ("washing_machine", "coastal"): "In humid, salty air, leave the door open after washing and wipe the door seal dry.",
    ("water_heater", "hot"): "Hard water is common in many hot, dry areas: have the geyser descaled once a year.",
    ("water_heater", "dry"): "Hard water is common in dry areas: have the geyser descaled once a year.",
    ("water_heater", "cold"): "In cold months the geyser works hardest: switch it off when not needed and have the safety valve checked before winter.",
    ("smartphone", "humid"): "Humid weather can fog the camera and charging port: keep the phone dry and away from bathrooms.",
    ("laptop", "hot"): "Heat shortens battery life: keep the laptop out of hot cars and use it on a hard surface so air can flow.",
    ("tv", "coastal"): "Salty, humid air can damage electronics: use a voltage stabiliser and keep the TV's vents dust-free.",
    ("printer", "dry"): "In dry, hot weather ink dries faster: print a page every few days so the nozzles do not clog.",
}


def climate_tip(product_line: Optional[str], region: Optional[Dict[str, object]]) -> Optional[str]:
    """A weather tip for the product, only when the customer agreed to use their city/state."""
    if not region or region.get("consent") is not True:
        return None
    return _CLIMATE_TIPS.get((str(product_line or ""), climate_for(region) or ""))
