from datetime import datetime

from app.db import SessionLocal
from app.db_models import BehaviourProfile, OemCommunicationTraceDB, OemIssueSignalDB, UserDB, WarrantyDB
from app.deps import hash_password
from app.services import oem_dispatch


def _ensure_user(db, username: str, role: str = "user") -> None:
    row = db.query(UserDB).filter_by(username=username).first()
    if row:
        return
    db.add(
        UserDB(
            username=username,
            role=role,
            hashed_password=hash_password("pass123"),
            email=f"{username}@example.com",
            consent_analytics=1,
        )
    )
    db.commit()


def _ensure_warranty(db, wid: str, brand: str, model_code: str, region: str = "IN") -> None:
    w = db.query(WarrantyDB).filter_by(id=wid).first()
    if w:
        return
    db.add(
        WarrantyDB(
            id=wid,
            product_name="TV",
            brand=brand,
            model_code=model_code,
            region_code=region,
            coverage_months=12,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()


def test_weekly_dispatch_sends_important_update_when_issue_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("OEM_DISPATCH_POLICY_FILE", str(tmp_path / "oem_dispatch_policy.json"))
    oem_dispatch.set_dispatch_policy(
        {
            "enabled": True,
            "allowed_kinds": ["important_update"],
            "send_product_recommendations": False,
            "max_targets_per_run": 50,
            "min_issue_count": 1,
            "min_issue_severity": 0.4,
            "issue_lookback_days": 90,
        }
    )

    with SessionLocal() as db:
        _ensure_user(db, "weekly_user_1", "user")
        _ensure_warranty(db, "w_week_1", "Samsung", "QLED-55", "IN")
        db.add(
            BehaviourProfile(
                user_id="weekly_user_1",
                warranty_id="w_week_1",
                product_type="tv",
                behaviour_score=0.6,
                care_score=0.6,
                responsiveness_score=0.6,
                last_updated_at=datetime.utcnow(),
            )
        )
        db.add(
            OemIssueSignalDB(
                brand="Samsung",
                model_code="QLED-55",
                product_type="tv",
                region="IN",
                issue_type="panel_issue",
                severity=0.9,
                count=2,
                source_url="https://www.samsung.com/in/support",
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
        )
        db.commit()

        stats = oem_dispatch.run_weekly_dispatch(db, dry_run=False)
        assert stats["ok"] is True
        assert stats["sent"] >= 1

        sent_row = (
            db.query(OemCommunicationTraceDB)
            .filter_by(recipient_user_id="weekly_user_1", decision="sent")
            .order_by(OemCommunicationTraceDB.created_at.desc())
            .first()
        )
        assert sent_row is not None


def test_weekly_dispatch_dry_run_does_not_send(tmp_path, monkeypatch):
    monkeypatch.setenv("OEM_DISPATCH_POLICY_FILE", str(tmp_path / "oem_dispatch_policy.json"))
    oem_dispatch.set_dispatch_policy(
        {
            "enabled": True,
            "allowed_kinds": ["important_update"],
            "send_product_recommendations": False,
        }
    )

    with SessionLocal() as db:
        _ensure_user(db, "weekly_user_2", "user")
        _ensure_warranty(db, "w_week_2", "LG", "AC-9K", "IN")
        db.add(
            BehaviourProfile(
                user_id="weekly_user_2",
                warranty_id="w_week_2",
                product_type="ac",
                behaviour_score=0.7,
                care_score=0.7,
                responsiveness_score=0.7,
                last_updated_at=datetime.utcnow(),
            )
        )
        db.add(
            OemIssueSignalDB(
                brand="LG",
                model_code="AC-9K",
                product_type="ac",
                region="IN",
                issue_type="compressor",
                severity=0.8,
                count=3,
                source_url="https://www.lg.com/in/support",
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
        )
        db.commit()

        stats = oem_dispatch.run_weekly_dispatch(db, dry_run=True)
        assert stats["ok"] is True
        assert stats["sent"] == 0
