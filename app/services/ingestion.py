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
    if any(k in hay for k in ("phone", "mobile", "iphone", "android", "galaxy")):
        return "mobile"
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


def _line_item_candidates(lines: List[str]) -> List[Tuple[int, str]]:
    candidates: List[Tuple[int, str]] = []
    for line in lines:
        clean = _strip_invoice_table_prefix(line)
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
_PRINTED_CODE_RE = re.compile(r"\b(?=[A-Z0-9\-]*\d)(?=[A-Z0-9\-]*[A-Z])([A-Z0-9]{2,}-[A-Z0-9\-]{2,}|[A-Z0-9]{6,})\b")


def _model_candidate_from_line(line: str, brand: Optional[str]) -> Tuple[Optional[str], str]:
    """(model, kind) from a product line; kind is "code" for a printed model code, "marketing" for a
    marketing name such as "Galaxy S24", or "" when nothing was found."""
    text = line
    if brand:
        text = re.sub(rf"\b{re.escape(brand)}\b", "", text, flags=re.IGNORECASE)
    marketing = _MARKETING_MODEL_RE.search(text)
    code_text = _MARKETING_MODEL_RE.sub(" ", text) if marketing else text
    for match in _PRINTED_CODE_RE.finditer(code_text.upper()):
        candidate = match.group(1)
        if not _is_spec_only(candidate) and not re.fullmatch(r"\d+", candidate) and not re.fullmatch(r"B0[A-Z0-9]{8}", candidate):
            return candidate, "code"
    if marketing:
        return _normalize_spaces(marketing.group(1)).upper(), "marketing"
    product_words = "|".join(re.escape(term) for term in _PRODUCT_TERMS)
    text = re.sub(rf"\b({product_words})\b", " ", text, flags=re.IGNORECASE)
    text = _normalize_spaces(text)
    patterns = (
        r"\b([A-Z]{1,5}\s*-?\s*\d{2,5}[A-Z0-9\-]*)\b",
        r"\b(\d{2,4}[A-Z]{1,6}[A-Z0-9\-]*)\b",
        r"\b([A-Z0-9]{2,}-[A-Z0-9\-]{2,})\b",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            candidate = _normalize_spaces(m.group(1)).replace(" ", "").upper()
            if _is_spec_only(candidate):
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
    if brand and (_is_boilerplate_line(brand) or _is_spec_only(brand) or _looks_like_seller_text(brand)):
        sanitized_fields.pop("brand", None)
        sanitized_confidence.pop("brand", None)
        removed.append(f"brand:{brand}")

    model = sanitized_fields.get("model_code")
    if model and (_is_boilerplate_line(model) or _is_spec_only(model)):
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


def _serial_candidate(lines: List[str], product_line: Optional[str]) -> Tuple[Optional[str], float, str, str]:
    """Return (serial, confidence, kind, source_line); kind is "labelled", "misread_label" (the label
    itself was garbled by OCR, e.g. "seriat"), "under_line_item" or "" when nothing was found."""
    clean_lines = [_normalize_spaces(line) for line in lines]
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
                    return value.group(0).upper(), 0.7, "labelled", line
                return value.group(0).upper(), 0.5, "misread_label", line
    if product_line:
        # Unlabelled fallback: a single code on the line directly under a real line item
        # (e.g. "1 Epson L 3250 Printer ..." followed by "XAHT699208").
        target = _normalize_spaces(product_line)
        idx = next((i for i, line in enumerate(clean_lines) if line == target), -1)
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


def parse_date_from_text(text: str) -> Optional[str]:
    """Extract date from text, supporting multiple formats."""
    # Pattern 1: Date with month names (15-Nov-2025, 24 Dec 2025, 24-Dec-2025)
    month_pattern = r"(\d{1,2})[\s\-/]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-/]+(\d{2,4})"
    month_matches = re.findall(month_pattern, text, re.IGNORECASE)
    for day, month, year in month_matches:
        try:
            raw = f"{day}-{month[:3].title()}-{year}"
            if len(year) == 2:
                dt = datetime.strptime(raw, "%d-%b-%y")
            else:
                dt = datetime.strptime(raw, "%d-%b-%Y")
            return dt.date().isoformat()
        except ValueError:
            continue
    
    # Pattern 2: Numeric dates (24-12-2025, 24/12/2025, 24.12.2025, 2025-12-24)
    numeric_candidates = re.findall(
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})", text
    )
    for raw in numeric_candidates:
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
    
    return None


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
        model_token = re.search(r"\b([A-Z]{2,}[A-Z0-9\-]{2,})\b", text)
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
            "reason": "Serial label was misread by OCR; please confirm the number.",
        }
    elif serial_value:
        fields["serial_no"] = serial_value
        confidence["serial_no"] = serial_confidence
        if serial_kind == "under_line_item":
            alternatives["serial_evidence"] = serial_kind  # the Epson exception: stored, not suggested

    # === PURCHASE DATE ===
    # Look specifically for "Date:" labeled date first
    if has_warranty_context:
        date_label_match = re.search(r"(?:date|invoice date|purchase date)\s*[:\-]\s*(.{8,20})", text, re.IGNORECASE)
        if date_label_match:
            date_str = parse_date_from_text(date_label_match.group(1))
            if date_str:
                fields["purchase_date"] = date_str
                confidence["purchase_date"] = 0.8
    
    # Fallback: Any date in text
    if has_warranty_context and "purchase_date" not in fields:
        date_str = parse_date_from_text(text)
        if date_str:
            fields["purchase_date"] = date_str
            confidence["purchase_date"] = 0.5

    # === INVOICE NUMBER ===
    inv_patterns = [
        r"(?:invoice|invo[il1]ce|inv)\s*(?:no|number|#)\s*[:\-]?\s*([a-zA-Z0-9][a-zA-Z0-9\-/]{2,30})",
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
