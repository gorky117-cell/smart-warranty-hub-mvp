from __future__ import annotations

from datetime import datetime, date
import os
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
from .ingestion import extract_product_fields, sanitize_invoice_identity_fields
from .terms_lookup import classify_terms_source_url, lookup_terms
from .warranty_parser import sanitize_base_terms
from .oem_domain_verify import verify_or_suggest
from .notifications import create_oem_notification
from .review_crawler import crawl_reviews_for_product
from .summary_engine import summarize_warranty, build_structured_summary
from .openai_intelligence import enrich_invoice_fields, merge_invoice_enrichment


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


def _lookup_identity_text(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if text.lower() in {"", "product", "n/a", "none", "null", "unknown"}:
        return ""
    return text


def _has_terms_lookup_identity(warranty: WarrantyDB, fields: Dict[str, Any]) -> bool:
    brand = _lookup_identity_text(warranty.brand or fields.get("brand"))
    model = _lookup_identity_text(warranty.model_code or fields.get("model_code"))
    product = _lookup_identity_text(warranty.product_name or fields.get("product_name"))
    return bool(brand and (model or product))


def _safe_summary(canonical: CanonicalWarranty) -> tuple[str, str, Dict[str, Any]]:
    try:
        summary_text, source = summarize_warranty(canonical)
    except Exception:
        summary_text = (
            f"{canonical.product_name or 'Product'} warranty record saved. "
            "Warranty terms could not be summarized by the configured intelligence provider."
        )
        source = "template_fallback"
    try:
        structured = build_structured_summary(canonical)
    except Exception:
        structured = {"points": [], "tags": ["summary_fallback"]}
    return summary_text, source, structured


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
    if fields.get("region_code"):
        warranty.region_code = fields["region_code"]

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
            try:
                enrichment = enrich_invoice_fields(text, fields, confidence)
                fields, confidence, openai_meta = merge_invoice_enrichment(fields, confidence, enrichment)
            except Exception as exc:
                openai_meta = {
                    "provider": "openai_invoice_enrichment",
                    "error": "upstream_error",
                    "error_type": exc.__class__.__name__,
                }
            fields, confidence, alternatives = sanitize_invoice_identity_fields(fields, confidence, alternatives)
            if openai_meta:
                alternatives = dict(alternatives or {})
                alternatives["openai_invoice_enrichment"] = openai_meta
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
            terms_result = None
            terms_lookup_error = None
            should_lookup_terms = _has_terms_lookup_identity(warranty, fields) or not fields.get("coverage_months")
            if should_lookup_terms:
                try:
                    terms_result = lookup_terms(
                        db,
                        brand=warranty.brand,
                        category=fields.get("product_category"),
                        region=warranty.region_code,
                        model_code=warranty.model_code,
                        product_name=warranty.product_name,
                        force_refresh=True,
                    )
                except Exception as exc:
                    terms_lookup_error = exc.__class__.__name__
            # Auto-verify OEM domain on new brand (bounded attempts)
            if os.getenv("OEM_AUTO_VERIFY", "true").lower() == "true" and warranty.brand:
                try:
                    res = verify_or_suggest(
                        brand=warranty.brand,
                        domain="",
                        region=warranty.region_code,
                    )
                    if not res.get("verified"):
                        try:
                            create_oem_notification(
                                db,
                                user_id="oem-1",
                                ntype="oem_domain_unverified",
                                title=f"OEM domain unverified: {warranty.brand}",
                                message=f"Auto-verify failed. Suggestions: {res.get('suggestions')}",
                                severity="warning",
                                brand=warranty.brand,
                                region=warranty.region_code,
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
            terms_source_type = None
            if terms_result:
                terms_source_type = classify_terms_source_url(terms_result.source_url or "", warranty.brand)
            if terms_result and terms_result.duration_months and (
                terms_source_type == "approved_oem_source" or not warranty.coverage_months
            ):
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
            if terms_result:
                warranty.terms = sanitize_base_terms(terms_result.terms or [])
                warranty.exclusions = terms_result.exclusions
                warranty.claim_steps = terms_result.claim_steps
            # Persist source hints for UI transparency.
            meta = dict(warranty.alternatives or {})
            if terms_result:
                source_url = terms_result.source_url or ""
                meta["terms_source_url"] = source_url or None
                meta["terms_source_urls"] = terms_result.source_urls or ([source_url] if source_url else [])
                meta["terms_source_type"] = terms_source_type or classify_terms_source_url(source_url, warranty.brand)
                meta["terms_last_refreshed_at"] = datetime.utcnow().isoformat()
                meta.pop("terms_lookup_error", None)
            elif terms_lookup_error:
                meta["terms_lookup_error"] = terms_lookup_error
                meta["terms_last_lookup_error_at"] = datetime.utcnow().isoformat()
                meta.setdefault("terms_source_type", "invoice_only")
            else:
                meta.setdefault("terms_source_type", "invoice_only")
            warranty.alternatives = meta
            # Optional: per-upload review crawl for real-time enrichment
            if os.getenv("REVIEW_CRAWL_ON_UPLOAD", "false").lower() == "true":
                try:
                    if warranty.brand and (warranty.model_code or warranty.product_name):
                        crawl_reviews_for_product(
                            db,
                            brand=warranty.brand,
                            model_code=warranty.model_code,
                            product_name=warranty.product_name,
                            region=warranty.region_code or "IN",
                            max_pages=int(os.getenv("REVIEW_ON_UPLOAD_MAX_PAGES", "5")),
                        )
                except Exception:
                    pass
            db.add(warranty)
            db.commit()
            db.refresh(warranty)

            _set_job_status(db, job, "summarized")
            # Refresh cache to ensure summary reflects DB updates
            store.warranties.pop(job.warranty_id, None)
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
            summary_text, source, structured = _safe_summary(canonical)
            db.add(
                WarrantySummaryDB(
                    warranty_id=job.warranty_id,
                    summary_text=summary_text,
                    source=source,
                    summary_points=structured.get("points"),
                    summary_tags=structured.get("tags"),
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()
            # RAG index
            try:
                from .rag import upsert_document, rag_enabled
                if rag_enabled():
                    upsert_document(
                        db,
                        doc_type="warranty_summary",
                        doc_id=job.warranty_id,
                        content=summary_text,
                        metadata={
                            "brand": warranty.brand,
                            "model_code": warranty.model_code,
                            "region": warranty.region_code,
                        },
                    )
            except Exception:
                pass
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
