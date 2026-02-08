import os
import sys
import json
import tempfile
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    tmp_dir = Path(tempfile.mkdtemp(prefix="swh_demo_db_"))
    demo_db = tmp_dir / "app_demo.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{demo_db.as_posix()}"

    from app.deps import init_db
    from app.models import ArtifactType
    from app.services.ingestion import ingest_artifact
    from app.services.canonical import canonicalize_artifact
    from app.services import invoice_pipeline
    from app.db import SessionLocal
    from app.db_models import ParsedFieldDB, WarrantyDB, WarrantySummaryDB, WarrantyTermsCacheDB

    init_db()

    invoice_path = repo_root / "test_data" / "mock_invoice.txt"
    invoice_text = invoice_path.read_text(encoding="utf-8")

    artifact = ingest_artifact(ArtifactType.invoice, content=invoice_text, use_ocr=False)
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
        wdb = db.query(WarrantyDB).filter_by(id=warranty.id).first()
        summary = (
            db.query(WarrantySummaryDB)
            .filter_by(warranty_id=warranty.id)
            .order_by(WarrantySummaryDB.created_at.desc())
            .first()
        )
        terms_cache = (
            db.query(WarrantyTermsCacheDB)
            .filter_by(brand=(parsed.brand if parsed else None))
            .order_by(WarrantyTermsCacheDB.fetched_at.desc())
            .first()
        )

    print("=== Demo Flow Result ===")
    print(f"Warranty ID: {warranty.id}")
    if parsed:
        print(f"Parsed brand: {parsed.brand}")
        print(f"Parsed model: {parsed.model_code}")
        print(f"Parsed purchase_date: {parsed.purchase_date}")
    if wdb:
        print(f"Coverage months: {wdb.coverage_months}")
        print(f"Expiry date: {wdb.expiry_date}")
        print(f"Terms: {wdb.terms}")
        print(f"Exclusions: {wdb.exclusions}")
        print(f"Claim steps: {wdb.claim_steps}")
    if summary:
        print("--- Summary ---")
        print(summary.summary_text)

    output = {
        "warranty_id": warranty.id,
        "parsed": {
            "brand": parsed.brand if parsed else None,
            "model_code": parsed.model_code if parsed else None,
            "product_name": parsed.product_name if parsed else None,
            "purchase_date": parsed.purchase_date.isoformat() if parsed and parsed.purchase_date else None,
        },
        "warranty": {
            "coverage_months": wdb.coverage_months if wdb else None,
            "expiry_date": wdb.expiry_date.isoformat() if wdb and wdb.expiry_date else None,
            "terms": wdb.terms if wdb else None,
            "exclusions": wdb.exclusions if wdb else None,
            "claim_steps": wdb.claim_steps if wdb else None,
        },
        "source_url": terms_cache.source_url if terms_cache else None,
        "summary": summary.summary_text if summary else None,
    }
    out_path = repo_root / "data" / "demo_output.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Saved demo output: {out_path}")


if __name__ == "__main__":
    main()
