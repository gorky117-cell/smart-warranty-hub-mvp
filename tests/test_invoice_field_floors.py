"""Per-field accuracy floors on the labelled 50-sample invoice set (work plan step 6).

Floors are the exact-match counts measured on 2026-10-03 (MEMORY.md 90.6). A change that lowers any
`correct` count, raises a `wrong` count, or reintroduces `TAKINVOICE` fails here. Raise a floor when
a change genuinely improves it. Samples are synthetic.

- `test_field_floors_on_cached_ocr_text` scores the captured OCR text, so it checks extraction code
  deterministically on any machine.
- `test_field_floors_with_real_ocr` re-runs real image OCR (needs Tesseract; ~30 s).
"""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from app.services import ocr

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("measure_invoice_fields", ROOT / "scripts" / "measure_invoice_fields.py")
measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure)

ROWS = list(csv.DictReader(open(ROOT / "test_data" / "ingestion_ocr_50_labeled.csv", encoding="utf-8")))
CACHED = json.loads((ROOT / "tests" / "fixtures" / "ocr_text_50.json").read_text(encoding="utf-8"))["samples"]

# Minimum correct per field, `normal` case (30 labelled synthetic images), measured 2026-10-03.
MIN_CORRECT = {
    "brand": 26,
    "model_code": 0,  # 2 before follow-up step 2: misread-label models ("Madet X") are now suggestions
    "purchase_date": 24,
    "serial_no": 0,
    "invoice_no": 0,
    "coverage_months": 16,
    "product_category": 26,
}
# Maximum confidently-wrong values per field, same set.
MAX_WRONG = {
    "brand": 0,
    "model_code": 0,  # was 1 before follow-up step 2
    "purchase_date": 6,
    "serial_no": 0,  # was 30 before fix run B5 (misread-label values are now suggestions)
    "invoice_no": 0,
    "coverage_months": 14,
    "product_category": 0,
}


# Minimum suggestions offered for confirmation instead of a stored value (follow-up step 2).
MIN_SUGGESTIONS = {"model_code": 28, "serial_no": 30}


def _assert_floors(report):
    normal = report["fields_by_case"]["normal"]
    for field, floor in MIN_SUGGESTIONS.items():
        offered = normal[field].get("suggestion_exact", 0) + normal[field].get("suggestion_needs_edit", 0)
        assert offered >= floor, (field, normal[field])
    for field in measure.FIELDS:
        counts = normal[field]
        assert counts.get("correct", 0) >= MIN_CORRECT[field], (field, counts)
        assert counts.get("wrong", 0) <= MAX_WRONG[field], (field, counts)
        assert counts.get("takinvoice", 0) == 0, (field, counts)
    assert report["non_warranty_false_positive_fields"] == {}


def test_field_floors_on_cached_ocr_text():
    _assert_floors(measure.score(ROWS, CACHED))


# Real OCR after small text is enlarged for Tesseract (cloud batch 2, backlog #16): measured 30/30 with none
# wrong for these fields in the cloud container (Tesseract 5.3.4); a margin of 2 allows other Tesseract builds.
REAL_OCR_MIN_CORRECT = {"brand": 28, "purchase_date": 28, "invoice_no": 28, "coverage_months": 28}
REAL_OCR_MAX_WRONG = {"purchase_date": 1, "coverage_months": 1}


@pytest.mark.skipif(not ocr._tesseract_ready()[0], reason="Tesseract not installed")
def test_field_floors_with_real_ocr():
    report = measure.score(ROWS, measure.ocr_texts(ROWS, ROOT))
    _assert_floors(report)
    normal = report["fields_by_case"]["normal"]
    for field, floor in REAL_OCR_MIN_CORRECT.items():
        assert normal[field].get("correct", 0) >= floor, (field, normal[field])
    for field, ceiling in REAL_OCR_MAX_WRONG.items():
        assert normal[field].get("wrong", 0) <= ceiling, (field, normal[field])
