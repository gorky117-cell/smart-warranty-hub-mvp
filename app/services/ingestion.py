import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import Artifact, ArtifactType
from ..storage import generate_id, store
from .ocr import extract_text


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
    
    # Pattern 2: Numeric dates (24-12-2025, 24/12/2025, 2025-12-24)
    numeric_candidates = re.findall(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", text
    )
    for raw in numeric_candidates:
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
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

    # === BRAND EXTRACTION ===
    # Strategy 1: Explicit "Brand:" label
    brand_match = re.search(r"brand\s*[:\-]\s*([a-zA-Z0-9 \-]{2,40})", text, re.IGNORECASE)
    if brand_match:
        raw_brand = brand_match.group(1).strip()
        # Trim if the model label leaked into the brand capture
        lower = raw_brand.lower()
        if " model" in lower:
            raw_brand = raw_brand[: lower.index(" model")].strip()
        fields["brand"] = raw_brand.title()
        confidence["brand"] = 0.8
    else:
        # Strategy 2: First non-empty line (usually company name on invoices)
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if len(line) > 3 and not line.lower().startswith(('invoice', 'bill', 'receipt', 'tax', 'gst', 'date')):
                # Clean up common suffixes
                cleaned = re.sub(r'\s*(Pvt\.?|Ltd\.?|Private|Limited|Inc\.?|LLC|Corp\.?).*$', '', line, flags=re.IGNORECASE).strip()
                if cleaned and len(cleaned) >= 3:
                    fields["brand"] = cleaned.title()
                    confidence["brand"] = 0.6
                    break

    # === PRODUCT NAME EXTRACTION ===
    # Strategy 1: Explicit "Product:" or "Item:" label
    product_match = re.search(r"(?:product|item name|device)\s*[:\-]\s*([a-zA-Z0-9 \-\.]{3,60})", text, re.IGNORECASE)
    if product_match:
        val = product_match.group(1).strip()
        # Exclude header keywords
        if val.lower() not in ('description', 'hsn', 'sac', 'qty', 'price', 'tax', 'total'):
            fields["product_name"] = val.title()
            confidence["product_name"] = 0.7
    
    # Strategy 2: Look for product patterns in line items (e.g., "1. Samsung Galaxy S24")
    if "product_name" not in fields:
        item_pattern = r"(?:^|\n)\s*\d+[\.\)]\s*([A-Z][a-zA-Z0-9 \-]{5,50}?)(?:\s+\d|\s+[A-Z]{2,5}\d|\s*$)"
        item_match = re.search(item_pattern, text)
        if item_match:
            val = item_match.group(1).strip()
            if val.lower() not in ('description', 'hsn', 'sac', 'qty', 'price', 'tax', 'total'):
                fields["product_name"] = val.title()
                confidence["product_name"] = 0.5

    # === MODEL CODE ===
    model_match = re.search(r"model\s*[:\-#]\s*([a-zA-Z0-9\-]{2,30})", text, re.IGNORECASE)
    if model_match:
        fields["model_code"] = model_match.group(1).strip().upper()
        confidence["model_code"] = 0.7

    # === SERIAL NUMBER ===
    serial_match = re.search(r"(?:serial|s/n|sn|imei)\s*[:\-#]?\s*([a-zA-Z0-9\-]{6,})", text, re.IGNORECASE)
    if serial_match:
        fields["serial_no"] = serial_match.group(1).strip().upper()
        confidence["serial_no"] = 0.7

    # === PURCHASE DATE ===
    # Look specifically for "Date:" labeled date first
    date_label_match = re.search(r"(?:date|invoice date|purchase date)\s*[:\-]\s*(.{8,20})", text, re.IGNORECASE)
    if date_label_match:
        date_str = parse_date_from_text(date_label_match.group(1))
        if date_str:
            fields["purchase_date"] = date_str
            confidence["purchase_date"] = 0.8
    
    # Fallback: Any date in text
    if "purchase_date" not in fields:
        date_str = parse_date_from_text(text)
        if date_str:
            fields["purchase_date"] = date_str
            confidence["purchase_date"] = 0.5

    # === INVOICE NUMBER ===
    inv_match = re.search(r"(?:invoice|inv|bill)\s*(?:no|number|#)?\s*[:\-]?\s*([a-zA-Z0-9\-/]{3,20})", text, re.IGNORECASE)
    if inv_match:
        fields["invoice_no"] = inv_match.group(1).strip().upper()
        confidence["invoice_no"] = 0.7

    # === WARRANTY DURATION ===
    warranty_match = re.search(r"(\d{1,2})\s*(?:year|yr|month|mo)s?\s*warranty", text, re.IGNORECASE)
    if warranty_match:
        val = int(warranty_match.group(1))
        if "year" in text.lower() or "yr" in text.lower():
            val = val * 12
        fields["coverage_months"] = str(val)
        confidence["coverage_months"] = 0.7

    if not confidence:
        alternatives["notes"] = ["No strong signals found; manual entry may be required."]

    return fields, confidence, alternatives
