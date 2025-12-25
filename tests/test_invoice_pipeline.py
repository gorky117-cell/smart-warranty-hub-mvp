import os
from pathlib import Path

from fastapi.testclient import TestClient
from fpdf import FPDF

from app.main import app
from app.db import SessionLocal
from app.db_models import PipelineJobDB, WarrantySummaryDB, ParsedFieldDB
from app.services import invoice_pipeline, summary_engine
from app.services.ingestion import ingest_artifact
from app.services.canonical import canonicalize_artifact
from app.models import ArtifactType, CanonicalWarranty


def _make_pdf(path: Path, text: str) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    pdf.output(str(path))


def test_upload_creates_job(tmp_path):
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    assert login.status_code == 200
    token = login.json().get("access_token")
    assert token

    sample_path = tmp_path / "invoice.txt"
    sample_path.write_text("Brand: Acmeco Model: ZX-100 Purchase date: 2025-01-01", encoding="utf-8")
    with sample_path.open("rb") as fh:
        resp = client.post(
            "/artifacts/upload",
            files={"file": ("invoice.txt", fh, "text/plain")},
            data={"type": "invoice"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("job_id")
    with SessionLocal() as db:
        job = db.query(PipelineJobDB).filter_by(id=payload["job_id"]).first()
        assert job is not None


def test_pipeline_completes_with_pdf(tmp_path):
    pdf_path = tmp_path / "invoice.pdf"
    _make_pdf(pdf_path, "Brand: Acmeco Model: ZX-100 Purchase date: 2025-01-01 Warranty 12 months")
    artifact = ingest_artifact(ArtifactType.invoice, file_path=str(pdf_path), use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)

    with SessionLocal() as db:
        job = invoice_pipeline.create_job(
            db,
            warranty_id=warranty.id,
            artifact_id=artifact.id,
            source_path=str(pdf_path),
        )
    invoice_pipeline.run_job(job.id)
    with SessionLocal() as db:
        job_row = db.query(PipelineJobDB).filter_by(id=job.id).first()
        assert job_row is not None
        assert job_row.status == "done"
        summary = db.query(WarrantySummaryDB).filter_by(warranty_id=warranty.id).first()
        assert summary is not None


def test_pipeline_with_mock_text():
    text = "Invoice No: INV-123 Brand: Acmeco Model: ZX-100 Purchase date: 2025-01-01"
    artifact = ingest_artifact(ArtifactType.invoice, content=text, use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)
    with SessionLocal() as db:
        job = invoice_pipeline.create_job(
            db,
            warranty_id=warranty.id,
            artifact_id=artifact.id,
            source_path=None,
        )
    invoice_pipeline.run_job(job.id)
    with SessionLocal() as db:
        parsed = (
            db.query(ParsedFieldDB)
            .filter_by(warranty_id=warranty.id)
            .order_by(ParsedFieldDB.created_at.desc())
            .first()
        )
        assert parsed is not None
        assert parsed.brand == "Acmeco"


def test_summary_template_when_llm_disabled():
    summary_engine._LLM_PROVIDER = "none"
    warranty = CanonicalWarranty(
        id="wty_test",
        brand="Acmeco",
        model_code="ZX-100",
        coverage_months=12,
        terms=["Coverage applies under normal usage."],
        exclusions=["Physical damage excluded."],
        claim_steps=["Keep invoice ready."],
    )
    text, source = summary_engine.summarize_warranty(warranty)
    assert source == "template"
    assert "Coverage" in text
