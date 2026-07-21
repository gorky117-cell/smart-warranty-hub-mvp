from datetime import datetime, timedelta

from app.db import SessionLocal
from app.db_models import BehaviourProfile, RiskSnapshotDB, SymptomSearch, WarrantyDB
from app.services.oem_aggregate import build_privacy_safe_oem_aggregate


def _seed_oem_record(db, idx: int, *, brand: str = "Phase6Brand", model: str = "P6", region: str = "IN") -> None:
    wid = f"phase6_w_{idx}"
    user = f"phase6_user_{idx}"
    db.merge(
        WarrantyDB(
            id=wid,
            product_name="Smart Washer",
            brand=brand,
            model_code=model,
            region_code=region,
            coverage_months=12,
            expiry_date=datetime.utcnow() + timedelta(days=20 if idx % 2 == 0 else 120),
            created_at=datetime.utcnow() - timedelta(days=idx),
        )
    )
    db.add(
        BehaviourProfile(
            user_id=user,
            warranty_id=wid,
            product_type="washer",
            behaviour_score=0.5 + (idx % 3) * 0.1,
            care_score=0.6,
            responsiveness_score=0.7,
            last_updated_at=datetime.utcnow(),
        )
    )
    db.add(
        RiskSnapshotDB(
            user_id=user,
            warranty_id=wid,
            risk_label="HIGH" if idx % 2 == 0 else "LOW",
            risk_score=0.8 if idx % 2 == 0 else 0.2,
            created_at=datetime.utcnow() - timedelta(hours=idx),
        )
    )
    db.add(
        SymptomSearch(
            user_id=user,
            warranty_id=wid,
            product_type="washer",
            brand=brand,
            model=model,
            query_text="noise during spin",
            matched_component="drum noise",
            region=region,
            created_at=datetime.utcnow(),
        )
    )


def test_oem_aggregate_suppresses_small_cohort():
    with SessionLocal() as db:
        for idx in range(2):
            _seed_oem_record(db, idx, brand="Phase6Small")
        db.commit()

        out = build_privacy_safe_oem_aggregate(db, brand="Phase6Small", min_cohort=3)

    assert out["status"] == "suppressed"
    assert out["cohort_size"] == 2
    assert out["min_cohort"] == 3


def test_oem_aggregate_reports_privacy_safe_metrics():
    with SessionLocal() as db:
        for idx in range(4):
            _seed_oem_record(db, idx, brand="Phase6Large")
        db.commit()

        out = build_privacy_safe_oem_aggregate(db, brand="Phase6Large", product_type="washer", min_cohort=4)

    assert out["status"] == "ok"
    assert out["registered_product_count"] == 4
    assert out["risk_distribution"]["HIGH"] == 2
    assert out["risk_distribution"]["LOW"] == 2
    assert out["expiry_cohorts"]["0_30_days"] == 2
    assert out["top_care_issues"][0]["issue"] == "drum noise"
    assert out["service_demand"][0]["count"] >= 4
    assert out["privacy_note"].startswith("Aggregate cohort metrics")
    assert out["recommendation_opportunities"]
