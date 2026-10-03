"""AI vision tier for low-text invoice images (fix run B10). Images are generated, people fictitious,
the AI provider is mocked; image redaction uses real Tesseract."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.db import SessionLocal
from app.db_models import PipelineJobDB, WarrantyDB, WarrantyOwnerDB
from app.main import _placeholder_upload_warranty, app
from app.models import ArtifactType
from app.services import invoice_pipeline, ocr
from app.services import vision_extraction as vx
from app.services.ingestion import ingest_artifact

needs_tesseract = pytest.mark.skipif(not ocr._tesseract_ready()[0], reason="Tesseract not installed")


def _image(lines, path=None):
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default(size=30)
    img = Image.new("RGB", (900, 70 + 50 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 30 + 50 * i), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    if path:
        path.write_bytes(buf.getvalue())
    return buf.getvalue()


def _ocr_png(png):
    import pytesseract

    return pytesseract.image_to_string(Image.open(io.BytesIO(png)))


@needs_tesseract
def test_redacted_image_hides_buyer_and_keeps_identifiers():
    raw = _image(["Bill To: Asha Verma", "Mobile: 9876543210", "Invoice No: SE/2026/0417", "Model: SM-X100"])
    png, info = vx.redact_image(raw)
    assert png is not None and info["tokens_masked"] >= 3
    text = _ocr_png(png)
    assert "Asha" not in text and "Verma" not in text and "9876543210" not in text
    assert "SE/2026/0417" in text and "SM-X100" in text


def test_image_without_locatable_text_is_never_sent(monkeypatch):
    calls = []
    monkeypatch.setattr(vx, "_locate_words", lambda image: [])
    png, info = vx.redact_image(_image([]))
    assert png is None and info["reason"] == "no_locatable_text"


def test_validation_grounds_or_suggests_never_trusts_unquoted_values():
    payload = {
        "brand": {"value": "Samsung", "source_line": "Samsung Authorised Store", "confidence": 0.9},
        "serial_no": {"value": "R58N12ABCDE", "source_line": "S/N R58N12ABCDE", "confidence": 0.8},
        "model_code": {"value": "SM-X100", "source_line": "Invoice No 17", "confidence": 0.9},
        "invoice_no": {"value": "17", "source_line": "Invoice No 17", "confidence": 0.2},
        "product_name": {"value": "", "source_line": "", "confidence": 0},
        "purchase_date": {"value": "12-03-2026", "source_line": "[REDACTED] 12-03-2026", "confidence": 0.9},
    }
    grounded, suggestions, rejected = vx.validate_vision_fields(payload, ocr_text="Samsung store")
    assert grounded == {"brand": "Samsung"}  # also present in the OCR text
    assert suggestions["serial_no"]["status"] == "pending" and suggestions["serial_no"]["source"] == "ai_vision"
    assert rejected == {"model_code": "value_not_in_source_line", "invoice_no": "low_confidence", "purchase_date": "from_redacted_area"}


@needs_tesseract
def test_pipeline_vision_only_when_enabled_and_values_need_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(invoice_pipeline, "lookup_terms", lambda *a, **k: None)
    monkeypatch.setattr(invoice_pipeline, "verify_or_suggest", lambda **k: {"verified": True})
    sent = []
    payload = {
        "brand": {"value": "Samsung", "source_line": "Samsung Galaxy M17e", "confidence": 0.9},
        "serial_no": {"value": "R58N12ABCDE", "source_line": "S/N R58N12ABCDE", "confidence": 0.8},
    }
    monkeypatch.setattr(vx, "_openai_vision_provider", lambda png: sent.append(png) or payload)
    path = tmp_path / "photo.png"
    _image(["Bill To: Asha Verma", "Mobile: 9876543210"], path)

    def run():
        artifact = ingest_artifact(ArtifactType.invoice, file_path=str(path), use_ocr=True)
        warranty = _placeholder_upload_warranty(artifact)
        with SessionLocal() as db:
            job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=str(path))
        invoice_pipeline.run_job(job.id)
        with SessionLocal() as db:
            return db.query(PipelineJobDB).filter_by(id=job.id).first().status, db.query(WarrantyDB).filter_by(id=warranty.id).first()

    monkeypatch.delenv("VISION_AI_EXTRACTION", raising=False)
    run()
    assert sent == []

    monkeypatch.setenv("VISION_AI_EXTRACTION", "1")
    status, row = run()
    assert status == "done" and len(sent) == 1
    assert "Asha" not in _ocr_png(sent[0]) and "9876543210" not in _ocr_png(sent[0])
    assert row.brand != "Samsung" and row.serial_no is None  # vision-only: not stored as fields
    assert row.alternatives["vision_suggestions"]["brand"]["status"] == "pending"
    assert row.alternatives["ai_vision"]["sent"] is True


def test_confirm_vision_suggestion_endpoint():
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_vision_confirm").delete()
        db.add(WarrantyDB(id="wty_vision_confirm", product_name="Product", confidence={}, alternatives={
            "vision_suggestions": {
                "serial_no": {"value": "R58N12ABCDE", "source_line": "S/N R58N12ABCDE", "status": "pending"},
                "purchase_date": {"value": "12-03-2026", "source_line": "Date 12-03-2026", "status": "pending"},
            }
        }))
        if not db.query(WarrantyOwnerDB).filter_by(user_id="admin", warranty_id="wty_vision_confirm").first():
            db.add(WarrantyOwnerDB(user_id="admin", warranty_id="wty_vision_confirm"))
        db.commit()
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.post("/warranties/wty_vision_confirm/vision-suggestion", json={"field": "serial_no", "action": "confirm"}, headers=auth).status_code == 200
    assert client.post("/warranties/wty_vision_confirm/vision-suggestion", json={"field": "purchase_date", "action": "dismiss"}, headers=auth).status_code == 200
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id="wty_vision_confirm").first()
        assert row.serial_no == "R58N12ABCDE" and row.confidence["serial_no"] == 0.95
        assert row.purchase_date is None
        assert row.alternatives["vision_suggestions"]["purchase_date"]["status"] == "dismissed"


def test_low_confidence_ocr_uses_strict_redaction(monkeypatch):
    """Garbled OCR ("Bil Tc") cannot be trusted to find the buyer label: only invoice-like lines survive."""
    def word(text, line, x):
        return {"text": text, "conf": 40.0, "line": (1, 1, line), "box": (x, 20 * line, x + 40, 20 * line + 15)}

    words = [
        word("Bil", 1, 10), word("Tc:", 1, 60), word("Asha", 1, 110), word("Verma", 1, 160),
        word("Invoice", 2, 10), word("No", 2, 60), word("INV-2026-0031", 2, 110),
        word("12,", 3, 10), word("Lake", 3, 60), word("View", 3, 110), word("Road,", 3, 160), word("400076", 3, 210),
    ]
    monkeypatch.setattr(vx, "_locate_words", lambda image: words)
    png, info = vx.redact_image(_image([]))
    assert info["mode"] == "strict"
    img = Image.open(io.BytesIO(png)).convert("L")

    def is_black(w):
        x0, y0, x1, y1 = w["box"]
        return img.getpixel(((x0 + x1) // 2, (y0 + y1) // 2)) < 50

    assert all(is_black(w) for w in words if w["line"][2] in (1, 3))  # garbled buyer line and address
    assert not any(is_black(w) for w in words if w["line"][2] == 2)  # invoice line kept
