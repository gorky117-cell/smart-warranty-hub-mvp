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
    candidates = re.findall(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", text
    )
    for raw in candidates:
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
    return None


def extract_product_fields(text: str) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, List[str]]]:
    lowered = text.lower()
    fields: Dict[str, str] = {}
    confidence: Dict[str, float] = {}
    alternatives: Dict[str, List[str]] = {}

    brand_match = re.search(r"brand[:\s]+([a-z0-9 \-]{2,40})", lowered, re.IGNORECASE)
    if brand_match:
        fields["brand"] = brand_match.group(1).strip().title()
        confidence["brand"] = 0.7

    model_match = re.search(r"model[:\s]+([a-z0-9\-]{2,50})", lowered, re.IGNORECASE)
    if model_match:
        fields["model_code"] = model_match.group(1).strip().upper()
        confidence["model_code"] = 0.65

    serial_match = re.search(
        r"(serial|s\/n|sn)[:\s-]*([a-z0-9\-]{6,})", lowered, re.IGNORECASE
    )
    if serial_match:
        fields["serial_no"] = serial_match.group(2).strip().upper()
        confidence["serial_no"] = 0.6

    purchase_date = parse_date_from_text(text)
    if purchase_date:
        fields["purchase_date"] = purchase_date
        confidence["purchase_date"] = 0.6

    if "warranty" in lowered:
        months_match = re.search(r"(\d{1,2})\s*(month|months|mo)\b", lowered)
        if months_match:
            fields["coverage_months"] = months_match.group(1)
            confidence["coverage_months"] = 0.6

    if not confidence:
        alternatives["notes"] = [
            "No strong signals found; manual confirmation required."
        ]

    return fields, confidence, alternatives
