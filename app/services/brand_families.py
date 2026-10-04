"""Brand names shared by unrelated companies (Bajaj, Honda, Hero, ...).

The product on the invoice decides which company's warranty terms apply: a Bajaj mixer is Bajaj
Electricals, a Bajaj Pulsar is Bajaj Auto, and nothing is ever Bajaj Finserv (a lender). When the
segment cannot be told, or the family has no company for it, no OEM terms are used.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

_PATH = Path(__file__).resolve().parents[2] / "data" / "brand_families.json"

# Checked in this order; the first segment with a keyword hit wins. Vehicles first, so "motor" in
# "Bajaj Auto motorcycle" is not read as an appliance motor; "pump"/"mixer" stay appliances.
_SEGMENT_KEYWORDS = (
    ("two_wheeler", (
        "motorcycle", "motorbike", "two wheeler", "two-wheeler", "2 wheeler", "2w", "scooter", "scooty", "moped",
        "pulsar", "platina", "avenger", "dominar", "chetak", "ct 100", "ct100", "splendor", "passion", "glamour",
        "hf deluxe", "xtreme", "xpulse", "destini", "maestro", "pleasure", "activa", "dio", "shine", "unicorn",
        "hornet", "sp 125", "livo", "fz", "r15", "mt 15", "mt-15", "fascino", "ray zr", "aerox", "rx100",
    )),
    ("car", (
        "car", "suv", "sedan", "hatchback", "creta", "venue", "verna", "i20", "i10", "exter", "alcazar", "tucson",
        "city", "amaze", "elevate", "wr-v", "jazz", "nexon", "punch", "tiago", "tigor", "altroz", "harrier",
        "safari", "curvv",
    )),
    ("bicycle", ("bicycle", "cycle", "mtb", "e-cycle", "ecycle")),
    ("mobile", ("phone", "mobile", "smartphone", "feature phone")),
    ("audio", (
        "speaker", "soundbar", "receiver", "amplifier", "av receiver", "headphone", "earphone", "keyboard",
        "piano", "guitar", "drum", "synthesizer",
    )),
    ("industrial", ("transformer", "switchgear", "industrial motor", "alternator", "traction", "cable drum")),
    ("home_appliance", (
        "fan", "mixer", "grinder", "juicer", "blender", "food processor", "iron", "geyser", "water heater",
        "heater", "cooler", "kettle", "toaster", "induction", "cooktop", "chimney", "hob", "oven", "otg",
        "microwave", "lamp", "bulb", "led", "light", "batten", "tube light", "downlight", "emergency light",
        "air conditioner", "ac", "refrigerator", "fridge", "washing machine", "purifier", "inverter",
        "stabilizer", "stabiliser", "pump", "sewing machine", "television", "tv", "rice cooker", "sandwich maker",
        "air fryer", "vacuum", "hair dryer", "trimmer", "appliance", "kitchen_appliance", "water_heater",
        "air_conditioner", "washing_machine",
    )),
)
_CATEGORY_SEGMENTS = {
    "mobile": "mobile", "smartphone": "mobile", "audio": "audio", "appliance": "home_appliance",
    "kitchen_appliance": "home_appliance", "fan": "home_appliance", "heater": "home_appliance",
    "water_heater": "home_appliance", "cooler": "home_appliance", "inverter": "home_appliance",
    "fridge": "home_appliance", "tv": "home_appliance", "air_conditioner": "home_appliance",
    "washing_machine": "home_appliance", "microwave": "home_appliance", "purifier": "home_appliance",
}


@dataclass(frozen=True)
class OemEntity:
    family: Optional[str]  # shared brand name, or None when the brand is not shared
    segment: Optional[str]
    company: Optional[str]  # registry name whose terms apply; None means "no OEM terms"


@lru_cache(maxsize=1)
def _load() -> Dict[str, dict]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"families": {}, "aliases": {}}


def family_of(brand: Optional[str]) -> Optional[str]:
    data = _load()
    key = (brand or "").strip().lower()
    if not key:
        return None
    for alias, family in (data.get("aliases") or {}).items():
        if alias.lower() == key:
            return family
    for family in data.get("families") or {}:
        if family.lower() == key:
            return family
    return None


def product_segment(*texts: Optional[str]) -> Optional[str]:
    """Segment from product name, model and category text; None when it cannot be told."""
    for text in texts:
        if text and text.strip().lower() in _CATEGORY_SEGMENTS:
            return _CATEGORY_SEGMENTS[text.strip().lower()]
    hay = " ".join(t for t in texts if t).lower()
    for segment, words in _SEGMENT_KEYWORDS:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", hay) for w in words):
            return segment
    return None


def resolve_oem_entity(
    brand: Optional[str],
    *,
    product_name: Optional[str] = None,
    model_code: Optional[str] = None,
    category: Optional[str] = None,
) -> OemEntity:
    family = family_of(brand)
    if not family:
        return OemEntity(family=None, segment=None, company=brand)
    segment = product_segment(product_name, model_code, category)
    company = ((_load().get("families") or {}).get(family) or {}).get(segment) if segment else None
    return OemEntity(family=family, segment=segment, company=company)
