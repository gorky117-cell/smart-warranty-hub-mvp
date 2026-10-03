"""Product-scoped base warranty duration selection (work plan step 8).

Replaces `max(durations)` when merging OEM terms sources. A duration is used only when the sentence
that states it:

- is base-warranty wording ("warranty", "guarantee", "coverage", or a "<product> - N months" list row),
- is not an optional/extended/paid plan (those are returned separately), not an installation/demo or
  exchange period, and not a component/part-only warranty,
- does not name a different product family than the one being looked up (watch/buds/TV lines on a page
  that also covers phones), and does not name a different country than the lookup region,
- comes from a source that mentions the product, model or category somewhere.

Among qualifying sentences the one that names the product/model wins, then the value most sentences
agree on, then the highest-ranked source. The largest number never wins by being largest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .warranty_parser import _EXTENDED_PLAN_MARKERS, duration_candidates

_GENERATED_RE = re.compile(r"^(standard coverage for \d+ months from purchase date|minimum coverage enforced for region)", re.I)

_EXTENDED_MARKERS = tuple(_EXTENDED_PLAN_MARKERS) + (
    "additional", "care+", "care plus", "protection", "extended", "upgrade", "offer", "optional", "paid",
)
_NON_WARRANTY_MARKERS = ("installation", "demo", "exchange", "return", "delivery", "emi", "trial", "refund")
_COMPONENT_MARKERS = (
    "part warranty", "parts warranty", "only part", "compressor", "motor", "panel", "battery", "adapter",
    "charger", "drum", "lamp", "printhead", "print head", "magnetron", "inverter",
)
_BASE_WORDS = ("warranty", "guarantee", "coverage", "covered", "covers")
_STRONG_BASE = (
    "standard warranty", "limited warranty", "manufacturer", "warranty period", "from the date of purchase",
    "from purchase", "from date of purchase", "warranty of", "warranty for",
)

FAMILY_WORDS: Dict[str, Tuple[str, ...]] = {
    "mobile": ("mobile", "mobiles", "phone", "phones", "smartphone", "smartphones", "handset", "handsets", "cellphone"),
    "tablet": ("tablet", "tablets"),
    "wearable": ("watch", "watches", "buds", "earbuds", "fitness", "wearable", "wearables"),
    "audio": ("speaker", "speakers", "soundbar", "headphone", "headphones", "earphone", "earphones", "audio"),
    "tv": ("tv", "tvs", "television", "televisions", "oled", "qled", "projector", "monitor", "monitors"),
    "computer": ("laptop", "laptops", "notebook", "notebooks", "pc", "desktop", "chromebook", "computer"),
    "printer": ("printer", "printers", "ink", "toner", "scanner"),
    "appliance": (
        "refrigerator", "refrigerators", "fridge", "washing", "washer", "dryer", "microwave", "oven", "dishwasher",
        "ac", "conditioner", "conditioners", "geyser", "heater", "purifier", "vacuum", "appliance", "appliances",
        "cooler", "chimney", "fan", "fans",
    ),
    "ev": ("scooter", "scooters", "vehicle", "vehicles", "motorcycle", "bike", "car", "ev"),
    "accessory": ("accessories", "accessory", "remote", "handsfree", "glasses", "cable"),
}
CATEGORY_FAMILIES: Dict[str, Set[str]] = {
    "mobile": {"mobile"},
    "appliance": {"appliance"},
    "ev": {"ev"},
    "electronics": {"tv", "computer", "printer", "audio", "tablet"},
    "general": set(),
}
COUNTRY_WORDS: Dict[str, Tuple[str, ...]] = {
    "IN": ("india",),
    "US": ("united states", "usa", "u.s."),
    "UK": ("united kingdom", "uk", "britain"),
    "GB": ("united kingdom", "uk", "britain"),
    "AE": ("uae", "emirates", "dubai"),
    "SG": ("singapore",),
    "AU": ("australia",),
    "CA": ("canada",),
}


@dataclass
class DurationContext:
    category: str = "general"  # terms_lookup._normalize_category() value
    model_code: Optional[str] = None
    product_name: Optional[str] = None
    region: Optional[str] = None
    # False when the user chose the page for this product (manual URL), which is itself the context.
    require_source_context: bool = True


@dataclass
class DurationChoice:
    months: Optional[int]
    evidence: Optional[str]
    optional_plans: List[str]


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9+]+", (text or "").lower())


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _families_in(tokens: Iterable[str]) -> Set[str]:
    token_set = set(tokens)
    return {family for family, words in FAMILY_WORDS.items() if token_set.intersection(words)}


def _target(context: DurationContext) -> Tuple[Set[str], List[str]]:
    families = set(CATEGORY_FAMILIES.get(context.category, set()))
    families |= _families_in(_tokens(context.product_name or ""))
    models = [m for m in {_alnum(context.model_code or "")} if len(m) >= 3]
    return families, models


def _mentions_target(text: str, families: Set[str], models: List[str]) -> bool:
    if families & _families_in(_tokens(text)):
        return True
    flat = _alnum(text)
    return any(model in flat for model in models)


def _other_country(sentence_low: str, region: Optional[str]) -> bool:
    country = (region or "").upper().split("-")[0]
    if country not in COUNTRY_WORDS:
        return False
    padded = f" {' '.join(_tokens(sentence_low))} "
    for code, words in COUNTRY_WORDS.items():
        if code == country or set(words) & set(COUNTRY_WORDS[country]):
            continue
        if any(f" {' '.join(_tokens(word))} " in padded for word in words):
            return True
    return False


def _classify(sentence: str, context: DurationContext, families: Set[str], models: List[str]) -> Tuple[str, int]:
    """Return (kind, score). kind: base | extended | component | skip."""
    low = sentence.lower().strip()
    if _GENERATED_RE.match(low):
        return "skip", 0
    if any(marker in low for marker in _EXTENDED_MARKERS):
        return "extended", 0
    toks = _tokens(low)
    has_base_word = any(word in toks for word in _BASE_WORDS) or "warranty" in low
    if any(marker in low for marker in _NON_WARRANTY_MARKERS) and not has_base_word:
        return "skip", 0
    present = _families_in(toks)
    names_target = _mentions_target(sentence, families, models)
    if present and not names_target and (families or present - {"accessory"}):
        return "skip", 0  # about another product family
    if _other_country(low, context.region):
        return "skip", 0
    if any(marker in low for marker in _COMPONENT_MARKERS):
        return "component", 0
    list_row = bool(re.match(r"^\W*[a-z][\w &/()+.-]{1,40}\s*[-–:]\s*\d", low)) and names_target
    if not (has_base_word or list_row):
        return "skip", 0
    names_model = any(model in _alnum(sentence) for model in models)
    score = 1 + (5 if names_model else 3 if names_target else 0) + (2 if any(p in low for p in _STRONG_BASE) else 0)
    return "base", score


def _source_text(result: Any) -> str:
    parts = [result.source_url or "", result.raw_text or ""]
    parts += list(result.terms or []) + list(result.exclusions or []) + list(result.claim_steps or [])
    parts += [c.get("sentence", "") for c in (getattr(result, "duration_candidates", None) or [])]
    return "\n".join(parts)


def _candidates_for(result: Any) -> List[Dict[str, Any]]:
    stored = list(getattr(result, "duration_candidates", None) or [])
    if stored:
        return stored
    # Results built without parser candidates (cache rows, tests): read the sentences we do have.
    return duration_candidates("\n".join(list(result.terms or []) + [result.raw_text or ""]))


def select_duration(results: List[Any], context: Optional[DurationContext]) -> DurationChoice:
    """Choose the base warranty duration across ranked source results (best source first)."""
    if context is None:
        # Legacy callers without product context: highest-ranked source's parsed duration.
        first = next((r.duration_months for r in results if r.duration_months), None)
        return DurationChoice(first, None, [])

    families, models = _target(context)
    scored: List[Tuple[int, int, int, Dict[str, Any], str]] = []  # (score, -rank, -pos, cand, url)
    optional: List[str] = []
    fallback: Optional[int] = None
    for rank, result in enumerate(results):
        needs_context = context.require_source_context and (families or models)
        if needs_context and not _mentions_target(_source_text(result), families, models):
            continue  # source never mentions this product/category
        cands = _candidates_for(result)
        real = [c for c in cands if not _GENERATED_RE.match(c.get("sentence", "").lower().strip())]
        if not real and result.duration_months and fallback is None:
            fallback = result.duration_months  # no sentence evidence available; parser value only
        for pos, cand in enumerate(real):
            kind, score = _classify(cand["sentence"], context, families, models)
            if kind == "extended":
                optional.append(cand["sentence"])
            elif kind == "base":
                scored.append((score, -rank, -pos, cand, result.source_url or ""))
    optional = list(dict.fromkeys(optional))
    if not scored:
        return DurationChoice(fallback, None, optional)
    support: Dict[int, int] = {}
    for _score, _rank, _pos, cand, _url in scored:
        support[cand["months"]] = support.get(cand["months"], 0) + 1
    best = max(scored, key=lambda item: (item[0], support[item[3]["months"]], item[1], item[2]))
    evidence = f"{best[3]['sentence']} [{best[4]}]" if best[4] else best[3]["sentence"]
    return DurationChoice(best[3]["months"], evidence, optional)
