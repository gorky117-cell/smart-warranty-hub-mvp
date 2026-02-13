from datetime import datetime, timedelta

from app.db import SessionLocal
from app.db_models import NotificationDB, OemIssueSignalDB, UserDB
from app.deps import hash_password
from app.services import oem_communication


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


def test_oem_important_update_sends_with_issue_signal():
    with SessionLocal() as db:
        _ensure_user(db, "oem_sender_1", role="oem")
        _ensure_user(db, "user_rcv_1", role="user")
        db.add(
            OemIssueSignalDB(
                brand="Samsung",
                model_code="QLED-55",
                product_type="tv",
                region="IN",
                issue_type="panel_issue",
                severity=0.8,
                count=3,
                source_url="https://www.samsung.com/in/support/",
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
        )
        db.commit()

        res = oem_communication.send_oem_message(
            db,
            sender_user_id="oem_sender_1",
            sender_role="oem",
            recipient_user_id="user_rcv_1",
            kind="important_update",
            title="Important product update",
            message="Please run a preventive check for your device.",
            brand="Samsung",
            model_code="QLED-55",
            region="IN",
        )

        assert res["ok"] is True
        assert res["decision"] == "sent"
        notif = (
            db.query(NotificationDB)
            .filter_by(user_id="user_rcv_1", type="oem_important_update")
            .order_by(NotificationDB.created_at.desc())
            .first()
        )
        assert notif is not None


def test_oem_product_recommendation_blocked_without_match():
    with SessionLocal() as db:
        _ensure_user(db, "oem_sender_2", role="oem")
        _ensure_user(db, "user_rcv_2", role="user")

        res = oem_communication.send_oem_message(
            db,
            sender_user_id="oem_sender_2",
            sender_role="oem",
            recipient_user_id="user_rcv_2",
            kind="product_recommendation",
            title="Accessory recommendation",
            message="A new accessory is available.",
            brand="UnknownBrand",
            model_code="X1",
            region="IN",
        )

        assert res["ok"] is False
        assert res["decision"] == "blocked"
        assert res["blocked_reason"] == "not_important_or_not_matched"


def test_oem_contact_rate_limited_to_one_in_six_months():
    with SessionLocal() as db:
        _ensure_user(db, "oem_sender_3", role="oem")
        _ensure_user(db, "user_rcv_3", role="user")
        db.add(
            OemIssueSignalDB(
                brand="LG",
                model_code="AC-9K",
                product_type="ac",
                region="IN",
                issue_type="compressor_alert",
                severity=0.9,
                count=2,
                source_url="https://www.lg.com/in/support",
                created_at=datetime.utcnow() - timedelta(days=1),
                last_seen_at=datetime.utcnow() - timedelta(days=1),
            )
        )
        db.commit()

        first = oem_communication.send_oem_message(
            db,
            sender_user_id="oem_sender_3",
            sender_role="oem",
            recipient_user_id="user_rcv_3",
            kind="important_update",
            title="Important safety update",
            message="Please schedule a preventive check.",
            brand="LG",
            model_code="AC-9K",
            region="IN",
        )
        assert first["decision"] == "sent"

        second = oem_communication.send_oem_message(
            db,
            sender_user_id="oem_sender_3",
            sender_role="oem",
            recipient_user_id="user_rcv_3",
            kind="important_update",
            title="Another update",
            message="Follow-up update.",
            brand="LG",
            model_code="AC-9K",
            region="IN",
        )
        assert second["decision"] == "blocked"
        assert second["blocked_reason"] == "rate_limited_6_months"
