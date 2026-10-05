"""Live test 1, item 4: one product uploaded several times does not multiply alerts; summary; access."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB, WarrantyDB
from app.deps import hash_password
from app.main import app
from app.services import notifications as ns

USER = "notif_dedup_user"
BOUGHT = datetime(2026, 5, 1)


def _reset():
    with SessionLocal() as db:
        db.query(NotificationDB).filter(NotificationDB.user_id.in_([USER, "notif_other_user"])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_nd_%")).delete(synchronize_session=False)
        for name in (USER, "notif_other_user"):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123")))
        db.commit()


def _warranty(db, wid, model="M17E", bought=BOUGHT):
    db.add(WarrantyDB(id=wid, brand="Samsung", model_code=model, product_name="Galaxy M17e", purchase_date=bought, alternatives={}))
    db.commit()


def test_same_product_uploaded_twice_gets_one_alert_per_type():
    _reset()
    with SessionLocal() as db:
        for wid in ("wty_nd_1", "wty_nd_2", "wty_nd_3"):
            _warranty(db, wid)
            ns.create_notification(user_id=USER, warranty_id=wid, type="warranty_onboarded", title="t", message="m", db=db)
        _warranty(db, "wty_nd_other", model="A155F")  # a different product still gets its own
        ns.create_notification(user_id=USER, warranty_id="wty_nd_other", type="warranty_onboarded", title="t", message="m", db=db)
        _warranty(db, "wty_nd_later", bought=datetime(2026, 7, 1))  # same model bought on another day: another phone
        ns.create_notification(user_id=USER, warranty_id="wty_nd_later", type="warranty_onboarded", title="t", message="m", db=db)
        count = db.query(NotificationDB).filter_by(user_id=USER, type="warranty_onboarded").count()
    assert count == 3


def test_summary_counts_by_type_and_reports_duplicates():
    _reset()
    with SessionLocal() as db:
        _warranty(db, "wty_nd_1")
        _warranty(db, "wty_nd_2")
        for wid in ("wty_nd_1", "wty_nd_2"):  # duplicates written directly, as older code did
            db.add(NotificationDB(id=f"ntf_{wid}", user_id=USER, warranty_id=wid, type="risk_medium", title="t",
                                  message="m", severity="warning", is_read=0, created_at=datetime.utcnow(), audience="user"))
        db.commit()
        summary = ns.unread_summary(USER, db=db)
    assert summary["unread_by_type"] == {"risk_medium": 2}
    assert summary["duplicates_same_product"][0]["count"] == 2 and summary["extra_from_duplicates"] == 1


def _client(user):
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": user, "password": "secret123" if user != "admin" else "admin123"},
                        headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_users_only_see_their_own_notifications(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _reset()
    with SessionLocal() as db:
        _warranty(db, "wty_nd_1")
        ns.create_notification(user_id=USER, warranty_id="wty_nd_1", type="warranty_onboarded", title="t", message="m", db=db)
    other, auth = _client("notif_other_user")
    assert other.get(f"/notifications?user_id={USER}", headers=auth).status_code == 403  # was readable before
    assert other.get(f"/notifications/summary?user_id={USER}", headers=auth).status_code == 403
    owner, owner_auth = _client(USER)
    assert owner.get("/notifications/summary", headers=owner_auth).json()["unread_by_type"] == {"warranty_onboarded": 1}
    admin, admin_auth = _client("admin")
    assert admin.get(f"/notifications?user_id={USER}", headers=admin_auth).status_code == 200
