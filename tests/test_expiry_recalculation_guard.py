"""Recalculated expiry dates never trigger notifications or e-mails (fix run B11)."""

from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.db_models import NotificationDB, RiskSnapshotDB, WarrantyDB
from app.services import emailer, notifications
from app.services.expiry_guard import due_stage_types

USER = "expiry_guard_user"


def _seed(wid, **values):
    with SessionLocal() as db:
        db.query(NotificationDB).filter_by(warranty_id=wid).delete()
        db.query(RiskSnapshotDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, product_name="Phone", alternatives={}, confidence={"coverage_months": 0.7}, **values))
        db.add(RiskSnapshotDB(user_id=USER, warranty_id=wid, risk_label="LOW", risk_score=0.1))
        db.commit()


def _expiry_notifications(wid):
    with SessionLocal() as db:
        return [n.type for n in db.query(NotificationDB).filter_by(warranty_id=wid).all() if n.type.startswith("expiry")]


def test_recalculated_expiry_is_suppressed_for_already_due_stages(monkeypatch):
    sent = []
    for name in dir(emailer):
        if name.startswith("send_"):
            monkeypatch.setattr(emailer, name, lambda *a, **k: sent.append(name))
    wid = "wty_expiry_recalc"
    purchase = datetime.utcnow() - timedelta(days=365 - 5)
    _seed(wid, purchase_date=purchase, coverage_months=60, expiry_date=purchase + timedelta(days=5 * 365))
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        row.coverage_months = 12  # e.g. product-scoped duration replaced the old 60 months
        row.expiry_date = purchase + timedelta(days=365)  # now 5 days left
        db.commit()
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        assert set(row.alternatives["expiry_suppressed_types"]) >= {"expiry_30d", "expiry_7d"}
        assert row.alternatives["expiry_recalculated"][-1]["to"] == row.expiry_date.date().isoformat()
        assert notifications.create_expiry_notifications(db=db, user_id=USER, warranty_id=wid, warranty=row) == []
        stats = notifications.refresh_expiry_notifications(db)
    assert _expiry_notifications(wid) == []
    assert sent == []
    assert stats["created"] >= 0


def test_recalculation_into_the_past_does_not_send_expired_notice():
    wid = "wty_expiry_recalc_past"
    purchase = datetime.utcnow() - timedelta(days=400)
    _seed(wid, purchase_date=purchase, coverage_months=24)  # derived expiry ~ +330 days
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        row.coverage_months = 12  # derived expiry now ~35 days ago
        db.commit()
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        assert "expiry_expired" in row.alternatives["expiry_suppressed_types"]
        assert notifications.create_expiry_notifications(db=db, user_id=USER, warranty_id=wid, warranty=row) == []


def test_first_expiry_is_not_a_recalculation_and_still_notifies():
    wid = "wty_expiry_first"
    _seed(wid)
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        row.expiry_date = datetime.utcnow() + timedelta(days=5)
        db.commit()
        row = db.query(WarrantyDB).filter_by(id=wid).first()
        assert "expiry_suppressed_types" not in (row.alternatives or {})
        created = notifications.create_expiry_notifications(db=db, user_id=USER, warranty_id=wid, warranty=row)
    assert [n["type"] for n in created] == ["expiry_7d"]


def test_later_stages_reached_by_time_are_not_suppressed():
    expiry = date(2027, 1, 31)
    at_recalc = due_stage_types(expiry, today=date(2027, 1, 6))  # 25 days left
    assert at_recalc == ["expiry_30d"]
    assert "expiry_7d" not in at_recalc and "expiry_due" not in at_recalc
