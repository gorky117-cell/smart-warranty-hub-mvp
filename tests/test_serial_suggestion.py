"""Serial suggestions from misread labels are confirmed by the user (fix run B5). Synthetic data."""

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.main import app
from app.services import invoice_pipeline
from app.services.ingestion import extract_product_fields

MISREAD = "Apple Authorized Store\nTAX INVOICE\nProduct iPhone 15\nseriat SNO01X1001\nWarranty 12 months"
LABELLED = "Apple Authorized Store\nTAX INVOICE\nProduct iPhone 15\nSerial No: SN001X1001\nWarranty 12 months"
EPSON = "Tax Invoice\nThe Print Mall\n1 Epson L 3250 Printer 84433240 1no 13,200.00 11,186.44\nXAHT699208\nDated 1-Jul-25"


def test_kinds_of_serial_evidence():
    f, _c, a = extract_product_fields(MISREAD)
    assert "serial_no" not in f and a["serial_suggestion"]["value"] == "SNO01X1001"
    f, c, a = extract_product_fields(LABELLED)
    assert f["serial_no"] == "SN001X1001" and c["serial_no"] == 0.7 and "serial_suggestion" not in a
    f, c, _a = extract_product_fields(EPSON)
    assert f["serial_no"] == "XAHT699208" and c["serial_no"] == 0.5  # narrow Epson exception kept


def _seed(wid, alternatives, serial=None):
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, product_name="iPhone 15", serial_no=serial, alternatives=alternatives, confidence={}))
        db.commit()


def _admin_token(client):
    return client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]


def test_confirm_with_correction_and_dismiss():
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {_admin_token(client)}"}
    suggestion = {"serial_suggestion": {"value": "SNO01X1001", "source_line": "seriat SNO01X1001", "status": "pending"}}

    _seed("wty_serial_confirm", dict(suggestion))
    resp = client.post("/warranties/wty_serial_confirm/serial-suggestion", json={"action": "confirm", "value": "sn001x1001"}, headers=auth)
    assert resp.status_code == 200
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id="wty_serial_confirm").first()
        assert row.serial_no == "SN001X1001" and row.confidence["serial_no"] == 0.95
        assert row.alternatives["serial_suggestion"]["status"] == "confirmed"

    _seed("wty_serial_dismiss", dict(suggestion))
    resp = client.post("/warranties/wty_serial_dismiss/serial-suggestion", json={"action": "dismiss"}, headers=auth)
    assert resp.status_code == 200
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id="wty_serial_dismiss").first()
        assert row.serial_no is None and row.alternatives["serial_suggestion"]["status"] == "dismissed"

    assert client.post("/warranties/wty_serial_dismiss/serial-suggestion", json={"action": "confirm", "value": "bad value!"}, headers=auth).status_code == 422
    assert client.post("/warranties/wty_serial_dismiss/serial-suggestion", json={"action": "x"}, headers=auth).status_code == 422


def test_reprocessing_never_overrides_user_decision_or_clears_confirmed_serial():
    confirmed = {"serial_suggestion": {"value": "SNO01X1001", "status": "confirmed", "confirmed_value": "SN001X1001"}}
    _seed("wty_serial_keep", confirmed, serial="SN001X1001")
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_serial_keep").first().confidence = {"serial_no": 0.95}
        db.commit()
        fields, conf, alt = extract_product_fields(MISREAD)
        row = invoice_pipeline._update_warranty(db, "wty_serial_keep", fields, conf, alt)
        assert row.serial_no == "SN001X1001"
        assert row.alternatives["serial_suggestion"]["status"] == "confirmed"


def test_pending_suggestion_dropped_when_labelled_serial_found():
    _seed("wty_serial_relabel", {"serial_suggestion": {"value": "SNO01X1001", "status": "pending"}})
    with SessionLocal() as db:
        fields, conf, alt = extract_product_fields(LABELLED)
        row = invoice_pipeline._update_warranty(db, "wty_serial_relabel", fields, conf, alt)
        assert row.serial_no == "SN001X1001" and "serial_suggestion" not in row.alternatives
