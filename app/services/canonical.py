from datetime import date
from typing import Dict, Optional

from ..models import Artifact, CanonicalWarranty
from ..storage import generate_id, store
from .ingestion import extract_product_fields


def add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(
        start.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
            month - 1
        ],
    )
    return date(year, month, day)


def canonicalize_artifact(
    artifact: Artifact, overrides: Optional[Dict[str, str]] = None
) -> CanonicalWarranty:
    fields, confidence, alternatives = extract_product_fields(artifact.content)
    overrides = overrides or {}
    for key, value in overrides.items():
        fields[key] = value
        confidence[key] = max(confidence.get(key, 0.0), 0.9)

    purchase_date = None
    if "purchase_date" in fields:
        try:
            purchase_date = date.fromisoformat(str(fields["purchase_date"]))
        except ValueError:
            purchase_date = None

    coverage_months = None
    if "coverage_months" in fields:
        try:
            coverage_months = int(fields["coverage_months"])
        except (TypeError, ValueError):
            coverage_months = None

    expiry_date = None
    if purchase_date and coverage_months:
        expiry_date = add_months(purchase_date, coverage_months)

    warranty = CanonicalWarranty(
        id=generate_id("wty"),
        product_name=fields.get("product_name"),
        brand=fields.get("brand"),
        model_code=fields.get("model_code"),
        serial_no=fields.get("serial_no"),
        purchase_date=purchase_date,
        coverage_months=coverage_months,
        expiry_date=expiry_date,
        terms=[
            "Base parts and labour coverage within stated period.",
            "Firmware support updates included where applicable.",
        ],
        exclusions=[
            "Physical or liquid damage.",
            "Unauthorised repair or tampering.",
            "Improper installation or maintenance outside guidance.",
        ],
        claim_steps=[
            "Keep invoice or receipt ready.",
            "Share serial/model information with support.",
            "Provide error evidence (photos or logs) for faster triage.",
        ],
        confidence=confidence,
        alternatives=alternatives,
        source_artifact_ids=[artifact.id],
    )
    return store.add_warranty(warranty)
