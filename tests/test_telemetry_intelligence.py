from datetime import datetime

from app.db import SessionLocal
from app.db_models import TelemetryEventDB, WarrantyDB
from app.services.telemetry_intelligence import (
    build_oem_telemetry_aggregate,
    prepare_event_payload,
)


def test_prepare_event_payload_removes_direct_identifiers_and_classifies():
    payload = prepare_event_payload(
        "error",
        {
            "serial_no": "ABC-123",
            "imei": "123456789",
            "location": "12.9,77.5",
            "hours": 1200,
            "errors": 4,
            "temperature": 48,
            "note": "fan running hot",
        },
    )

    assert "serial_no" not in payload
    assert "imei" not in payload
    assert "location" not in payload
    assert payload["note"] == "fan running hot"
    assert payload["_telemetry_intelligence"]["signal"] == "high_risk"
    assert "high operating temperature" in payload["_telemetry_intelligence"]["reasons"]


def test_oem_telemetry_aggregate_suppresses_small_cohort_and_reports_large_cohort():
    with SessionLocal() as db:
        for i in range(3):
            wid = f"tel_w_small_{i}"
            db.merge(WarrantyDB(id=wid, product_name="Smart TV", brand="Acmeco", model_code="ZX", region_code="IN"))
            db.merge(
                TelemetryEventDB(
                    id=f"tel_small_{i}",
                    user_id=f"user_small_{i}",
                    warranty_id=wid,
                    model_code="ZX",
                    region="IN",
                    event_type="error",
                    payload=prepare_event_payload("error", {"errors": 1}),
                    timestamp=datetime.utcnow(),
                )
            )
        db.commit()

        small = build_oem_telemetry_aggregate(db, brand="Acmeco", model="ZX", min_cohort=5)
        assert small["status"] == "suppressed"
        assert small["cohort_size"] == 3

        for i in range(3, 5):
            wid = f"tel_w_big_{i}"
            db.merge(WarrantyDB(id=wid, product_name="Smart TV", brand="Acmeco", model_code="ZX", region_code="IN"))
            db.merge(
                TelemetryEventDB(
                    id=f"tel_big_{i}",
                    user_id=f"user_big_{i}",
                    warranty_id=wid,
                    model_code="ZX",
                    region="IN",
                    event_type="maintenance" if i == 4 else "error",
                    payload=prepare_event_payload(
                        "maintenance" if i == 4 else "error",
                        {"cleaned_filter": True} if i == 4 else {"errors": 1},
                    ),
                    timestamp=datetime.utcnow(),
                )
            )
        db.commit()

        large = build_oem_telemetry_aggregate(db, brand="Acmeco", model="ZX", min_cohort=5)
        assert large["status"] == "ok"
        assert large["cohort_size"] == 5
        assert large["event_count"] == 5
        assert large["signals"]["watch"] == 4
        assert large["signals"]["care_positive"] == 1
