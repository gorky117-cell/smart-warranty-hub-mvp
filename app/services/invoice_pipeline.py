from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..db_models import (
    PipelineJobDB,
    ArtifactDB,
    WarrantyDB,
    ParsedFieldDB,
    WarrantySummaryDB,
)
from ..storage import generate_id, store
from ..models import CanonicalWarranty
from .ocr import extract_text_with_meta
from .ingestion import extract_product_fields
from .terms_lookup import lookup_terms
from .summary_engine import summarize_warranty


def _set_job_status(db: Session, job: PipelineJobDB, status: str, detail: str | None = None, error: str | None = None) -> None:
    job.status = status
    job.detail = detail
    job.error = error
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()


def create_job(
    db: Session,
    *,
    warranty_id: str,
    artifact_id: Optional[str] = None,
    source_path: Optional[str] = None,
) -> PipelineJobDB:
    job = PipelineJobDB(
        id=generate_id("job"),
        warranty_id=warranty_id,
        artifact_id=artifact_id,
        source_path=source_path,
        status="uploaded",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Optional[Dict[str, Any]]:
    job = db.query(PipelineJobDB).filter_by(id=job_id).first()
    if not job:
        return None
    return {
        "job_id": job.id,
        "warranty_id": job.warranty_id,
        "artifact_id": job.artifact_id,
        "status": job.status,
        "detail": job.detail,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _parse_date(value: str | None) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _update_warranty(db: Session, warranty_id: str, fields: Dict[str, Any]) -> Optional[WarrantyDB]:
    warranty = db.query(WarrantyDB).filter_by(id=warranty_id).first()
    if not warranty:
        return None

    if fields.get("product_name"):
        warranty.product_name = fields["product_name"]
    if fields.get("brand"):
        warranty.brand = fields["brand"]
    if fields.get("model_code"):
        warranty.model_code = fields["model_code"]
    if fields.get("serial_no"):
        warranty.serial_no = fields["serial_no"]

    purchase_date = _parse_date(fields.get("purchase_date"))
    if purchase_date:
        warranty.purchase_date = datetime.combine(purchase_date, datetime.min.time())

    coverage_months = fields.get("coverage_months")
    if isinstance(coverage_months, str):
        try:
            coverage_months = int(coverage_months)
        except ValueError:
            coverage_months = None
    if isinstance(coverage_months, int):
        warranty.coverage_months = coverage_months

    db.add(warranty)
    db.commit()
    db.refresh(warranty)
    return warranty


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.query(PipelineJobDB).filter_by(id=job_id).first()
        if not job:
            return
        try:
            _set_job_status(db, job, "extracting_text")
            text = ""
            if job.artifact_id:
                artifact = db.query(ArtifactDB).filter_by(id=job.artifact_id).first()
                if artifact and artifact.content:
                    text = artifact.content
            ocr_detail = "skipped"
            if job.source_path and len(text) < 200:
                extracted, err, meta = extract_text_with_meta(job.source_path)
                if extracted and len(extracted) > len(text):
                    text = extracted
                if meta.get("ocr_used"):
                    ocr_detail = str(meta.get("method"))
            _set_job_status(db, job, "ocr_if_needed", detail=ocr_detail)
            if not text:
                _set_job_status(db, job, "failed", error="no_text")
                return

            _set_job_status(db, job, "parsed_fields")
            fields, confidence, alternatives = extract_product_fields(text)
            parsed_date = None
            if fields.get("purchase_date"):
                try:
                    parsed_date = datetime.fromisoformat(fields["purchase_date"])
                except ValueError:
                    parsed_date = None
            db.add(
                ParsedFieldDB(
                    warranty_id=job.warranty_id,
                    brand=fields.get("brand"),
                    model_code=fields.get("model_code"),
                    product_name=fields.get("product_name"),
                    product_category=fields.get("product_category"),
                    serial_no=fields.get("serial_no"),
                    invoice_no=fields.get("invoice_no"),
                    purchase_date=parsed_date,
                    confidence=confidence,
                    raw_text=text[:4000],
                    created_at=datetime.utcnow(),
                )
            )
            warranty = _update_warranty(db, job.warranty_id, fields)
            if not warranty:
                _set_job_status(db, job, "failed", error="warranty_not_found")
                return

            _set_job_status(db, job, "terms_lookup")
            terms_result = lookup_terms(
                db,
                brand=warranty.brand,
                category=fields.get("product_category"),
                region=warranty.region_code,
                model_code=warranty.model_code,
            )
            if terms_result.duration_months and not warranty.coverage_months:
                warranty.coverage_months = terms_result.duration_months
            if warranty.purchase_date and warranty.coverage_months:
                try:
                    expiry = warranty.purchase_date.date()
                    year = expiry.year + (expiry.month - 1 + warranty.coverage_months) // 12
                    month = (expiry.month - 1 + warranty.coverage_months) % 12 + 1
                    day = min(expiry.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
                    warranty.expiry_date = datetime(year, month, day)
                except Exception:
                    pass
            warranty.terms = terms_result.terms
            warranty.exclusions = terms_result.exclusions
            warranty.claim_steps = terms_result.claim_steps
            db.add(warranty)
            db.commit()
            db.refresh(warranty)

            _set_job_status(db, job, "summarized")
            canonical = store.get_warranty_db(job.warranty_id)
            if not canonical:
                canonical = CanonicalWarranty(
                    id=warranty.id,
                    product_name=warranty.product_name,
                    brand=warranty.brand,
                    model_code=warranty.model_code,
                    serial_no=warranty.serial_no,
                    purchase_date=warranty.purchase_date.date() if warranty.purchase_date else None,
                    coverage_months=warranty.coverage_months,
                    expiry_date=warranty.expiry_date.date() if warranty.expiry_date else None,
                    terms=warranty.terms or [],
                    exclusions=warranty.exclusions or [],
                    claim_steps=warranty.claim_steps or [],
                    confidence=warranty.confidence or {},
                    alternatives=warranty.alternatives or {},
                    source_artifact_ids=warranty.source_artifact_ids or [],
                )
            summary_text, source = summarize_warranty(canonical)
            db.add(
                WarrantySummaryDB(
                    warranty_id=job.warranty_id,
                    summary_text=summary_text,
                    source=source,
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()
            store.warranties.pop(job.warranty_id, None)
            _set_job_status(db, job, "done")
        except Exception as exc:
            _set_job_status(db, job, "failed", error=str(exc))


def get_latest_summary(db: Session, warranty_id: str) -> Optional[WarrantySummaryDB]:
    return (
        db.query(WarrantySummaryDB)
        .filter_by(warranty_id=warranty_id)
        .order_by(WarrantySummaryDB.created_at.desc())
        .first()
    )
