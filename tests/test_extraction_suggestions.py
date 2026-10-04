"""Follow-up step 2: printed model codes, unknown brands and label misreads become suggestions;
unreadable invoices show a message instead of estimated coverage. Synthetic data."""

from fastapi.testclient import TestClient
from PIL import Image

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.main import app
from app.models import ArtifactType
from app.services import invoice_pipeline
from app.services.canonical import canonicalize_artifact
from app.services.ingestion import extract_product_fields, ingest_artifact, route_uncertain_identity

TEXT_PDF = """ELECTRA MART INVOICE
Invoice No: INV-2026-00145
Date: 22-Jan-2026
PRODUCT DETAILS:
Samsung Galaxy S24 Ultra
Model Code: SM-S928BZKGINS
Serial Number: R5CX40VP8LA
Warranty: 12 Months"""
SCANNED = "UG Authorized Store\nTAXINVOICE\nInvoice Not INV-2025-0002\nDate: 11-Jan-2025\nProduct OLEDS5C3\nBrand: Lo\nModet OLEDSS-002\nSeriat sN002x1002\nWarranty. 12 months manufacturer warranty"
PHOTO = "Apple Authorized Store\nTAKINVOICE\nInvoice Ne INV:2026-0001\nDate: 06-Jan-2025\nProduct iPhone 15\nBand: Apple\nMad IPHONEOO1\nseriat SNO01X1001\nWarranty 38 months manufacturer warranty"


def test_printed_model_code_beats_marketing_name():
    fields, conf, alt = extract_product_fields(TEXT_PDF)
    assert fields["model_code"] == "SM-S928BZKGINS" and conf["model_code"] == 0.8
    assert fields["product_name"] == "Samsung Galaxy S24 Ultra"  # marketing name kept as product name
    assert "model_suggestion" not in alt


def test_printed_code_on_the_same_line_as_the_marketing_name():
    fields, _c, _a = extract_product_fields("Tax Invoice\n1 Samsung Galaxy S24 Ultra SM-S928BZKGINS Mobile 1 Nos 1,29,999.00")
    assert fields["model_code"] == "SM-S928BZKGINS"


def test_marketing_name_alone_is_still_stored():
    fields, _c, alt = extract_product_fields("Tax Invoice\n1 Samsung Galaxy M17e 5G Mobile 1 Nos 12,999.00")
    assert fields["model_code"] == "M17E" and alt["model_evidence"] == "marketing_name"


def test_unknown_brand_becomes_a_suggestion():
    fields, _c, alt = extract_product_fields(SCANNED)
    assert "brand" not in fields
    assert alt["brand_suggestion"]["value"] == "Lo" and alt["brand_suggestion"]["status"] == "pending"
    assert alt["model_suggestion"]["value"] == "OLEDSS-002"  # misread "Model" label
    assert alt["serial_suggestion"]["value"] == "SN002X1002"


def test_label_misread_is_never_the_product_name():
    fields, _c, alt = extract_product_fields(PHOTO)
    assert fields["product_name"] == "iPhone 15"
    assert fields["brand"] == "Apple"
    assert alt["model_suggestion"]["value"] == "IPHONEOO1" and "model_code" not in fields
    for line in ("Band: Apple", "Brand: Sony", "Modet: WMEKG-004", "Seriat: SN1"):
        fields, _c, _a = extract_product_fields(f"Tax Invoice\n{line}\nDate: 01-01-2025")
        assert fields.get("product_name") != line


def test_ordinary_product_words_are_not_taken_for_labels():
    fields, _c, _a = extract_product_fields("Tax Invoice\n1 Data Cable USB-C 1m Mobile Accessory 1 Nos 299.00")
    assert "Data Cable" in (fields.get("product_name") or "")


def test_low_confidence_values_route_to_suggestions_but_epson_and_user_values_stay():
    fields, conf, alt = route_uncertain_identity(
        {"brand": "Acmeco", "model_code": "ZX1", "serial_no": "AB12345"},
        {"brand": 0.8, "model_code": 0.4, "serial_no": 0.95},
        {},
    )
    assert fields == {"serial_no": "AB12345"}
    assert alt["brand_suggestion"]["value"] == "Acmeco" and alt["model_suggestion"]["value"] == "ZX1"
    epson = "Tax Invoice\nThe Print Mall\n1 Epson L 3250 Printer 84433240 1no 13,200.00 11,186.44\nXAHT699208\nDated 1-Jul-25"
    fields, _c, _a = extract_product_fields(epson)
    assert fields["serial_no"] == "XAHT699208"


def _blank_upload(tmp_path):
    path = tmp_path / "blurred.png"
    Image.new("RGB", (400, 300), "white").save(path)
    artifact = ingest_artifact(ArtifactType.invoice, content="", use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=warranty.id).first()
        row.coverage_months = 12  # what the old default-rules path stored
        db.commit()
        job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=str(path))
    invoice_pipeline.run_job(job.id)
    return warranty.id


def test_unreadable_invoice_shows_message_not_estimated_coverage(tmp_path):
    wid = _blank_upload(tmp_path)
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        assert row.coverage_months is None and row.expiry_date is None
        assert row.alternatives["unreadable_invoice"]["message"] == invoice_pipeline.UNREADABLE_MESSAGE
        assert row.alternatives["terms_source_type"] == "unreadable"
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    body = client.get(f"/warranties/{wid}", headers=auth).json()
    assert body["evidence_status"]["status"] == "unreadable"
    assert body["evidence_status"]["note"] == invoice_pipeline.UNREADABLE_MESSAGE


def test_manual_details_clear_the_unreadable_state(tmp_path, monkeypatch):
    wid = _blank_upload(tmp_path)
    monkeypatch.setattr(invoice_pipeline, "lookup_terms", lambda *a, **k: None)
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.post(f"/warranties/{wid}/manual-details", json={}, headers=auth).status_code == 422
    assert client.post(f"/warranties/{wid}/manual-details", json={"purchase_date": "05/01/2025"}, headers=auth).status_code == 422
    resp = client.post(
        f"/warranties/{wid}/manual-details",
        json={"brand": "apple", "product_name": "iPhone 15", "serial_no": "sn001x1001", "purchase_date": "2025-01-06"},
        headers=auth,
    )
    assert resp.status_code == 200
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        assert row.brand == "Apple" and row.serial_no == "SN001X1001" and row.confidence["brand"] == 0.95
        assert "unreadable_invoice" not in row.alternatives
        assert row.alternatives["terms_source_type"] == "invoice_only"


def test_field_suggestion_endpoint_confirms_brand_and_model():
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_field_sugg").delete()
        db.add(WarrantyDB(id="wty_field_sugg", product_name="OLED TV", confidence={}, alternatives={
            "brand_suggestion": {"value": "Lo", "status": "pending"},
            "model_suggestion": {"value": "OLEDSS-002", "status": "pending"},
        }))
        db.commit()
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    url = "/warranties/wty_field_sugg/field-suggestion"
    assert client.post(url, json={"field": "price", "action": "confirm"}, headers=auth).status_code == 422
    assert client.post(url, json={"field": "brand", "action": "confirm", "value": "lg"}, headers=auth).json()["brand"] == "LG"
    assert client.post(url, json={"field": "model_code", "action": "confirm", "value": "oled55-002"}, headers=auth).json()["model_code"] == "OLED55-002"
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id="wty_field_sugg").first()
        assert (row.brand, row.model_code) == ("LG", "OLED55-002")
        assert row.confidence == {"brand": 0.95, "model_code": 0.95}
        assert row.alternatives["brand_suggestion"]["status"] == "confirmed"
