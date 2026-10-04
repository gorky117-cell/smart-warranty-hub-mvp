"""Manufacturer brand resolution over the OEM domain registry (`data/oem_domains.json`).

Replaces the old hardcoded 27-brand tuple in `ingestion.py`. Brands belong in the registry; this
module only adds matching rules:

- Registry keys ending in " India" are regional duplicates and resolve to the base name
  ("Samsung India" -> "Samsung"); case duplicates ("USHA"/"Usha") resolve to the first spelling.
- Multi-word names match as whole-word token sequences, longest first ("Bajaj Electricals" before
  "Bajaj").
- Names that are ordinary words or short codes (`AMBIGUOUS`) only match when written as a name in the
  source text (Title Case or ALL CAPS), never lower case ("nothing", "carrier", "noise").
- `RETAILERS` are sellers that also appear in the registry; they never resolve as a manufacturer from a
  seller line, only from a product line with no other brand.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .oem_domains import load_oem_domains

# Extra spellings that are not registry keys. Keep this tiny; new brands go in the registry.
ALIASES: Dict[str, str] = {
    "mi": "Xiaomi",
    "one plus": "OnePlus",
    "i phone": "Apple",
}

# Registry names that are ordinary words, people/places or 2-letter codes.
AMBIGUOUS = frozenset(
    {
        "nothing", "noise", "honor", "carrier", "singer", "sharp", "hero", "polar", "orient", "symphony",
        "butterfly", "pigeon", "glen", "kent", "titan", "surya", "cello", "prestige", "usha", "pioneer",
        "google", "tata", "mg", "mi", "hp", "lg", "kia", "tcl", "bpl", "hpl", "byd", "ifb", "msi", "cera",
        "candes", "eureka forbes", "anker", "boult", "casio", "fossil",
    }
)

RETAILERS = frozenset({"croma"})
# Lenders that appear on EMI invoices; never the product's maker.
NON_MAKERS = frozenset({"bajaj finserv"})

# Words that mark a line as a seller/shop line rather than a product line.
SELLER_MARKERS = (
    "store", "retail", "mall", "dealer", "distributor", "enterprises", "traders", "agencies",
    "pvt", "private limited", "ltd", "llp", "sold by", "seller", "outlet", "showroom", "digital",
)


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


@lru_cache(maxsize=1)
def _index() -> Tuple[Tuple[Tuple[str, ...], str], ...]:
    canonical_by_key: Dict[str, str] = {}
    for name in load_oem_domains().keys():
        base = re.sub(r"\s+india$", "", name.strip(), flags=re.IGNORECASE)
        key = " ".join(_tokens(base))
        if key and key not in canonical_by_key:
            canonical_by_key[key] = base
    for alias, target in ALIASES.items():
        canonical_by_key.setdefault(" ".join(_tokens(alias)), target)
    entries = [(tuple(key.split()), name) for key, name in canonical_by_key.items()]
    # Longest token sequence first so "bajaj electricals" wins over "bajaj".
    entries.sort(key=lambda item: (-len(item[0]), -len(" ".join(item[0]))))
    return tuple(entries)


def reset_cache() -> None:
    _index.cache_clear()


def brand_count() -> int:
    return len({name for _key, name in _index()})


def _written_as_name(original: str, key: Tuple[str, ...]) -> bool:
    """True when an ambiguous name appears in Title Case or ALL CAPS and is not used as a field
    label ("Carrier: Blue Dart")."""
    pattern = r"\b" + r"[\s\-]*".join(re.escape(token) for token in key) + r"\b"
    for match in re.finditer(pattern, original, re.IGNORECASE):
        words = re.findall(r"[A-Za-z0-9]+", match.group(0))
        if not all(word[:1].isupper() or word[:1].isdigit() for word in words):
            continue
        if re.match(r"\s*[:=]", original[match.end():]):
            continue
        return True
    return False


# A brand-like word followed by one of these is a place name ("MG Road", "Hero Honda Chowk").
ADDRESS_WORDS = frozenset(
    {
        # Not "tower"/"main"/"block": real products ("Bajaj Tower Fan") use them.
        "road", "rd", "street", "st", "marg", "nagar", "lane", "layout", "colony", "sector", "cross",
        "avenue", "chowk", "circle", "park", "complex", "plaza", "enclave", "vihar",
        "bagh", "gali", "bazar", "bazaar", "market", "junction", "flyover", "estate",
    }
)


def find_brands(text: str) -> List[str]:
    """All registry brands named in ``text``, in order of appearance, longest names first on overlap."""
    original = text or ""
    tokens = _tokens(original)
    if not tokens:
        return []
    taken = [False] * len(tokens)
    found: List[Tuple[int, str]] = []
    for key, name in _index():
        size = len(key)
        for start in range(0, len(tokens) - size + 1):
            if tuple(tokens[start:start + size]) != key or any(taken[start:start + size]):
                continue
            if set(tokens[start + size:start + size + 2]) & ADDRESS_WORDS:
                continue  # "MG Road", "Hero Honda Chowk" are addresses, not brands (fix run B6)
            if " ".join(key) in AMBIGUOUS and not _written_as_name(original, key):
                continue
            for i in range(start, start + size):
                taken[i] = True
            found.append((start, name))
    seen: List[str] = []
    for _pos, name in sorted(found):
        if name not in seen:
            seen.append(name)
    return seen


def is_seller_line(text: str) -> bool:
    low = f" {' '.join(_tokens(text))} "
    return any(f" {marker} " in low for marker in SELLER_MARKERS)


def is_retailer(name: Optional[str]) -> bool:
    return " ".join(_tokens(name or "")) in RETAILERS


def resolve_brand(product_line: Optional[str], seller_lines: Optional[List[str]] = None) -> Optional[str]:
    """Pick the manufacturer: a non-retailer brand in the product line wins; then a brand named in a
    seller line (e.g. "LG Authorized Store") unless it is a retailer; a retailer brand only when it is
    the sole brand in the product line (retailer own-label products)."""
    in_product = [name for name in find_brands(product_line or "") if not is_non_maker(name)]
    makers = [name for name in in_product if not is_retailer(name)]
    if makers:
        return makers[0]
    for line in seller_lines or []:
        for name in find_brands(line):
            if not is_retailer(name) and not is_non_maker(name):
                return name
    return in_product[0] if in_product else None


def is_non_maker(name: Optional[str]) -> bool:
    return " ".join(_tokens(name or "")) in NON_MAKERS
