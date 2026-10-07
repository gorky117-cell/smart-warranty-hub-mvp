import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import Artifact, ArtifactType
from ..storage import generate_id, store
from .ocr import extract_text_with_meta
from . import brand_registry

_PRODUCT_TERMS = (
    "ac", "air conditioner", "battery", "camera", "desktop", "dishwasher", "fridge",
    "geyser", "headphone", "laptop", "microwave", "mobile", "monitor", "notebook",
    "phone", "power bank", "printer", "refrigerator", "router", "scooter", "speaker",
    "tablet", "television", "tv", "washing machine",
)

_LINE_NOISE_TERMS = (
    "amount", "bank", "buyer", "cgst", "declaration", "delivery", "dispatch", "email",
    "gst", "gstin", "hsn", "ifsc", "invoice", "jurisdiction", "original for recipient",
    "pan", "payment", "recipient", "rupees", "sgst", "state", "tax", "terms", "total",
)

_RETAILER_MARKERS = (
    "flipkart",
    "amazon",
    "croma",
    "reliance digital",
    "vijay sales",
    "tatacliq",
    "jiomart",
    "myntra",
    "snapdeal",
    "meesho",
    "mall",
    "retail",
    "store",
    "traders",
    "trade centre",
)

_FIELD_LABEL_NOISE = (
    "ack date", "ack no", "address", "bill from", "bill to", "buyer", "customer",
    "description", "description of goods", "dispatch", "e-way", "gst", "gstin",
    "invoice", "irn", "original for recipient", "payment", "recipient", "seller",
    "ship to", "sold by", "supplier", "tax invoice", "terms", "total",
)

_ADDRESS_MARKERS = (
    "adjacent", "billing address", "city", "country", "dehradun", "district",
    "gurgaon", "haryana", "kattigenahalli", "landmark", "manesar", "nagar",
    "near", "pincode", "place of delivery", "place of supply", "postal",
    "road", "ship to", "shipping address", "state code", "state/ut", "street",
    "survey no", "tehsil", "uttarakhand", "village", "vinayak",
)

_SPEC_ONLY_PATTERNS = (
    r"^ip\s*\d{2,3}$",
    r"^\d+(?:\.\d+)?\s*(mah|ah|wh|w|kw|v|hz|inch|inches|cm|mm|kg|l|litre|liter|gb|tb)$",
    r"^\d+(?:\.\d+)?\s*(mp|megapixel|hz|mah|gb|tb)\b",
    r"^(refresh\s+rate|resolution|capacity|colour|color|size|variant)\b",
    r"^\d+\s*(no|nos|pcs|piece|pieces|qty|quantity)$",
    r"^\d{1,3}$",
    # Processor names are specs of laptops and phones, never the product's model (run 3 global check).
    r"^i[3579]-?\d{4,5}[a-z]{0,2}$",
    r"^(?:intel|amd|ryzen|core|celeron|pentium|athlon|snapdragon|helio|dimensity|exynos|tensor)\b",
)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _looks_like_seller_text(value: str) -> bool:
    low = (value or "").strip().lower()
    if not low:
        return True
    if low in ("tax", "tax invoice", "invoice", "bill", "receipt", "cash memo"):
        return True
    if low.startswith(("seller", "sold by", "merchant", "supplier", "retailer")):
        return True
    return any(marker in low for marker in _RETAILER_MARKERS)


# Invoice field labels, used to spot label lines whose label OCR garbled ("Band: Apple", "Modet X1").
_FIELD_LABELS = (
    "brand", "model", "serial", "imei", "date", "invoice", "warranty", "colour", "color", "price",
    "quantity", "seller", "buyer", "gstin", "total", "make", "mrp",
)
_LABEL_PREFIX_RE = re.compile(r"^\s*\W?\s*([A-Za-z]{3,9})\b\s*([:\-.]?)\s*(\S.*)$")
# Labels OCR garbles most; for these a label without a colon still counts ("Band Sony").
_IDENTITY_LABELS = ("brand", "model", "serial")


# First words of an item title that are not a maker's name.
_TITLE_NON_BRAND_WORDS = frozenset({
    "the", "new", "item", "items", "product", "description", "goods", "qty", "total", "smart", "digital",
    "wireless", "bluetooth", "portable", "automatic", "electric", "original", "combo", "pack", "set",
})

# A field label inside a joined product line: "Samsung Galaxy S24 Ultra Model Code: SM-S928B".
_EMBEDDED_FIELD_RE = re.compile(
    r"\s+(?:model|serial|imei|colou?r|warranty|invoice)(?:\s*(?:code|no\.?|number|#))?\s*[:\-#]",
    re.IGNORECASE,
)


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _field_label(word: str) -> Optional[str]:
    """The invoice field label ``word`` is, or is one OCR slip away from ("band" -> "brand")."""
    low = word.lower()
    if low in _FIELD_LABELS:
        return low
    if len(low) < 4:
        return None
    for label in _FIELD_LABELS:
        if len(label) >= 4 and abs(len(label) - len(low)) <= 1 and _edit_distance(low, label) <= 1:
            return label
    return None


def _labelled_line(value: str) -> Optional[Tuple[str, str]]:
    """(label, value) when the line starts with a field label, exact or misread; else None.
    A colon or dash after the word is not required because OCR often drops it ("Band Sony")."""
    match = _LABEL_PREFIX_RE.match(_normalize_spaces(value))
    if not match:
        return None
    word, separator, rest = match.group(1), match.group(2), match.group(3).strip()
    label = _field_label(word)
    if not label or not rest:
        return None
    if label == "brand" and not separator and rest.lower().startswith("new"):
        return None  # "Brand new ..." is a description
    if not separator and label not in _IDENTITY_LABELS:
        return None  # "Data Cable" / "Color Black Edition" are product lines, not "Date:" / "Color:"
    return label, rest


def _is_boilerplate_line(value: str) -> bool:
    low = _normalize_spaces(value).lower()
    if not low:
        return True
    if low.startswith("[ocr note]"):
        return True
    if "file not found" in low or "ocr note" in low:
        return True
    if any(marker in low for marker in _FIELD_LABEL_NOISE):
        return True
    if _looks_like_address_text(value):
        return True
    return False


def _is_spec_only(value: str) -> bool:
    text = _normalize_spaces(value).strip(":-|").lower()
    if not text:
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _SPEC_ONLY_PATTERNS)


def _contains_product_term(value: str) -> bool:
    text = _normalize_spaces(value).lower()
    if not text:
        return False
    for term in _PRODUCT_TERMS:
        words = [re.escape(part) for part in term.split()]
        pattern = r"\b" + r"\s+".join(words) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _has_product_signal(value: str) -> bool:
    text = _normalize_spaces(value)
    return bool(_canonical_oem(text) or _contains_product_term(text.lower()))


def _looks_like_address_text(value: str) -> bool:
    text = _normalize_spaces(value)
    low = text.lower()
    if not low:
        return True
    hard_markers = (
        "shipping address", "billing address", "place of supply", "place of delivery",
        "state/ut", "state code",
    )
    if any(marker in low for marker in hard_markers):
        return True
    marker_hits = sum(1 for marker in _ADDRESS_MARKERS if marker in low)
    has_pin = bool(re.search(r"\b\d{5,6}\b", low))
    has_plot_or_house = bool(re.search(r"\b\d+/\d+(?:/\d+)?\b", low))
    many_commas = text.count(",") >= 2
    if marker_hits >= 2:
        return True
    if marker_hits and (has_pin or has_plot_or_house or many_commas):
        return True
    if has_pin and many_commas:
        return True
    if _has_product_signal(text):
        return False
    return False


def _strip_invoice_table_prefix(value: str) -> str:
    """Remove OCR-merged table headers before product identity scoring."""
    text = _normalize_spaces(value)
    low = text.lower()
    if "description" not in low:
        return text

    named = brand_registry.find_brands(text)
    oem_pattern = "|".join(
        r"[\s\-]*".join(re.escape(part) for part in re.findall(r"[A-Za-z0-9]+", name))
        for name in sorted(named, key=len, reverse=True)
    )
    if oem_pattern:
        for match in re.finditer(rf"\b(?:{oem_pattern})\b", text, re.IGNORECASE):
            prefix = text[: match.start()].lower()
            if any(marker in prefix for marker in ("description", "unit price", "net amount", "tax rate")):
                candidate = text[match.start():].strip(" :-|")
                if _has_product_signal(candidate):
                    return candidate

    term_pattern = "|".join(re.escape(term) for term in sorted(_PRODUCT_TERMS, key=len, reverse=True))
    if term_pattern:
        for match in re.finditer(rf"\b(?:{term_pattern})\b", text, re.IGNORECASE):
            prefix = text[: match.start()].lower()
            if "description" not in prefix:
                continue
            candidate = text[match.start():].strip(" :-|")
            if _has_product_signal(candidate):
                return candidate

    return text


def _canonical_oem(value: str) -> Optional[str]:
    """Manufacturer named in ``value``, resolved over the OEM domain registry."""
    return brand_registry.resolve_brand(value)


def _clean_brand_candidate(raw: str) -> Optional[str]:
    text = _normalize_spaces(raw).strip(":-|")
    if not text:
        return None
    if _is_boilerplate_line(text) or _is_spec_only(text) or _looks_like_address_text(text):
        return None
    # Remove noisy prefixes that often appear in OCR.
    text = re.sub(r"^(brand|make)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(seller|sold by|merchant|supplier|retailer)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    # Stop at other field labels.
    text = re.split(r"\b(model|invoice|serial|imei|warranty|purchase date|date|gstin)\b", text, flags=re.IGNORECASE)[0]
    text = _normalize_spaces(text).strip(":-|")
    if len(text) < 2:
        return None
    if _looks_like_seller_text(text) or _looks_like_address_text(text):
        return None
    # Trim common legal suffixes.
    text = re.sub(r"\s*(pvt\.?|ltd\.?|private|limited|inc\.?|llc|corp\.?).*$", "", text, flags=re.IGNORECASE).strip()
    if len(text) < 2:
        return None
    if _is_boilerplate_line(text) or _is_spec_only(text) or _looks_like_address_text(text):
        return None
    return text.title()


def _clean_seller_candidate(raw: str) -> Optional[str]:
    text = _normalize_spaces(raw).strip(":-|")
    if not text:
        return None
    text = re.split(
        r"\b(invoice|order|bill to|buyer|delivery note|mode/terms|gstin|description of goods|hsn|quantity|rate|amount)\b",
        text,
        flags=re.IGNORECASE,
    )[0]
    text = _normalize_spaces(text).strip(":-|")
    low = text.lower()
    if len(text) < 3 or low in ("tax", "tax invoice", "invoice", "bill", "receipt"):
        return None
    if _is_boilerplate_line(text) or _is_spec_only(text) or _has_product_signal(text) or _looks_like_address_text(text):
        return None
    if any(term in low for term in ("shop no", "state name", "place of supply", "contact", "e-mail", "email")):
        return None
    return text.title()


def _logical_invoice_lines(lines: List[str]) -> List[str]:
    """Join wrapped invoice item descriptions before product identity scoring."""
    logical: List[str] = []
    current: Optional[str] = None

    def flush_current() -> None:
        nonlocal current
        if current:
            logical.append(current)
            current = None

    def is_standalone_item_marker(value: str) -> bool:
        return bool(re.fullmatch(r"\d{1,3}[\.\)]?", value))

    stop_pattern = re.compile(
        r"^(?:invoice\s+date|order\s+date|shipping charges?|total|subtotal|taxable|igst|cgst|sgst|amount|grand total)\b",
        re.IGNORECASE,
    )
    field_line_pattern = re.compile(
        r"^(?:invoice|inv|bill|order|date|dated|gstin|warranty|sold by|seller|buyer|ship to|bill to)\b[^:\-]{0,20}[:\-]",
        re.IGNORECASE,
    )
    continuation_pattern = re.compile(
        r"\b("
        r"gb|ram|storage|hz|refresh|battery|mah|charger|os upgrades?|ai|gemini|"
        r"model|printer|mobile|phone|galaxy|laptop|fridge|refrigerator|washing|"
        r"microwave|geyser|heater|camera|router|inverter|purifier|speaker|"
        r"B0[A-Z0-9]+|[A-Z0-9]{2,}[-+][A-Z0-9\-+]+"
        r")\b",
        re.IGNORECASE,
    )

    for raw in lines:
        clean = _normalize_spaces(raw)
        if not clean:
            continue

        if is_standalone_item_marker(clean):
            flush_current()
            current = clean
            continue

        starts_item = bool(re.match(r"^\d+[\.\)]?\s+", clean))
        product_bearing = _has_product_signal(clean)
        likely_item_start = product_bearing and not stop_pattern.search(clean) and not _is_boilerplate_line(clean)
        if (starts_item and product_bearing) or (likely_item_start and not current):
            flush_current()
            current = clean
            continue

        if current:
            if (stop_pattern.search(clean) and not _has_product_signal(clean)) or field_line_pattern.match(clean):
                # A field line ("Invoice No: INV-77", "Date: 02-03-2025") never continues a product line.
                flush_current()
                logical.append(clean)
                continue
            if (
                "|" in clean
                or clean.startswith("(")
                or clean.endswith(("(", ")"))
                or continuation_pattern.search(clean)
            ):
                current = f"{current} {clean}"
                continue
            flush_current()

        logical.append(clean)

    flush_current()
    return logical


def _clean_product_name_candidate(raw: str) -> Optional[str]:
    text = _strip_invoice_table_prefix(raw).strip(":-|")
    if not text or _is_boilerplate_line(text):
        return None
    if _labelled_line(text):
        return None  # a field line such as "Band: Apple" (misread "Brand:") is never a product name
    text = _EMBEDDED_FIELD_RE.split(text, maxsplit=1)[0]
    # Marketplace codes after the title: "... (Black, 3 Jars) FSN: MIXEFZ3W... HSN/SAC: 85094010".
    text = re.split(r"\s+(?:FSN|ASIN|HSN/SAC|HSN|SAC)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = re.sub(r"^\d+[\.\)]?\s*", "", text)
    text = re.sub(r"\bIP\s*\d{2,3}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bB0[A-Z0-9]{6,}\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHSN\s*:?\s*\d+.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*(?:no|nos|pcs|piece|pieces|qty|quantity)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b.*$", "", text)
    text = _normalize_spaces(text).strip(":-|")
    if not text or _is_spec_only(text) or _looks_like_address_text(text):
        return None
    return text


def _infer_product_category(*, product_name: Optional[str], model_code: Optional[str], lowered_text: str) -> Optional[str]:
    hay = " ".join([product_name or "", model_code or "", lowered_text]).lower()
    tokens = set(re.findall(r"[a-z0-9]+", hay))
    if tokens & {"phone", "phones", "mobile", "smartphone", "iphone", "android", "galaxy"}:  # not "headphones"
        return "mobile"
    if tokens & {"headphone", "headphones", "earphones", "earbuds", "speaker", "soundbar"}:
        return "electronics"
    if "printer" in tokens:
        return "electronics"
    if any(k in tokens for k in ("tv", "oled", "qled", "bravia")):
        return "electronics"
    if any(k in tokens for k in ("laptop", "notebook", "macbook", "monitor", "router", "camera")):
        return "electronics"
    if (
        "ac" in tokens
        or any(
            k in hay
            for k in (
                "air conditioner",
                "fridge",
                "refrigerator",
                "washing",
                "microwave",
                "geyser",
                "air fryer",
                "mixer",
                "grinder",
                "ceiling fan",
                "whirlpool",
                "bosch",
                "wm-",
                "fr-",
            )
        )
    ):
        return "appliance"
    if (
        "ev" in tokens
        or "battery" in tokens
        or "batt" in tokens
        or any(k in tokens for k in ("scooter", "motor", "car", "ather", "450x", "nexon"))
    ):
        return "ev"
    return None


def _infer_invoice_region(text: str) -> Optional[str]:
    low = (text or "").lower()
    india_markers = (
        "tax invoice",
        "gstin",
        "cgst",
        "sgst",
        "igst",
        "hsn",
        "place of supply",
        "state/ut",
        "inr",
        "amazon.in",
        "india",
    )
    marker_hits = sum(1 for marker in india_markers if marker in low)
    has_indian_pin = bool(re.search(r"\b[1-9]\d{5}\b", low))
    if marker_hits >= 2 or (marker_hits and has_indian_pin):
        return "IN"
    return None


# Where the description of a numbered table row ends: HSN/SAC or FSN codes, or the first price column.
_ROW_TAIL_RE = re.compile(
    r"\s+\(?\s*(?:HSN|SAC|HSN/SAC)\b|\s+FSN\s*:|\s+\d{1,3}(?:,\d{2,3})+(?:\.\d{2})?(?!\d)|\s+\d+\.\d{2}(?!\d)",
    re.IGNORECASE,
)


def _item_row_description(line: str) -> str:
    """Description part of a numbered item row on a marketplace/retail invoice: "1 boAt Rockerz 450 ...
    | B07PR1CL3S ( HSN:85183000 ) 1,299.00 1 1,299.00 18% IGST ..." -> "1 boAt Rockerz 450 ... | B07PR1CL3S".
    Tax and price columns otherwise make the whole row look like boilerplate."""
    if not re.match(r"^\d{1,3}[\.\)]?\s+[A-Za-z]", line):
        return line
    head = _ROW_TAIL_RE.split(line, maxsplit=1)[0]
    head = re.sub(r"\s+\d{1,2}$", "", head.rstrip(" (|"))  # trailing quantity column
    return head if len(head) >= 8 else line


def _line_item_candidates(lines: List[str]) -> List[Tuple[int, str]]:
    candidates: List[Tuple[int, str]] = []
    for line in lines:
        clean = _item_row_description(_strip_invoice_table_prefix(line))
        if len(clean) < 5:
            continue
        low = clean.lower()
        if _is_boilerplate_line(clean) or _looks_like_address_text(clean) or _labelled_line(clean):
            continue
        # Split pipe-heavy item descriptions and score the strongest product-bearing segment.
        segments = [
            _normalize_spaces(part)
            for part in re.split(r"\s*\|\s*|\t+", clean)
            if _normalize_spaces(part)
        ]
        if len(segments) > 1:
            usable = [
                part
                for part in segments
                if not _is_boilerplate_line(part) and not _is_spec_only(part) and not _looks_like_address_text(part)
            ]
            if usable:
                clean = max(usable, key=lambda part: (1 if _has_product_signal(part) else 0, len(part)))
                low = clean.lower()
        if sum(1 for term in _LINE_NOISE_TERMS if term in low) >= 2:
            continue
        # A shop/seller line ("LG Authorized Store") is not a product line.
        if brand_registry.is_seller_line(clean) and not _contains_product_term(low):
            continue
        score = 0
        if re.match(r"^\d+[\.\)]?\s+", clean):
            score += 2
        if _canonical_oem(clean):
            score += 4
        if _has_product_signal(clean):
            score += 2
        if _contains_product_term(low):
            score += 3
        if re.search(r"\b[A-Z]{1,4}\s*-?\s*\d{2,5}[A-Z0-9\-]*\b", clean):
            score += 2
        if re.search(r"\b\d{5,}\b", clean):
            score -= 1
        if score >= 3:
            candidates.append((score, clean))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def _strip_line_item_noise(line: str) -> str:
    text = re.sub(r"^\d+[\.\)]?\s*", "", _strip_invoice_table_prefix(line))
    text = re.split(r"\s+\d{6,}\b", text, maxsplit=1)[0]
    text = re.split(r"\s+\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b", text, maxsplit=1)[0]
    return _normalize_spaces(text).strip(":-|")


def _model_from_product_line(line: str, brand: Optional[str]) -> Optional[str]:
    value, _kind = _model_candidate_from_line(line, brand)
    return value


# Marketing names that are not model codes ("Galaxy S24", "iPhone 15", "Redmi Note 13").
_MARKETING_MODEL_RE = re.compile(
    r"\b(?:Galaxy|iPhone|Pixel|Redmi(?:\s+Note)?|Note|Bravia|Vivobook|Ideapad|Inspiron|Pavilion)\s+"
    r"([A-Z]?\d{1,3}[A-Z]{0,3}(?:\s+(?:Ultra|Pro|Plus|Max|Mini|Lite|FE))?)\b",
    re.IGNORECASE,
)
# A printed model code: letters and digits joined by a hyphen, or 6+ chars mixing both ("SM-S928BZKGINS").
# Codes may carry "/" variant parts: "HL7756/00", "SM-A155F/DS".
_PRINTED_CODE_RE = re.compile(
    r"\b(?=[A-Z0-9\-]*\d)(?=[A-Z0-9\-]*[A-Z])((?:[A-Z0-9]{2,}-[A-Z0-9\-]{2,}|[A-Z0-9]{6,})(?:/[A-Z0-9]{1,6})*)\b"
)


# Marketplace listing codes are not model codes or serials: Amazon ASIN ("B0CMTVYVRS") and FNSKU
# ("X0011PGZX7"), Flipkart FSN ("MOBGTAGPAQNVFZZY", 16 chars, 3-letter category prefix).
_LISTING_CODE_RE = re.compile(r"(?:B0|X0)[A-Z0-9]{8}|[A-Z]{3}[A-Z0-9]{13}")


def is_listing_code(value: Optional[str]) -> bool:
    code = re.sub(r"[\s()]", "", str(value or "")).upper()
    if not _LISTING_CODE_RE.fullmatch(code):
        return False
    # An FSN-shaped code with a hyphen or few letters is more likely a real code; FSNs are mostly letters.
    return code.startswith(("B0", "X0")) or len(re.findall(r"[A-Z]", code)) >= 10


def _drop_spec_suffix(code: str) -> str:
    """Keep "/" variant parts of a model code, but not spec pairs: "HL7756/00" stays, "8GB/128GB" -> "8GB"."""
    parts = code.split("/")
    unit = re.compile(r"^\d+(?:\.\d+)?(?:GB|TB|MB|MAH|AH|WH|KW|W|V|HZ|L|KG|MM|CM|INCH|MP)$", re.IGNORECASE)
    return "/".join([parts[0]] + [part for part in parts[1:] if not unit.match(part)])


def _model_candidate_from_line(line: str, brand: Optional[str]) -> Tuple[Optional[str], str]:
    """(model, kind) from a product line; kind is "code" for a printed model code, "marketing" for a
    marketing name such as "Galaxy S24", or "" when nothing was found."""
    text = line
    if brand:
        text = re.sub(rf"\b{re.escape(brand)}\b", "", text, flags=re.IGNORECASE)
    marketing = _MARKETING_MODEL_RE.search(text)
    code_text = _MARKETING_MODEL_RE.sub(" ", text) if marketing else text
    for match in _PRINTED_CODE_RE.finditer(code_text.upper()):
        candidate = _drop_spec_suffix(match.group(1))
        if (not _is_spec_only(candidate) and not re.fullmatch(r"\d+", candidate) and not is_listing_code(candidate)
                and not re.fullmatch(r"[A-Z]{1,5}\d+(?:\.\d+)?(?:KG|L|LTR|W|GB|TB|MAH)", candidate)):
            return candidate, "code"
    if marketing:
        # "Note" is part of the series name ("Redmi Note 12 Pro" is not a "Redmi 12 Pro").
        series = "NOTE " if re.search(r"\bnote\b", marketing.group(0), re.IGNORECASE) else ""
        return series + _normalize_spaces(marketing.group(1)).upper(), "marketing"
    product_words = "|".join(re.escape(term) for term in _PRODUCT_TERMS)
    text = re.sub(rf"\b({product_words})\b", " ", text, flags=re.IGNORECASE)
    text = _normalize_spaces(text)
    patterns = (
        r"\b([A-Z]{1,5}\s*-?\s*\d{2,5}[A-Z0-9\-]*(?:/[A-Z0-9]{1,6})*)\b",
        r"\b(\d{2,4}[A-Z]{1,6}[A-Z0-9\-]*(?:/[A-Z0-9]{1,6})*)\b",
        r"\b([A-Z0-9]{2,}-[A-Z0-9\-]{2,}(?:/[A-Z0-9]{1,6})*)\b",
    )
    for pat in patterns:
        for m in re.finditer(pat, text):
            raw = m.group(1)
            # "Monza EC 15L": a series word followed by a capacity is not a model code ("EC15L").
            if re.search(r"\s", raw.strip()) and _is_spec_only(re.sub(r"^[A-Za-z]{1,5}\s*-?\s*", "", raw.strip())):
                continue
            candidate = _drop_spec_suffix(_normalize_spaces(raw).replace(" ", "").upper())
            if _is_spec_only(candidate):
                continue
            # Letters glued to a capacity ("WXS7KG", "EC15L"): a series name plus a size, not a model code.
            if re.fullmatch(r"[A-Z]{1,5}\d+(?:\.\d+)?(?:KG|L|LTR|W|GB|TB|MAH)", candidate):
                continue
            return candidate, "code"
    return None, ""


def sanitize_invoice_identity_fields(
    fields: Dict[str, str],
    confidence: Dict[str, float],
    alternatives: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, List[str]]]:
    """Reject invoice boilerplate/spec fragments before fields reach warranty lookup."""
    alternatives = dict(alternatives or {})
    sanitized_fields = dict(fields or {})
    sanitized_confidence = dict(confidence or {})
    removed: List[str] = []

    brand = sanitized_fields.get("brand")
    product_line = ((alternatives.get("product_line") or [""])[0] or "").lower()
    # Retailer own-label goods ("Croma 80 cm ... TV"): the retailer is the brand when it starts the item.
    own_label = bool(brand) and brand_registry.is_retailer(brand) and product_line.startswith(str(brand).lower())
    if brand and not own_label and (_is_boilerplate_line(brand) or _is_spec_only(brand) or _looks_like_seller_text(brand)):
        sanitized_fields.pop("brand", None)
        sanitized_confidence.pop("brand", None)
        removed.append(f"brand:{brand}")

    model = sanitized_fields.get("model_code")
    if model and (_is_boilerplate_line(model) or _is_spec_only(model) or is_listing_code(model)):
        sanitized_fields.pop("model_code", None)
        sanitized_confidence.pop("model_code", None)
        removed.append(f"model_code:{model}")

    product = sanitized_fields.get("product_name")
    if product:
        if _is_boilerplate_line(product) or _is_spec_only(product):
            sanitized_fields.pop("product_name", None)
            sanitized_confidence.pop("product_name", None)
            removed.append(f"product_name:{product}")
        else:
            parts = [
                _normalize_spaces(part)
                for part in re.split(r"\s+\|\s+|\t+", product)
                if _normalize_spaces(part) and not _is_boilerplate_line(part) and not _is_spec_only(part)
            ]
            if parts and len(parts) != 1:
                sanitized_fields["product_name"] = max(parts, key=lambda part: (1 if _has_product_signal(part) else 0, len(part)))
            cleaned_product = _clean_product_name_candidate(sanitized_fields.get("product_name", ""))
            if cleaned_product:
                sanitized_fields["product_name"] = cleaned_product

    if removed:
        alternatives["discarded_identity_candidates"] = removed
    return sanitized_fields, sanitized_confidence, alternatives


# Serial labels, including common OCR misreads of "serial" (seriat, seria:, seri, serlal).
_SERIAL_LABEL_RE = re.compile(
    r"\b(?:(?!series\b)seri[a-z0-9]{0,3}|s/n|sn|imei)\b(?:\s*(?:no\.?|number|num|#))?\s*[:\-#.]?",
    re.IGNORECASE,
)
_SERIAL_VALUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]{5,23}")
_SERIAL_HEADER_FRAGMENTS = ("INVOIC", "NVOICE", "RECEIPT", "BILL", "CUSTOMER", "ORIGINAL", "DUPLICATE", "TOTAL")


def _plausible_serial(value: str) -> bool:
    upper = value.upper()
    if not (re.search(r"\d", upper) and re.search(r"[A-Z]", upper)):
        return False
    letters = re.sub(r"[^A-Z]", "", upper)
    if any(fragment in letters for fragment in _SERIAL_HEADER_FRAGMENTS):
        return False
    if parse_date_from_text(value):
        return False
    return True


def luhn_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


_IMEI_LABEL_RE = re.compile(r"\bimei\s*(?:no\.?|number|1|2|#)?\s*(?:/\s*serial\s*(?:no\.?)?)?\s*[:\-#.]?\s*", re.IGNORECASE)


def _imei_candidate(lines: List[str]) -> Tuple[Optional[str], float, str, str]:
    """An IMEI (15 digits, Luhn check). Digit groups split by OCR ("86543206 1234567") are joined only
    when the result passes the Luhn check; anything else near an IMEI label becomes a suggestion."""
    for i, line in enumerate(lines):
        label = _IMEI_LABEL_RE.search(line)
        if not label:
            continue
        rest = line[label.end():] or next((nxt for nxt in lines[i + 1:i + 3] if nxt), "")
        first = rest.split()[0] if rest.split() else ""
        if re.search(r"[A-Za-z]", first):
            continue  # letters in the value: a serial printed after an IMEI label, handled as a serial
        groups = re.findall(r"\d+", rest.split("IMEI")[0].split("imei")[0])
        whole = next((g for g in groups if len(g) == 15), None)
        if whole and luhn_ok(whole):
            return whole, 0.7, "labelled", line
        joined = ""
        for g in groups:  # leading digit groups, as OCR split them
            joined += g
            if len(joined) >= 15:
                break
        if len(joined) == 15 and luhn_ok(joined):
            return joined, 0.7, "imei_repaired", line
        if whole or 13 <= len(joined) <= 17:
            return (whole or joined), 0.4, "misread_label", line
    return None, 0.0, "", ""


def _serial_candidate(lines: List[str], product_line: Optional[str]) -> Tuple[Optional[str], float, str, str]:
    """Return (serial, confidence, kind, source_line); kind is "labelled", "misread_label" (the label
    itself was garbled by OCR, e.g. "seriat"), "imei_repaired", "under_line_item" or "" when nothing was found."""
    clean_lines = [_normalize_spaces(line) for line in lines]
    misread = None
    for i, line in enumerate(clean_lines):
        for label in _SERIAL_LABEL_RE.finditer(line):
            exact = label.group(0).strip(" :-#.").lower().split()[0] in {"serial", "s/n", "sn", "imei"}
            rest = line[label.end():].strip()
            if not rest:
                # Label alone on its line: the value may sit on the next non-empty line.
                rest = next((nxt for nxt in clean_lines[i + 1:i + 3] if nxt), "")
            value = _SERIAL_VALUE_RE.match(rest)
            if value and _plausible_serial(value.group(0)):
                if exact:
                    return value.group(0).upper(), 0.7, "labelled", line  # a labelled serial wins over an IMEI
                misread = misread or (value.group(0).upper(), 0.5, "misread_label", line)
    imei = _imei_candidate(clean_lines)
    if imei[0]:
        return imei
    if misread:
        return misread
    if product_line:
        # Unlabelled fallback: a single code on the line directly under a real line item
        # (e.g. "1 Epson L 3250 Printer ..." followed by "XAHT699208").
        target = _normalize_spaces(product_line)
        # The product line may be the trimmed description of the row (see _item_row_description).
        idx = next((i for i, line in enumerate(clean_lines) if line == target or line.startswith(target)), -1)
        if idx >= 0 and re.match(r"^\d+[\.\)]?\s+\S", target) and idx + 1 < len(clean_lines):
            candidate = clean_lines[idx + 1]
            if re.fullmatch(r"[A-Z0-9]{8,18}", candidate) and _plausible_serial(candidate):
                return candidate, 0.5, "under_line_item", candidate
    return None, 0.0, "", ""


def _serial_from_lines(lines: List[str], product_line: Optional[str]) -> Tuple[Optional[str], float]:
    """Return (serial, confidence) for any candidate, including misread-label suggestions."""
    value, confidence, _kind, _line = _serial_candidate(lines, product_line)
    return value, confidence


_MISREAD_MODEL_RE = re.compile(r"^\W?\s*(m[ao]d[a-z0-9]{0,3})\b\s*[:\-.]?\s*(\S.*)$", re.IGNORECASE)


def _misread_model_line(lines: List[str]) -> Optional[Tuple[str, str]]:
    """(value, line) for a model line whose label OCR garbled ("Madet NEXON-007", "Mad IPHONEOO1")."""
    for raw in lines:
        line = _normalize_spaces(raw)
        match = _MISREAD_MODEL_RE.match(line)
        if not match:
            continue
        word, rest = match.group(1).lower(), match.group(2)
        if word == "made" and rest.lower().startswith(("in ", "by ")):
            continue
        value = rest.strip(" ,.;:").upper()
        if 3 <= len(value) <= 24 and re.search(r"\d", value) and re.search(r"[A-Z0-9]{2}", value):
            return value, line
    return None


# Pipeline confidence below which a brand, model or serial is offered for confirmation, not stored.
SUGGESTION_CONFIDENCE = 0.6
SUGGESTION_KEYS = {"brand": "brand_suggestion", "model_code": "model_suggestion", "serial_no": "serial_suggestion"}

# Characters OCR mixes up in codes (owner decision 3, 2026-10-06).
CONFUSABLE = set("O0I1S5B8")
OCR_METHODS = {"tesseract", "paddle", "tesseract_fallback", "pdf_ocr", "ocr", "vision"}


_SWAP = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B"}
_MAX_VARIANT_POSITIONS = 10  # 2**10 readings at most


def confusable_positions(value: str) -> List[int]:
    """Indexes in the value as printed whose character OCR could have mixed up (shown highlighted to the customer)."""
    return [i for i, ch in enumerate(str(value or "").upper()) if ch in CONFUSABLE]


def known_reading(code: str, known: set) -> Optional[str]:
    """The one known model that an O/0, I/1, S/5, B/8 mix-up of `code` would match, if exactly one does."""
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    positions = [i for i, ch in enumerate(code) if ch in CONFUSABLE]
    if not code or not known or not positions or len(positions) > _MAX_VARIANT_POSITIONS:
        return None
    matches = set()
    for mask in range(1, 2 ** len(positions)):
        chars = list(code)
        for bit, pos in enumerate(positions):
            if mask >> bit & 1:
                chars[pos] = _SWAP[chars[pos]]
        candidate = "".join(chars)
        if candidate in known:
            matches.add(candidate)
    return matches.pop() if len(matches) == 1 else None


def from_ocr(ocr_meta: Optional[Dict[str, object]]) -> bool:
    """True when the text was read from a scan or photo (not a PDF text layer, .txt or .docx)."""
    return str((ocr_meta or {}).get("method") or "").lower() in OCR_METHODS


def route_confusable_codes(
    fields: Dict[str, str],
    confidence: Dict[str, float],
    alternatives: Dict[str, object],
    *,
    ocr: bool,
    known_models: Optional[set] = None,
) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, object]]:
    """From a scan or photo, a model or serial containing O/0, I/1, S/5 or B/8 is saved as "please confirm"
    unless it can be validated: an IMEI that passes the Luhn check, or a model already known for the brand
    (knowledge base, official terms cache, or confirmed by customers). Text-layer PDFs and typed text are not
    affected. The suggestion lists the characters to check; when exactly one mix-up reading is a known model,
    that reading is offered (still to be confirmed) with what was read kept as `read_as`."""
    if not ocr:
        return fields, confidence, alternatives
    fields, confidence, alternatives = dict(fields), dict(confidence), dict(alternatives or {})
    known_display = {re.sub(r"[^A-Z0-9]", "", str(m).upper()): str(m).upper() for m in (known_models or set())}
    known = set(known_display)
    for field, key in (("model_code", "model_suggestion"), ("serial_no", "serial_suggestion")):
        value = fields.get(field)
        if not value or float(confidence.get(field) or 0.0) >= 0.9:  # missing, or confirmed by the user
            continue
        code = re.sub(r"[^A-Z0-9]", "", str(value).upper())
        if not CONFUSABLE & set(code):
            continue
        if field == "serial_no" and len(code) == 15 and luhn_ok(code):
            continue  # a valid IMEI
        if field == "model_code" and code in known:
            continue
        fields.pop(field, None)
        confidence.pop(field, None)
        suggestion = {
            "value": value,
            "source_line": "",
            "status": "pending",
            "reason": "Read from a scan or photo, where O/0, I/1, S/5 and B/8 are easy to mix up; "
                      "please check the highlighted characters.",
            "check_characters": confusable_positions(value),
        }
        match = known_reading(code, known) if field == "model_code" else None
        if match:
            match = known_display.get(match, match)
            suggestion.update({
                "value": match,
                "read_as": value,
                "reason": f"We read {value}, which looks like {match}, a model we know for this brand; please confirm.",
                "check_characters": confusable_positions(match),
            })
        alternatives[key] = suggestion
    return fields, confidence, alternatives


def route_uncertain_identity(
    fields: Dict[str, str],
    confidence: Dict[str, float],
    alternatives: Dict[str, object],
) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, object]]:
    """Move low-confidence brand/model/serial values, and brands that are not in the OEM registry,
    out of the stored fields and into pending ``<field>_suggestion`` entries the user confirms."""
    fields, confidence, alternatives = dict(fields), dict(confidence), dict(alternatives or {})
    for field, key in SUGGESTION_KEYS.items():
        value = fields.get(field)
        if not value:
            continue
        conf = float(confidence.get(field) or 0.0)
        if conf >= 0.9:
            continue  # user-confirmed
        if field == "serial_no" and alternatives.get("serial_evidence") == "under_line_item":
            continue
        reason = None
        if field == "brand" and not _canonical_oem(value):
            reason = "This brand is not in our list of known manufacturers; please confirm it."
        elif conf < SUGGESTION_CONFIDENCE:
            reason = "We are not sure we read this correctly; please confirm."
        if not reason:
            continue
        fields.pop(field, None)
        confidence.pop(field, None)
        alternatives.setdefault(key, {"value": value, "source_line": "", "status": "pending", "reason": reason})
    return fields, confidence, alternatives


def ingest_artifact(
    artifact_type: ArtifactType,
    content: Optional[str] = None,
    source: Optional[str] = None,
    file_path: Optional[str] = None,
    use_ocr: bool = False,
) -> Artifact:
    text_content = content or ""
    ocr_note = None
    ocr_meta = None
    if file_path or use_ocr:
        text, err, meta = extract_text_with_meta(file_path or "")
        ocr_meta = {
            "method": meta.get("method"),
            "engine": meta.get("engine"),
            "paddle_failed": bool(meta.get("paddle_error")),
        }
        if text:
            text_content = text
        if err:
            ocr_note = err

    if not text_content:
        text_content = ""
    if ocr_note:
        text_content = f"{text_content}\n\n[OCR note] {ocr_note}".strip()

    artifact = Artifact(
        id=generate_id("art"),
        type=artifact_type,
        content=text_content,
        source=source,
        ocr_meta=ocr_meta,
    )
    return store.add_artifact(artifact)


_MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
# "22 Apr 2017", "22-Apr-17", "22nd April, 2017"
_DAY_MONTH_YEAR_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s\-/.,]+{_MONTHS}[\s\-/.,]+(\d{{4}}|\d{{2}})\b", re.IGNORECASE)
# "Apr 22, 2017", "April 22nd 2017", "Apr-22-2017"
_MONTH_DAY_YEAR_RE = re.compile(rf"\b{_MONTHS}[\s\-/.]+(\d{{1,2}})(?:st|nd|rd|th)?[\s,\-/.]+(\d{{4}})\b", re.IGNORECASE)
_NUMERIC_DATE_RE = re.compile(r"(?<![\d.])(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})(?![\d.])")


def _plausible_year(year: int) -> bool:
    return 1990 <= year <= datetime.utcnow().year + 1


def _named_month_dates(text: str) -> List[Tuple[int, str]]:
    found: List[Tuple[int, str]] = []
    for m in _DAY_MONTH_YEAR_RE.finditer(text):
        day, month, year = m.group(1), m.group(2), m.group(3)
        found.append((m.start(), f"{day}-{month[:3].title()}-{year}"))
    for m in _MONTH_DAY_YEAR_RE.finditer(text):
        month, day, year = m.group(1), m.group(2), m.group(3)
        found.append((m.start(), f"{day}-{month[:3].title()}-{year}"))
    out = []
    for pos, raw in sorted(found):
        try:
            dt = datetime.strptime(raw, "%d-%b-%y" if len(raw.rsplit("-", 1)[1]) == 2 else "%d-%b-%Y")
        except ValueError:
            continue
        if _plausible_year(dt.year):
            out.append((pos, dt.date().isoformat()))
    return out


def parse_date_from_text(text: str) -> Optional[str]:
    """First date in the text: named months first ("22 Apr 2017", "Apr 22, 2017", "22nd April 2017"), then
    numeric dates ("22/04/2017", "22-04-17", "22.04.2017", "2017-04-22"; day before month, as in India)."""
    named = _named_month_dates(text or "")
    if named:
        return named[0][1]
    for raw in _NUMERIC_DATE_RE.findall(text or ""):
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y"):
            try:
                dt = datetime.strptime(raw, fmt)
            except ValueError:
                continue
            if _plausible_year(dt.year):
                return dt.date().isoformat()
    return None


# Where an invoice states its own date (strongest first). Each pattern's end is where the date starts.
_DATE_LABEL_RES = (
    re.compile(r"\b(?:invoice|bill|purchase|order|transaction)\s*(?:date|dt\.?)\s*[:\-.]?\s*", re.IGNORECASE),
    re.compile(r"\bdate\s+of\s+(?:invoice|purchase|issue|order)\s*[:\-.]?\s*", re.IGNORECASE),
    re.compile(r"\b(?:order\s+placed(?:\s+on)?|ordered\s+on|dated)\s*[:\-.]?\s*", re.IGNORECASE),
    # Headings such as "Invoice for DMVVzZMtnN Apr 22, 2017" / "Packing slip for 402-... 22/04/2017".
    re.compile(r"^\W*(?:tax\s+invoice|invoice|packing\s+slip|bill|order)\b[^\n]{0,40}?\bfor\s+\S+\s+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\bdate\s*[:\-.]?\s*", re.IGNORECASE),
)
# Amazon-style footer stamp "0422-10:15" (month, day, time): no year, so only used with the one year the
# invoice mentions, and only when nothing better was found.
_FOOTER_STAMP_RE = re.compile(r"\b(0[1-9]|1[0-2])([0-2]\d|3[01])-([01]\d|2[0-3]):[0-5]\d\b")


def find_purchase_date(text: str) -> Tuple[Optional[str], float]:
    """(ISO date, confidence) of the purchase: a labelled or heading date (0.8), any date (0.5), or the
    footer stamp with the invoice's only year (0.4)."""
    text = text or ""
    for pattern in _DATE_LABEL_RES:
        for m in pattern.finditer(text):
            before = text[max(0, m.start() - 16): m.start()].lower()
            if re.search(r"(?:due|expir\w*|deliver\w*|valid\w*|warranty|end|until|till|ship\w*)\W*$", before):
                continue  # "Due date", "Expiry date", "Delivery date" are not the purchase date
            window = text[m.end(): m.end() + 32].split("\n", 1)[0]
            found = parse_date_from_text(window)
            if found:
                return found, 0.8
    found = parse_date_from_text(text)
    if found:
        return found, 0.5
    stamp = _FOOTER_STAMP_RE.search(text)
    years = {int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text) if _plausible_year(int(y))}
    if stamp and len(years) == 1:
        try:
            dt = datetime(years.pop(), int(stamp.group(1)), int(stamp.group(2)))
            return dt.date().isoformat(), 0.4
        except ValueError:
            pass
    return None, 0.0


def extract_product_fields(text: str) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, List[str]]]:
    """Extract product fields from invoice/receipt text."""
    lowered = text.lower()
    fields: Dict[str, str] = {}
    confidence: Dict[str, float] = {}
    alternatives: Dict[str, List[str]] = {}
    lines = text.strip().split('\n')
    logical_lines = _logical_invoice_lines(lines)
    has_warranty_context = bool(
        re.search(r"\b(warranty|serial|imei|model|product|device)\b", lowered, re.IGNORECASE)
        or _contains_product_term(lowered)
    )

    line_items = _line_item_candidates(logical_lines)
    has_warranty_context = has_warranty_context or bool(line_items)
    best_item = _strip_line_item_noise(line_items[0][1]) if line_items else None
    item_brand = _canonical_oem(best_item or "")
    seller_candidates: List[str] = []
    for line in lines[:8]:
        cleaned = _clean_seller_candidate(line)
        if cleaned and cleaned != item_brand:
            seller_candidates.append(cleaned)
            break
    if seller_candidates:
        alternatives["seller"] = seller_candidates

    # === BRAND EXTRACTION ===
    # Strategy 1: Explicit "Brand:" label
    brand_match = re.search(r"brand\s*[:\-]\s*([a-zA-Z0-9 \-]{2,40})", text, re.IGNORECASE)
    labelled_brand = brand_match.group(1) if brand_match else None
    if not labelled_brand:
        # Misread label, e.g. "Band: Apple" / "Band Sony".
        for line in lines:
            labelled = _labelled_line(line)
            if labelled and labelled[0] in ("brand", "make"):
                labelled_brand = labelled[1][:40]
                break
    # Registry brand named only in the shop/header lines, e.g. "LG Authorized Store".
    shop_lines = [line for line in lines[:8] if brand_registry.is_seller_line(line)]
    header_brand = None if item_brand else brand_registry.resolve_brand(None, seller_lines=shop_lines)
    if item_brand:
        fields["brand"] = item_brand
        confidence["brand"] = 0.85
        alternatives["product_line"] = [best_item] if best_item else []
    elif labelled_brand and (_canonical_oem(labelled_brand) or not header_brand):
        # A labelled brand wins when it is a registry brand, or when nothing better exists.
        cleaned = _clean_brand_candidate(labelled_brand)
        if cleaned:
            fields["brand"] = _canonical_oem(cleaned) or cleaned
            confidence["brand"] = 0.8
    elif header_brand:
        fields["brand"] = header_brand
        confidence["brand"] = 0.7
    elif has_warranty_context:
        # Strategy 2: First non-empty line (usually company name on invoices)
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if (
                len(line) > 3
                and not line.lower().startswith(('invoice', 'bill', 'receipt', 'tax', 'gst', 'date'))
                and not _is_boilerplate_line(line)
                and not _has_product_signal(line)
                and not brand_registry.is_seller_line(line)
                and not re.match(r"^\d+[\.\)]?\s+", line)
            ):
                cleaned = _clean_brand_candidate(line)
                if cleaned and len(cleaned) >= 3:
                    fields["brand"] = cleaned
                    confidence["brand"] = 0.6
                    break

    # === PRODUCT NAME EXTRACTION ===
    # Strategy 1: Explicit "Product:" or "Item:" label
    product_match = re.search(r"(?:product|item name|device)\s*[:\-]\s*([a-zA-Z0-9 \-\.]{3,60})", text, re.IGNORECASE)
    if product_match:
        val = _clean_product_name_candidate(product_match.group(1).strip())
        # Exclude header keywords
        if val and val.lower() not in ('description', 'hsn', 'sac', 'qty', 'price', 'tax', 'total'):
            fields["product_name"] = val.title()
            confidence["product_name"] = 0.7
    if "product_name" not in fields:
        # "Product iPhone 15": the label's colon is often lost by OCR.
        for line in lines:
            m = re.match(r"^\s*(?:product|item)(?:\s*name)?\s*[:\-]?\s+(\S.{1,59})$", line.strip(), re.IGNORECASE)
            if not m:
                continue
            val = _clean_product_name_candidate(m.group(1))
            if val and not val.endswith(":") and val.lower().split()[0] not in ("details", "description", "info", "information", "code", "id"):
                fields["product_name"] = val
                confidence["product_name"] = 0.65
                break

    # Strategy 2: Look for product patterns in line items (e.g., "1. Samsung Galaxy S24")
    if "product_name" not in fields:
        if best_item:
            fields["product_name"] = _clean_product_name_candidate(best_item) or best_item
            confidence["product_name"] = 0.75
        else:
            item_pattern = r"(?:^|\n)\s*\d+[\.\)]\s*([A-Z][a-zA-Z0-9 \-]{5,50}?)(?:\s+\d|\s+[A-Z]{2,5}\d|\s*$)"
            item_match = re.search(item_pattern, text)
            if item_match:
                val = _clean_product_name_candidate(item_match.group(1).strip())
                if val and val.lower() not in ('description', 'hsn', 'sac', 'qty', 'price', 'tax', 'total'):
                    fields["product_name"] = val.title()
                    confidence["product_name"] = 0.5

    # Marketplace/retail rows name the maker first ("Reconnect 1.5 Ton ... AC"). When that word is not a
    # known brand, offer it for confirmation instead of guessing from the seller (consolidated run step 8).
    if "brand" not in fields and best_item and fields.get("product_name"):
        first = re.match(r"([A-Za-z][A-Za-z&'\-]{2,20})\b", fields["product_name"])
        if first and first.group(1).lower() not in _TITLE_NON_BRAND_WORDS and not _contains_product_term(first.group(1)):
            alternatives.setdefault("brand_suggestion", {
                "value": first.group(1),
                "source_line": best_item,
                "status": "pending",
                "reason": "We read this brand from the product title; it is not in our list of known manufacturers. Please confirm.",
            })

    # === MODEL CODE ===
    # Printed model code first ("Model Code: SM-S928BZKGINS"); a marketing name such as "Galaxy S24"
    # stays in the product name and is only offered as a suggestion.
    model_match = re.search(
        r"\b(?:model|mode[li1])(?:\s*(?:code|no\.?|number|#))?\s*[:\-#]\s*([a-zA-Z0-9][a-zA-Z0-9\-/]{1,29})",
        text,
        re.IGNORECASE,
    )
    item_model, item_model_kind = _model_candidate_from_line(best_item or "", fields.get("brand"))
    misread_model = None if model_match else _misread_model_line(lines)
    if model_match:
        fields["model_code"] = model_match.group(1).strip().upper()
        confidence["model_code"] = 0.8
    elif item_model and item_model_kind == "code":
        fields["model_code"] = item_model
        confidence["model_code"] = 0.75
    elif misread_model:
        alternatives["model_suggestion"] = {
            "value": misread_model[0],
            "source_line": misread_model[1],
            "status": "pending",
            "reason": "Model label was misread by OCR; please confirm the model code.",
        }
    elif item_model:
        # Only a marketing name ("Galaxy M17e") is printed: store it, as before, below a printed code.
        fields["model_code"] = item_model
        confidence["model_code"] = 0.7
        alternatives["model_evidence"] = "marketing_name"
    else:
        # Fallback: an unlabelled token shaped like a model code. Too weak to store; offer it instead.
        model_token = next(
            (
                m for m in re.finditer(r"\b([A-Z]{2,}[A-Z0-9\-]{2,})\b", text)
                # Never a tax/order identifier: PAN (AAAAA9999A), GSTIN, or a token on a PAN/GST/order/CIN line.
                if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]|\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z0-9]{2}", m.group(1))
                and not re.search(
                    r"\b(?:pan|gst|gstin|cin|order|fssai|invoice|bill|awb|irn)\b",
                    text[text.rfind("\n", 0, m.start()) + 1 : m.start()],
                    re.IGNORECASE,
                )
            ),
            None,
        )
        if model_token:
            token = model_token.group(1).strip().upper()
            if token not in (
                "GST", "HSN", "SAC", "INR", "CGST", "SGST", "IGST",
                "INVOICE", "BILL", "RETAIL", "TAX", "CUSTOMER", "COPY", "TOTAL",
                "ORIGINAL", "RECIPIENT", "DESCRIPTION", "QUANTITY", "AMOUNT",
            ) and re.search(r"\d", token) and not _is_spec_only(token):
                alternatives["model_suggestion"] = {
                    "value": token,
                    "source_line": next((line.strip() for line in lines if token in line.upper()), ""),
                    "status": "pending",
                    "reason": "This looks like a model code but was not labelled; please confirm.",
                }

    # === SERIAL NUMBER ===
    serial_value, serial_confidence, serial_kind, serial_line = _serial_candidate(
        logical_lines + lines, line_items[0][1] if line_items else None
    )
    if serial_value and serial_kind == "misread_label":
        # The label itself was garbled by OCR, so the value is likely garbled too: offer it to the
        # user to confirm instead of storing it (fix run B5).
        alternatives["serial_suggestion"] = {
            "value": serial_value,
            "source_line": serial_line,
            "status": "pending",
            "reason": (
                "This IMEI did not pass the IMEI check; please confirm the number."
                if re.search(r"imei", serial_line, re.IGNORECASE)
                else "Serial label was misread by OCR; please confirm the number."
            ),
        }
    elif serial_value:
        fields["serial_no"] = serial_value
        confidence["serial_no"] = serial_confidence
        if serial_kind == "under_line_item":
            alternatives["serial_evidence"] = serial_kind  # the Epson exception: stored, not suggested
        elif serial_kind == "imei_repaired":
            alternatives["serial_evidence"] = serial_kind  # OCR split the IMEI; joined only because Luhn passes

    # === PURCHASE DATE ===
    # A labelled or heading date first ("Invoice Date:", "Order placed", "Invoice for <code> <date>"), then any
    # date, then a footer stamp with the invoice's only year.
    if has_warranty_context:
        date_str, date_conf = find_purchase_date(text)
        if date_str:
            fields["purchase_date"] = date_str
            confidence["purchase_date"] = date_conf

    # === INVOICE NUMBER ===
    inv_patterns = [
        r"(?:invoice|invo[il1]ce|inv)\s*(?:no|number|#)\.?\s*[:\-#]?\s*([a-zA-Z0-9][a-zA-Z0-9\-/]{2,30})",
        r"(?:invoice|invo[il1]ce)\s*[:\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-/]{2,30})",
    ]
    if has_warranty_context:
        inv_patterns.append(r"(?:bill)\s*(?:no|number|#)\s*[:\-]?\s*([a-zA-Z0-9][a-zA-Z0-9\-/]{2,30})")
    invalid_invoice_tokens = {"INVOICE", "BILL", "NUMBER", "NO", "TAX", "DATE", "PRODUCT", "MODEL", "SERIAL"}
    invoice_value = None
    for pat in inv_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        candidate = m.group(1).strip().upper()
        if candidate in invalid_invoice_tokens:
            continue
        invoice_value = candidate
        break
    # Marketplace order IDs ("Order Number: 408-1234567-8901234", "Order ID: OD4312...") are not invoice
    # numbers: kept separately, and never stored as the invoice number.
    order_match = re.search(r"\border\s*(?:id|no|number|#)\.?\s*[:\-#]?\s*([A-Z0-9][A-Z0-9\-]{5,30})", text, re.IGNORECASE)
    if order_match:
        alternatives["order_id"] = [order_match.group(1).strip().upper()]
        if invoice_value and invoice_value == alternatives["order_id"][0]:
            invoice_value = None
    if invoice_value:
        fields["invoice_no"] = invoice_value
        confidence["invoice_no"] = 0.7

    # === WARRANTY DURATION ===
    coverage_months = None
    # Pattern A: "Warranty: 24 months" / "Warranty - 2 years"
    m_a = re.search(r"warranty\s*[:\-]?\s*(\d{1,2})\s*(year|yr|month|mo)s?\b", text, re.IGNORECASE)
    if m_a:
        qty = int(m_a.group(1))
        unit = m_a.group(2).lower()
        coverage_months = qty * 12 if unit in ("year", "yr") else qty
    else:
        # Pattern B: "24 months manufacturer warranty"
        m_b = re.search(
            r"(\d{1,2})\s*(year|yr|month|mo)s?(?:\s+\w+){0,4}\s+warranty\b",
            text,
            re.IGNORECASE,
        )
        if m_b:
            qty = int(m_b.group(1))
            unit = m_b.group(2).lower()
            coverage_months = qty * 12 if unit in ("year", "yr") else qty
    if coverage_months:
        fields["coverage_months"] = str(coverage_months)
        confidence["coverage_months"] = 0.7

    product_category = _infer_product_category(
        product_name=fields.get("product_name"),
        model_code=fields.get("model_code"),
        lowered_text=lowered,
    )
    if product_category:
        fields["product_category"] = product_category
        confidence["product_category"] = max(confidence.get("product_category", 0.0), 0.55)

    region_code = _infer_invoice_region(text)
    if region_code:
        fields["region_code"] = region_code
        confidence["region_code"] = 0.7

    fields, confidence, alternatives = sanitize_invoice_identity_fields(fields, confidence, alternatives)
    fields, confidence, alternatives = route_uncertain_identity(fields, confidence, alternatives)

    if not confidence:
        alternatives["notes"] = ["No strong signals found; manual entry may be required."]

    return fields, confidence, alternatives
