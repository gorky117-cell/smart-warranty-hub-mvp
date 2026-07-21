from datetime import date, datetime, time, timedelta

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB, WarrantyDB
from app.deps import hash_password
from app.services.notifications import create_expiry_notifications, list_notifications, refresh_expiry_notifications


def _ensure_user(db, username: str) -> None:
    row = db.query(UserDB).filter_by(username=username).first()
    if row:
        return
    db.add(
        UserDB(
            username=username,
            role="user",
            hashed_password=hash_password("pass123"),
            email=f"{username}@example.com",
            consent_analytics=1,
        )
    )
    db.commit()


def _upsert_warranty(db, wid: str, *, expiry_days: int | None, coverage_months: int | None = 12) -> WarrantyDB:
    w = db.query(WarrantyDB).filter_by(id=wid).first()
    if not w:
        w = WarrantyDB(id=wid, brand="TestBrand", model_code="M1", product_name="Device")
        db.add(w)
    w.purchase_date = datetime.utcnow() - timedelta(days=60)
    w.coverage_months = coverage_months
    w.expiry_date = datetime.combine(date.today() + timedelta(days=expiry_days), time(hour=12)) if expiry_days is not None else None
    w.created_at = w.created_at or datetime.utcnow()
    db.commit()
    return w


def test_create_expiry_notifications_staged_types():
    with SessionLocal() as db:
        _ensure_user(db, "notif_user_a")
        _upsert_warranty(db, "w_notif_30", expiry_days=20)
        out = create_expiry_notifications(db, "notif_user_a", "w_notif_30")
        assert len(out) == 1
        assert out[0]["type"] == "expiry_30d"

        _upsert_warranty(db, "w_notif_7", expiry_days=5)
        out2 = create_expiry_notifications(db, "notif_user_a", "w_notif_7")
        assert len(out2) == 1
        assert out2[0]["type"] == "expiry_7d"

        _upsert_warranty(db, "w_notif_due", expiry_days=0)
        out3 = create_expiry_notifications(db, "notif_user_a", "w_notif_due")
        assert len(out3) == 1
        assert out3[0]["type"] == "expiry_due"


def test_create_expiry_notifications_is_idempotent():
    with SessionLocal() as db:
        _ensure_user(db, "notif_user_b")
        _upsert_warranty(db, "w_notif_repeat", expiry_days=6)
        first = create_expiry_notifications(db, "notif_user_b", "w_notif_repeat")
        second = create_expiry_notifications(db, "notif_user_b", "w_notif_repeat")
        assert len(first) == 1
        assert second == []

        count = (
            db.query(NotificationDB)
            .filter_by(user_id="notif_user_b", warranty_id="w_notif_repeat", type="expiry_7d")
            .count()
        )
        assert count == 1


def test_refresh_expiry_notifications_uses_derived_expiry():
    with SessionLocal() as db:
        _ensure_user(db, "notif_user_c")
        w = _upsert_warranty(db, "w_notif_derived", expiry_days=None, coverage_months=2)
        # Link the pair by creating one onboarding notification
        db.add(
            NotificationDB(
                id="ntf_link_notif_user_c",
                user_id="notif_user_c",
                warranty_id=w.id,
                audience="user",
                type="warranty_onboarded",
                title="Warranty onboarded",
                message="linked",
                severity="info",
                is_read=0,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()

        stats = refresh_expiry_notifications(db)
        assert int(stats.get("scanned", 0)) >= 1
        row = (
            db.query(NotificationDB)
            .filter(
                NotificationDB.user_id == "notif_user_c",
                NotificationDB.warranty_id == "w_notif_derived",
                NotificationDB.type.like("expiry_%"),
            )
            .first()
        )
        assert row is not None


def test_list_notifications_upgrades_legacy_warranty_id_text():
    with SessionLocal() as db:
        _ensure_user(db, "notif_user_legacy")
        w = _upsert_warranty(db, "w_notif_legacy", expiry_days=60)
        w.product_name = "Microwave Oven"
        w.brand = "Acmeco"
        w.model_code = "ZX-100"
        db.query(NotificationDB).filter_by(id="ntf_link_notif_user_legacy").delete()
        db.add(
            NotificationDB(
                id="ntf_link_notif_user_legacy",
                user_id="notif_user_legacy",
                warranty_id=w.id,
                audience="user",
                type="risk_high",
                title="Risk High detected",
                message="Predictive model flagged high risk for warranty w_notif_legacy.",
                severity="critical",
                is_read=0,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()

        items = list_notifications("notif_user_legacy", only_unread=True, db=db)

        assert items[0]["message"] == "Predictive model flagged high risk for Microwave Oven (w_notif_legacy)."
        assert items[0]["product_label"] == "Microwave Oven (w_notif_legacy)"
        row = db.query(NotificationDB).filter_by(id="ntf_link_notif_user_legacy").first()
        assert row.message == items[0]["message"]
