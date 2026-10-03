"""OCR honesty (work plan step 4): real OCR on a real image file, honest health and engine metadata.

`S001.png` is a synthetic invoice image from `test_data/ingestion_ocr_samples/`; nothing here is
mocked except network-bound steps (OEM terms lookup, domain verification).
"""

import logging
from pathlib import Path

import pytest

from app.db import SessionLocal
from app.db_models import PipelineJobDB, WarrantyDB
from app.main import _placeholder_upload_warranty
from app.models import ArtifactType
from app.services import invoice_pipeline, ocr
from app.services.ingestion import ingest_artifact

S001 = Path("test_data/ingestion_ocr_samples/S001.png")

_tesseract_ok, _tesseract_err = ocr._tesseract_ready()
needs_tesseract = pytest.mark.skipif(not _tesseract_ok, reason=f"Tesseract not installed: {_tesseract_err}")


@pytest.fixture(autouse=True)
def _reset_health_cache():
    ocr._health_cache = None
    yield
    ocr._health_cache = None


@needs_tesseract
def test_real_image_ocr_pipeline_extracts_fields(monkeypatch):
    monkeypatch.setattr(invoice_pipeline, "lookup_terms", lambda *a, **k: None)
    monkeypatch.setattr(invoice_pipeline, "verify_or_suggest", lambda **k: {"verified": True})

    artifact = ingest_artifact(ArtifactType.invoice, file_path=str(S001), use_ocr=True)
    assert artifact.ocr_meta["engine"] in {"paddle", "tesseract"}
    assert artifact.ocr_meta["method"] in {"paddle", "tesseract", "tesseract_fallback"}

    warranty = _placeholder_upload_warranty(artifact)
    with SessionLocal() as db:
        job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=str(S001))
    invoice_pipeline.run_job(job.id)

    with SessionLocal() as db:
        assert db.query(PipelineJobDB).filter_by(id=job.id).first().status == "done"
        row = db.query(WarrantyDB).filter_by(id=warranty.id).first()
        # Ground truth (ingestion_ocr_50_labeled.csv): Apple, 2025-01-06, SN001X1001, 36 months, mobile.
        assert row.brand == "Apple"
        assert row.purchase_date.date().isoformat() == "2025-01-06"
        assert row.serial_no != "TAKINVOICE"
        assert row.serial_no in (None, "SN001X1001", "SNO01X1001")  # OCR reads 0 as O today
        assert row.alternatives["ocr"]["engine"] == artifact.ocr_meta["engine"]


@needs_tesseract
def test_extract_text_with_meta_reports_engine_that_ran():
    text, err, meta = ocr.extract_text_with_meta(str(S001))
    assert text and err is None
    assert meta["ocr_used"] is True
    assert meta["engine"] in {"paddle", "tesseract"}
    if meta["method"] == "tesseract_fallback":
        assert meta["engine"] == "tesseract"
        assert meta["paddle_error"]


def test_paddle_failure_is_logged_and_recorded(monkeypatch, tmp_path, caplog):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"not used")
    monkeypatch.setattr(ocr, "run_paddle_ocr", lambda _p: (None, "PaddleOCR failed: In user code:\n  frame\nNotFoundError: boom happened\n[operator < x > error]"))
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("receipt text", None))

    with caplog.at_level(logging.WARNING, logger="app.services.ocr"):
        text, err, meta = ocr._run_image_ocr_with_meta(image_path, "paddle")

    assert text == "receipt text"
    assert meta == {
        "method": "tesseract_fallback",
        "engine": "tesseract",
        "paddle_error": "PaddleOCR failed: NotFoundError: boom happened [operator < x > error]",
    }
    assert "boom happened" in caplog.text


def test_health_reports_configured_engine_failure(monkeypatch):
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "paddle")
    monkeypatch.setattr(ocr, "find_spec", lambda _name: object())
    monkeypatch.setattr(ocr, "run_paddle_ocr", lambda _p: (None, "PaddleOCR failed: NotFoundError: model mismatch"))
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("OCR 2468", None))

    report = ocr.health_report(force=True)

    assert report["ok"] is False
    assert report["active_engine"] == "tesseract"
    assert report["engines"]["paddle"] == {"ok": False, "error": "PaddleOCR failed: NotFoundError: model mismatch"}
    assert "Tesseract fallback read the test image" in report["detail"]
    assert ocr.health() == (False, report["detail"])


def test_health_ok_only_when_engine_reads_test_image(monkeypatch):
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "tesseract")
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("something else", None))
    assert ocr.health_report(force=True)["ok"] is False

    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("OCR 2468", None))
    report = ocr.health_report(force=True)
    assert report["ok"] is True
    assert report["active_engine"] == "tesseract"


def test_health_image_is_bundled():
    assert ocr._HEALTH_IMAGE.exists()
