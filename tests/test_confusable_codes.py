"""Owner decision 3: codes from scans/photos with O/0, I/1, S/5, B/8 are "please confirm" unless validated."""

import pytest

from app.db import SessionLocal
from app.db_models import VerifiedTermsDB
from app.services.ingestion import from_ocr, route_confusable_codes
from app.services.invoice_pipeline import known_models

OCR = {"method": "tesseract"}


def _route(model=None, serial=None, ocr=True, known=None, conf=0.7):
    fields = {k: v for k, v in (("model_code", model), ("serial_no", serial)) if v}
    confidence = {k: conf for k in fields}
    return route_confusable_codes(fields, confidence, {}, ocr=ocr, known_models=known)


@pytest.mark.parametrize("method,ocr", [
    ("tesseract", True), ("paddle", True), ("tesseract_fallback", True), ("pdf_ocr", True), ("ocr", True),
    ("pdf", False), ("text", False), ("docx", False), (None, False),
])
def test_what_counts_as_read_from_a_scan_or_photo(method, ocr):
    assert from_ocr({"method": method}) is ocr


@pytest.mark.parametrize("model", ["MTPO3HN/A", "82RKOOVWIN", "SM-M175F", "UA32T4380AKXXL", "TS-QI9YNZE"])
def test_ocr_models_with_confusable_characters_become_please_confirm(model):
    fields, _c, alts = _route(model=model)
    assert "model_code" not in fields
    assert alts["model_suggestion"]["value"] == model and alts["model_suggestion"]["status"] == "pending"
    assert "O/0, I/1, S/5 and B/8" in alts["model_suggestion"]["reason"]


@pytest.mark.parametrize("model", ["KD-X74L", "WA-HG42JD", "GL-T292RPZY"])  # no confusable characters: kept as read
def test_ocr_models_without_confusable_characters_are_kept(model):
    fields, _c, _a = _route(model=model)
    assert fields["model_code"] == model


def test_known_model_and_valid_imei_are_kept():
    fields, _c, alts = _route(model="SM-M175F", serial="352099001761481", known={"SMM175F"})
    assert fields == {"model_code": "SM-M175F", "serial_no": "352099001761481"} and alts == {}
    fields, _c, alts = _route(serial="352099001761482")  # 15 digits that fail Luhn
    assert "serial_no" not in fields and alts["serial_suggestion"]["status"] == "pending"
    fields, _c, alts = _route(serial="OC1A3CBR12345X")  # a TV serial read as O instead of 0
    assert "serial_no" not in fields


def test_text_layer_pdfs_and_confirmed_values_are_never_touched():
    assert _route(model="SM-M175F", ocr=False)[0] == {"model_code": "SM-M175F"}
    assert _route(model="SM-M175F", conf=0.95)[0] == {"model_code": "SM-M175F"}  # confirmed by the customer


def test_known_models_come_from_hand_checked_entries():
    with SessionLocal() as db:
        db.query(VerifiedTermsDB).filter_by(company="ConfusableCo").delete()
        db.add(VerifiedTermsDB(company="ConfusableCo", product_scope="model:AB1050", source_url="https://x.example/",
                               verified_by="admin", terms=[], exclusions=[], claim_steps=[]))
        db.commit()
        assert "AB1050" in known_models(db, "confusableco")
        assert known_models(db, None) == set()
