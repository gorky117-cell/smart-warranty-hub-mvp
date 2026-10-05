"""How a product is named for its owner: short clean name, optional nickname, a second line, an icon.

General for every product and brand: the name comes from the invoice's product title (marketplace titles
are cut at their first separator and stripped of sizes, specs and colours), with the brand in front, or
from brand + model when there is no usable title. Internal warranty IDs are never part of it; a short
support reference (`support_ref`) is for the downloaded PDF and admin views only.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Optional

# Marketplace titles: "Samsung Galaxy M17e 5G (Blitz Blue, 6GB RAM, 128GB Storage) | 50MP Camera ..."
_CUT = re.compile(r"\s*(?:\(|\[|\||,|;|\s[-–—]\s|\bwith\b|\bfor\b|\bcombo\b)", re.IGNORECASE)
_SPEC = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mb|mah|mp|hz|inch(?:es)?|in|cm|mm|l|ltr|litres?|liters?|kg|w|watts?|tons?|"
    r"stars?|ppm|v)\b|\b(?:ram|rom|storage|star|ton)\b|\"",
    re.IGNORECASE,
)
_COLOURS = re.compile(
    r"\b(?:black|white|silver|grey|gray|blue|red|green|gold|rose|pink|purple|violet|yellow|orange|brown|beige|"
    r"graphite|midnight|starlight|titanium|bronze|copper|navy|teal|mint|lavender|cream|ivory)\b",
    re.IGNORECASE,
)
_WORDS = 6
_SHORT_WORDS = 5
TYPE_LABELS = {
    "smartphone": "Phone", "laptop": "Laptop", "tv": "TV", "fridge": "Refrigerator",
    "air_conditioner": "Air conditioner", "washing_machine": "Washing machine", "water_heater": "Geyser",
    "printer": "Printer", "microwave": "Microwave", "fan": "Fan", "cooler": "Air cooler", "heater": "Heater",
    "inverter": "Inverter", "camera": "Camera", "router": "Router", "wearable": "Smartwatch", "audio": "Audio",
    "purifier": "Purifier", "kitchen_appliance": "Kitchen appliance", "appliance": "Appliance", "ev": "Vehicle",
}
ICONS = {
    "smartphone": "📱", "laptop": "💻", "tv": "📺", "fridge": "🧊", "air_conditioner": "❄️",
    "washing_machine": "🧺", "water_heater": "🚿", "printer": "🖨️", "microwave": "🍲", "fan": "🌀",
    "cooler": "💨", "heater": "🔥", "inverter": "🔋", "camera": "📷", "router": "📶", "wearable": "⌚",
    "audio": "🎧", "purifier": "💧", "kitchen_appliance": "🍳", "appliance": "🏠", "ev": "🚗",
}
DEFAULT_ICON = "📦"


def _clean(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -,.|")
    return "" if text.lower() in ("", "product", "n/a", "none", "null", "unknown") else text


def line_for(product_name: Optional[str], model_code: Optional[str]) -> Optional[str]:
    from .terms_cache import product_line

    return product_line(model_code, product_name)


def clean_title(title: Optional[str]) -> str:
    """The product part of a (marketplace) title, without sizes, specs or colours."""
    text = _clean(title)
    if not text:
        return ""
    head = _CUT.split(text, maxsplit=1)[0]
    if len(head.split()) < 2:  # "(Samsung) Galaxy M17e" or a cut too early: keep the whole title
        head = re.sub(r"[()\[\]|]", " ", text)
    head = _COLOURS.sub(" ", _SPEC.sub(" ", head))
    words = [w for w in re.sub(r"\s+", " ", head).strip(" -,.").split(" ") if w]
    return " ".join(words[:_WORDS])


def short_name(brand: Optional[str], product_name: Optional[str], model_code: Optional[str]) -> str:
    """"Samsung Galaxy M17e", "LG Refrigerator GL-T292RPZY", "Epson L3250"; never an internal ID."""
    brand = _clean(brand)
    model = _clean(model_code)
    title = clean_title(product_name)
    if title and brand and not title.lower().startswith(brand.lower()):
        title = f"{brand} {title}"
    if title and title.lower() != brand.lower():
        # A bare product type ("LG Refrigerator") gets its model so two products stay apart.
        if model and len(title.split()) <= 2 and model.lower() not in title.lower():
            title = f"{title} {model}"
        label = TYPE_LABELS.get(line_for(product_name, model_code) or "")
        if len(title.split()) > _SHORT_WORDS and label:
            # Long feature lists ("Frost-Free Smart Inverter Double Door"): brand + model or series + type.
            rest = title[len(brand):].split() if brand and title.lower().startswith(brand.lower()) else title.split()
            ident = model if model and len(model) <= 14 else (rest[0] if rest else "")
            title = " ".join(x for x in (brand, ident, label) if x)
        return title
    if brand or model:
        return " ".join(x for x in (brand, model) if x)
    label = TYPE_LABELS.get(line_for(product_name, model_code) or "")
    return label or "Your product"


def _date_text(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value[:10])
        except ValueError:
            return None
    if isinstance(value, (date, datetime)):
        return f"{value.day} {value.strftime('%b %Y')}"
    return None


def seller_from(alternatives) -> Optional[str]:
    candidates = (alternatives or {}).get("seller") if isinstance(alternatives, dict) else None
    if isinstance(candidates, str):
        candidates = [candidates]
    for raw in candidates or []:
        text = _clean(raw)
        if text:
            text = text if not text.isupper() else text.title()
            return text[:40].rstrip()
    return None


def subtitle(purchase_date, seller: Optional[str]) -> str:
    """Second line that tells two identical products apart: "Bought 5 May 2026 from Croma"."""
    when = _date_text(purchase_date)
    if when and seller:
        return f"Bought {when} from {seller}"
    if when:
        return f"Bought {when}"
    if seller:
        return f"Bought from {seller}"
    return "Purchase date not known yet"


def support_ref(warranty_id: Optional[str]) -> str:
    """Short reference for support ("Ref: 2CD9B3"); for the PDF and admin views, not the customer list."""
    return hashlib.sha1(str(warranty_id or "").encode("utf-8")).hexdigest()[:6].upper()


def describe(*, warranty_id, brand, product_name, model_code, purchase_date, alternatives=None,
             nickname: Optional[str] = None) -> dict:
    name = short_name(brand, product_name, model_code)
    line = line_for(product_name, model_code)
    nick = _clean(nickname)[:40] if nickname else ""
    return {
        "display_name": nick or name,
        "product_name_short": name,
        "nickname": nick or None,
        "subtitle": subtitle(purchase_date, seller_from(alternatives)),
        "icon": ICONS.get(line or "", DEFAULT_ICON),
        "type_label": TYPE_LABELS.get(line or ""),
        "support_ref": support_ref(warranty_id),
    }


def tell_apart(items: list) -> list:
    """Two products with the same name and second line (same model bought the same day from the same
    seller) get "(2)", "(3)" on the second line, in the order given (oldest first)."""
    seen: dict = {}
    for item in items:
        key = (item["display_name"].lower(), item["subtitle"].lower())
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            item["subtitle"] = f"{item['subtitle']} ({seen[key]})"
    return items
