import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import Artifact, ArtifactType
from ..storage import generate_id, store
from .ocr import extract_text

_KNOWN_OEMS = (
    "acer", "apple", "asus", "bajaj", "bosch", "brother", "canon", "dell", "dyson",
    "epson", "godrej", "haier", "hp", "lenovo", "lg", "mi", "microsoft", "oneplus",
    "oppo", "panasonic", "philips", "samsung", "sony", "vivo", "voltas", "whirlpool",
    "xiaomi",
)

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
    return False


def _is_spec_only(value: str) -> bool:
    text = _normalize_spaces(value).strip(":-|").lower()
    if not text:
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _SPEC_ONLY_PATTERNS)


def _has_product_signal(value: str) -> bool:
    low = _normalize_spaces(value).lower()
    return bool(_canonical_oem(low) or any(term in low for term in _PRODUCT_TERMS))


def _canonical_oem(value: str) -> Optional[str]:
    low = (value or "").lower()
    tokens = set(re.findall(r"[a-z0-9]+", low))
    for brand in _KNOWN_OEMS:
        if brand in tokens:
            if brand == "hp":
                return "HP"
            if brand == "lg":
                return "LG"
            if brand == "mi":
                return "Mi"
            return brand.title()
    return None


def _clean_brand_candidate(raw: str) -> Optional[str]:
    text = _normalize_spaces(raw).strip(":-|")
    if not text:
        return None
    if _is_boilerplate_line(text) or _is_spec_only(text):
        return None
    # Remove noisy prefixes that often appear in OCR.
    text = re.sub(r"^(brand|make)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(seller|sold by|merchant|supplier|retailer)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    # Stop at other field labels.
    text = re.split(r"\b(model|invoice|serial|imei|warranty|purchase date|date|gstin)\b", text, flags=re.IGNORECASE)[0]
    text = _normalize_spaces(text).strip(":-|")
    if len(text) < 2:
        return None
    if _looks_like_seller_text(text):
        return None
    # Trim common legal suffixes.
    text = re.sub(r"\s*(pvt\.?|ltd\.?|private|limited|inc\.?|llc|corp\.?).*$", "", text, flags=re.IGNORECASE).strip()
    if len(text) < 2:
        return None
    if _is_boilerplate_line(text) or _is_spec_only(text):
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
    if _is_boilerplate_line(text) or _is_spec_only(text) or _has_product_signal(text):
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

    stop_pattern = re.compile(
        r"^(?:invoice\s+date|order\s+date|shipping charges?|total|subtotal|taxable|igst|cgst|sgst|amount|grand total)\b",
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

        starts_item = bool(re.match(r"^\d+[\.\)]?\s+", clean))
        if starts_item and _has_product_signal(clean):
            flush_current()
            current = clean
            continue

        if current:
            if stop_pattern.search(clean) and not _has_product_signal(clean):
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
    text = _normalize_spaces(raw).strip(":-|")
    if not text or _is_boilerplate_line(text):
        return None
    text = re.sub(r"^\d+[\.\)]?\s*", "", text)
    text = re.sub(r"\bIP\s*\d{2,3}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*(?:no|nos|pcs|piece|pieces|qty|quantity)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b.*$", "", text)
    text = _normalize_spaces(text).strip(":-|")
    if not text or _is_spec_only(text):
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


def _line_item_candidates(lines: List[str]) -> List[Tuple[int, str]]:
    candidates: List[Tuple[int, str]] = []
    for line in lines:
        clean = _normalize_spaces(line)
        if len(clean) < 5:
            continue
        low = clean.lower()
        if _is_boilerplate_line(clean):
            continue
        # Split pipe-heavy item descriptions and score the strongest product-bearing segment.
        segments = [
            _normalize_spaces(part)
            for part in re.split(r"\s+\|\s+|\t+", clean)
            if _normalize_spaces(part)
        ]
        if len(segments) > 1:
            usable = [part for part in segments if not _is_boilerplate_line(part) and not _is_spec_only(part)]
            if usable:
                clean = max(usable, key=lambda part: (1 if _has_product_signal(part) else 0, len(part)))
                low = clean.lower()
        if sum(1 for term in _LINE_NOISE_TERMS if term in low) >= 2:
            continue
        score = 0
        if re.match(r"^\d+[\.\)]?\s+", clean):
            score += 2
        if _canonical_oem(clean):
            score += 4
        if any(term in low for term in _PRODUCT_TERMS):
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
    text = re.sub(r"^\d+[\.\)]?\s*", "", _normalize_spaces(line))
    text = re.split(r"\s+\d{6,}\b", text, maxsplit=1)[0]
    text = re.split(r"\s+\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b", text, maxsplit=1)[0]
    return _normalize_spaces(text).strip(":-|")


def _model_from_product_line(line: str, brand: Optional[str]) -> Optional[str]:
    text = line
    if brand:
        text = re.sub(rf"\b{re.escape(brand)}\b", "", text, flags=re.IGNORECASE)
    galaxy = re.search(r"\bGalaxy\s+([A-Z]\d{1,3}[A-Z]{0,3})\b", line, re.IGNORECASE)
    if galaxy:
        candidate = galaxy.group(1).upper()
        if not _is_spec_only(candidate):
            return candidate
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
            return candidate
    return None


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


def _serial_from_lines(lines: List[str], product_line: Optional[str]) -> Optional[str]:
    serial_match = re.search(r"\b(?:serial|s/n|sn|imei)\b\s*[:\-#]?\s*([a-zA-Z0-9\-]{6,})", "\n".join(lines), re.IGNORECASE)
    if serial_match:
        return serial_match.group(1).strip().upper()
    if product_line:
        try:
            idx = next(i for i, line in enumerate(lines) if _normalize_spaces(line) == product_line)
        except StopIteration:
            idx = -1
        for line in lines[idx + 1: idx + 4] if idx >= 0 else []:
            clean = _normalize_spaces(line)
            if re.fullmatch(r"[A-Z0-9]{8,18}", clean) and not clean.isdigit():
                return clean.upper()
    return None


def ingest_artifact(
    artifact_type: ArtifactType,
    content: Optional[str] = None,
    source: Optional[str] = None,
    file_path: Optional[str] = None,
    use_ocr: bool = False,
) -> Artifact:
    text_content = content or ""
    ocr_note = None
    if file_path or use_ocr:
        text, err = extract_text(file_path or "")
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
        or any(term in lowered for term in _PRODUCT_TERMS)
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
    if item_brand:
        fields["brand"] = item_brand
        confidence["brand"] = 0.85
        alternatives["product_line"] = [best_item] if best_item else []
    elif brand_match:
        cleaned = _clean_brand_candidate(brand_match.group(1))
        if cleaned:
            fields["brand"] = cleaned
            confidence["brand"] = 0.8
    elif has_warranty_context:
        # Strategy 2: First non-empty line (usually company name on invoices)
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if (
                len(line) > 3
                and not line.lower().startswith(('invoice', 'bill', 'receipt', 'tax', 'gst', 'date'))
                and not _is_boilerplate_line(line)
                and not _has_product_signal(line)
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
    model_match = re.search(r"(?:model|mode[li1])\s*[:\-#]\s*([a-zA-Z0-9\-]{2,30})", text, re.IGNORECASE)
    if model_match:
        fields["model_code"] = model_match.group(1).strip().upper()
        confidence["model_code"] = 0.7
    else:
        item_model = _model_from_product_line(best_item or "", fields.get("brand"))
        if item_model:
            fields["model_code"] = item_model
            confidence["model_code"] = 0.75
        else:
        # Fallback model signal from common invoice token shapes.
            model_token = re.search(r"\b([A-Z]{2,}[A-Z0-9\-]{2,})\b", text)
            if model_token:
                token = model_token.group(1).strip().upper()
                if token not in (
                    "GST", "HSN", "SAC", "INR", "CGST", "SGST", "IGST",
                    "INVOICE", "BILL", "RETAIL", "TAX", "CUSTOMER", "COPY", "TOTAL",
                    "ORIGINAL", "RECIPIENT", "DESCRIPTION", "QUANTITY", "AMOUNT",
                ) and re.search(r"\d", token) and not _is_spec_only(token):
                    fields["model_code"] = token
                    confidence["model_code"] = 0.4

    # === SERIAL NUMBER ===
    serial_value = _serial_from_lines(logical_lines + lines, line_items[0][1] if line_items else None)
    if serial_value:
        fields["serial_no"] = serial_value
        confidence["serial_no"] = 0.7

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

    fields, confidence, alternatives = sanitize_invoice_identity_fields(fields, confidence, alternatives)

    if not confidence:
        alternatives["notes"] = ["No strong signals found; manual entry may be required."]

    return fields, confidence, alternatives
