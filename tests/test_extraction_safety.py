"""Extraction safety (work plan step 3): serial fallback, field clearing on re-processing."""

import json
from pathlib import Path

import pytest

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.services import invoice_pipeline
from app.services.ingestion import _serial_from_lines, extract_product_fields

_OCR = json.loads((Path(__file__).parent / "fixtures" / "ocr_text_S001_S012.json").read_text(encoding="utf-8"))
_SAMPLES = sorted(k for k in _OCR if not k.startswith("_"))


@pytest.mark.parametrize("sample_id", _SAMPLES)
def test_ocr_samples_never_store_invoice_header_as_serial(sample_id):
    text = _OCR[sample_id]["text"] or ""
    fields, confidence, _ = extract_product_fields(text)

    serial = fields.get("serial_no")
    assert serial != "TAKINVOICE"
    assert "INVOIC" not in (serial or "")
    if serial:
        # Must come from the line carrying a serial label (OCR reads "Serial" as seriat/seria:/seri).
        label_line = next(line for line in text.splitlines() if line.lower().startswith("seri"))
        assert serial in label_line.upper()
        assert confidence["serial_no"] == 0.5


def test_ocr_sample_s001_misread_label_gives_suggestion_not_serial():
    fields, confidence, alternatives = extract_product_fields(_OCR["S001"]["text"])
    assert "serial_no" not in fields  # fix run B5: misread label -> unconfirmed suggestion
    suggestion = alternatives["serial_suggestion"]
    assert suggestion["value"] == "SNO01X1001"  # truth SN001X1001; OCR reads 0 as O
    assert suggestion["status"] == "pending" and suggestion["source_line"].startswith("seriat")


@pytest.mark.parametrize(
    "lines,expected",
    [
        (["Serial No: AB12345678"], ("AB12345678", 0.7)),
        (["S/N - XYZ987654"], ("XYZ987654", 0.7)),
        (["IMEI: 356789104512345X"], ("356789104512345X", 0.7)),
        (["Serial Number:", "QW12ER34TY"], ("QW12ER34TY", 0.7)),
        (["seriat SN001X1001"], ("SN001X1001", 0.5)),
    ],
)
def test_serial_accepted_only_next_to_label(lines, expected):
    assert _serial_from_lines(lines, None) == expected


@pytest.mark.parametrize(
    "lines,product_line",
    [
        (["'Apple Authorized Store", "TAKINVOICE", "Invoice Ne INV:2026-0001"], "'Apple Authorized Store"),
        (["TAX INVOICE", "Product iPhone 15"], None),
        (["Serial: TAXINVOICE1"], None),
        (["Series 7 Washer", "AB12345678"], None),
        (["HSN:85171300", "Serial No: 12-05-2026"], None),
        (["1 Widget 499.00", "INVOICE"], "1 Widget 499.00"),
    ],
)
def test_serial_left_blank_when_unsure(lines, product_line):
    assert _serial_from_lines(lines, product_line) == (None, 0.0)


def test_unlabelled_serial_directly_under_line_item_kept_with_low_confidence():
    lines = ["1 Epson L 3250 Printer 84433240 1no 13,200.00 11,186.44", "XAHT699208"]
    assert _serial_from_lines(lines, lines[0]) == ("XAHT699208", 0.5)


def _seed(warranty_id, **values):
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id=warranty_id).delete()
        db.add(WarrantyDB(id=warranty_id, **values))
        db.commit()


def test_reprocess_clears_lower_confidence_field_found_absent():
    warranty_id = "wty_step3_clear"
    _seed(
        warranty_id,
        product_name="iPhone 15",
        brand="Apple",
        serial_no="TAKINVOICE",
        confidence={"brand": 0.85, "serial_no": 0.7},
    )
    with SessionLocal() as db:
        warranty = invoice_pipeline._update_warranty(
            db, warranty_id, {"brand": "Apple", "product_name": "iPhone 15"}, {"brand": 0.85, "product_name": 0.75}, {}
        )
        assert warranty.serial_no is None
        assert warranty.brand == "Apple"
        assert "serial_no" not in warranty.confidence
        assert warranty.alternatives["cleared_on_reprocess"] == ["serial_no"]
        db.query(WarrantyDB).filter_by(id=warranty_id).delete()
        db.commit()


def test_reprocess_keeps_user_override_and_ignores_legacy_calls():
    warranty_id = "wty_step3_keep"
    _seed(warranty_id, product_name="Washer", serial_no="USER123456", confidence={"serial_no": 0.9})
    with SessionLocal() as db:
        warranty = invoice_pipeline._update_warranty(db, warranty_id, {"product_name": "Washer"}, {"product_name": 0.75})
        assert warranty.serial_no == "USER123456"

        # Without a pass confidence (legacy call shape) nothing is ever cleared.
        warranty.confidence = {}
        db.commit()
        warranty = invoice_pipeline._update_warranty(db, warranty_id, {"product_name": "Washer"})
        assert warranty.serial_no == "USER123456"
        db.query(WarrantyDB).filter_by(id=warranty_id).delete()
        db.commit()
