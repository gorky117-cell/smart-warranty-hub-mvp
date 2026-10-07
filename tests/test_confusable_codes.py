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


# Backlog #6: a better confirm step - characters to check, a known reading offered, customer-confirmed models.
from app.db_models import WarrantyDB, WarrantyOwnerDB  # noqa: E402
from app.services.ingestion import confusable_positions, known_reading  # noqa: E402


def test_characters_to_check_are_listed():
    assert confusable_positions("MTPO3HN/A") == [3]
    assert confusable_positions("82RKOOVWIN") == [0, 4, 5, 8]
    assert confusable_positions("KD-X74L") == []
    _f, _c, alts = _route(model="MTPO3HN/A")
    assert alts["model_suggestion"]["check_characters"] == [3]


@pytest.mark.parametrize("read,known,expected", [
    ("82RKOOVWIN", {"82RK00VWIN"}, "82RK00VWIN"),       # laptop: O read for 0
    ("SMM17SF", {"SMM175F"}, "SMM175F"),               # phone: S read for 5
    ("UA32T438OAKXXL", {"UA32T4380AKXXL"}, "UA32T4380AKXXL"),  # TV
    ("AR18BY5ZABUNNA", {"AR188Y5ZABUNNA"}, "AR188Y5ZABUNNA"),  # AC: B read for 8
    ("WA-H642", {"WAH642"}, None),                    # no confusable character in the difference
    ("OB1", {"0B1", "081"}, None),                     # two known readings: do not pick one
])
def test_known_reading_only_when_exactly_one_matches(read, known, expected):
    assert known_reading(read, known) == expected


def test_a_known_reading_is_offered_but_still_confirmed():
    fields, _c, alts = _route(model="82RKOOVWIN", known={"82RK00VWIN"})
    assert "model_code" not in fields  # never stored without the customer
    s = alts["model_suggestion"]
    assert s["value"] == "82RK00VWIN" and s["read_as"] == "82RKOOVWIN" and s["status"] == "pending"
    assert "looks like 82RK00VWIN" in s["reason"]
    # Punctuation of the known model is kept for display.
    _f, _c, alts = _route(model="SM-M17SF", known={"SM-M175F"})
    assert alts["model_suggestion"]["value"] == "SM-M175F"


def _owned(wid, user, brand, model, conf):
    with SessionLocal() as db:
        db.query(WarrantyOwnerDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, brand=brand, model_code=model, confidence={"model_code": conf}, alternatives={}))
        db.add(WarrantyOwnerDB(user_id=user, warranty_id=wid))
        db.commit()


def test_models_confirmed_by_two_customers_become_known():
    brand = "ConfirmCo"
    _owned("wty_cc_1", "cc_user_a", brand, "QX5O0", 0.95)
    _owned("wty_cc_2", "cc_user_a", brand, "QX5O0", 0.95)  # same customer twice: still one
    with SessionLocal() as db:
        assert "QX5O0" not in known_models(db, brand)
    _owned("wty_cc_3", "cc_user_b", brand, "QX5O0", 0.7)  # read by OCR, not confirmed
    with SessionLocal() as db:
        assert "QX5O0" not in known_models(db, brand)
    _owned("wty_cc_4", "cc_user_c", brand, "QX5O0", 0.95)
    with SessionLocal() as db:
        assert "QX5O0" in known_models(db, "confirmco")
        assert "QX5O0" not in known_models(db, "OtherCo")


def test_dashboard_highlights_characters_to_check():
    html = open("templates/neo_dashboard.html", encoding="utf-8").read()
    assert "function fillCheckedCode" in html and "check_characters" in html and "mark.check-char" in html
