"""Batch 3 item 5: the same invoice (number + seller) uploaded twice by one customer is offered as "open the product
you already have" instead of a second product numbered "(2)"."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import ParsedFieldDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import invoice_pipeline, product_naming

USER, OTHER = "dup_user", "dup_other"


def _user(name):
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=name).first():
            db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123"), email=f"{name}@example.com"))
            db.commit()


def _product(wid, owner, invoice_no, seller=None, bought=datetime(2017, 4, 22), age_days=0):
    with SessionLocal() as db:
        db.query(ParsedFieldDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyOwnerDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        alts = {"seller": [seller]} if seller else {}
        db.add(WarrantyDB(id=wid, brand="Voltas", product_name="Voltas 1.5 Ton 3 Star Window AC", purchase_date=bought,
                          alternatives=alts, confidence={}, created_at=datetime.utcnow() - timedelta(days=age_days)))
        db.add(ParsedFieldDB(warranty_id=wid, invoice_no=invoice_no, created_at=datetime.utcnow()))
        db.add(WarrantyOwnerDB(user_id=owner, warranty_id=wid))
        db.commit()


def _flag(wid, invoice_no, seller=None):
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id=wid).first()
        found = invoice_pipeline.flag_duplicate_invoice(db, w, invoice_no, {"seller": [seller]} if seller else {})
        return found, (w.alternatives or {}).get("duplicate_of")


@pytest.fixture(autouse=True)
def _users(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _user(USER)
    _user(OTHER)
    with SessionLocal() as db:  # each test starts with no products for these customers
        ids = [o.warranty_id for o in db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([USER, OTHER])).all()]
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.warranty_id.in_(ids)).delete(synchronize_session=False)
        db.query(ParsedFieldDB).filter(ParsedFieldDB.warranty_id.in_(ids)).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


def test_same_invoice_and_seller_is_a_duplicate():
    _product("dup_a1", USER, "HR-SDEG-1004-0000", "Cloudtail India Private Limited", age_days=3)
    _product("dup_a2", USER, "hr-sdeg-1004-0000", "CLOUDTAIL INDIA PRIVATE LIMITED")
    found, flag = _flag("dup_a2", "hr-sdeg-1004-0000", "CLOUDTAIL INDIA PRIVATE LIMITED")
    assert found == "dup_a1" and flag == {"warranty_id": "dup_a1", "status": "pending"}


@pytest.mark.parametrize("other_invoice,other_seller,other_owner", [
    ("HR-SDEG-1004-0001", "Cloudtail India Private Limited", USER),   # different invoice
    ("HR-SDEG-1004-0000", "Appario Retail Private Ltd", USER),        # different seller
    ("HR-SDEG-1004-0000", "Cloudtail India Private Limited", OTHER),  # another customer's invoice
])
def test_not_a_duplicate(other_invoice, other_seller, other_owner):
    _product("dup_b1", other_owner, other_invoice, other_seller, age_days=3)
    _product("dup_b2", USER, "HR-SDEG-1004-0000", "Cloudtail India Private Limited")
    found, flag = _flag("dup_b2", "HR-SDEG-1004-0000", "Cloudtail India Private Limited")
    assert found is None and flag is None


def test_without_sellers_the_purchase_date_must_match_too():
    _product("dup_c1", USER, "INV-77", None, bought=datetime(2025, 1, 5), age_days=3)
    _product("dup_c2", USER, "INV-77", None, bought=datetime(2025, 3, 9))
    assert _flag("dup_c2", "INV-77")[0] is None
    _product("dup_c3", USER, "INV-77", None, bought=datetime(2025, 1, 5))
    assert _flag("dup_c3", "INV-77")[0] == "dup_c1"


def test_list_explains_instead_of_numbering():
    items = [
        product_naming.describe(warranty_id="x1", brand="Voltas", product_name="Voltas Window AC", model_code=None,
                                purchase_date="2017-04-22", alternatives={"seller": ["Cloudtail"]}),
        product_naming.describe(warranty_id="x2", brand="Voltas", product_name="Voltas Window AC", model_code=None,
                                purchase_date="2017-04-22",
                                alternatives={"seller": ["Cloudtail"], "duplicate_of": {"warranty_id": "x1", "status": "pending"}}),
    ]
    product_naming.tell_apart(items)
    assert items[1]["subtitle"] == "Same invoice as a product you already added" and "(2)" not in items[1]["subtitle"]
    assert items[1]["duplicate_of"] == "x1"


def _client():
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": USER, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_open_existing_hides_the_copy_without_deleting_it():
    _product("dup_d1", USER, "HR-1", "Cloudtail", age_days=3)
    _product("dup_d2", USER, "HR-1", "Cloudtail")
    _flag("dup_d2", "HR-1", "Cloudtail")
    client, headers = _client()
    ids = [w["id"] for w in client.get("/warranties/list", headers=headers).json()["warranties"]]
    assert "dup_d1" in ids and "dup_d2" in ids
    resp = client.post("/warranties/dup_d2/duplicate", json={"action": "open_existing"}, headers=headers)
    assert resp.status_code == 200 and resp.json()["open_warranty_id"] == "dup_d1"
    ids = [w["id"] for w in client.get("/warranties/list", headers=headers).json()["warranties"]]
    assert "dup_d1" in ids and "dup_d2" not in ids
    with SessionLocal() as db:
        assert db.query(WarrantyDB).filter_by(id="dup_d2").first() is not None  # kept, not deleted
        assert db.query(WarrantyOwnerDB).filter_by(warranty_id="dup_d2", user_id=USER).first() is not None
    # Asked once: a re-processed upload is not flagged again.
    assert _flag("dup_d2", "HR-1", "Cloudtail")[0] is None


def test_keep_both():
    _product("dup_e1", USER, "HR-2", "Cloudtail", age_days=3)
    _product("dup_e2", USER, "HR-2", "Cloudtail")
    _flag("dup_e2", "HR-2", "Cloudtail")
    client, headers = _client()
    resp = client.post("/warranties/dup_e2/duplicate", json={"action": "keep_both"}, headers=headers)
    assert resp.status_code == 200 and resp.json()["duplicate_of"]["status"] == "kept_both"
    assert client.post("/warranties/dup_e2/duplicate", json={"action": "keep_both"}, headers=headers).status_code == 404
    item = next(w for w in client.get("/warranties/list", headers=headers).json()["warranties"] if w["id"] == "dup_e2")
    assert item["duplicate_of"] is None


def test_duplicate_endpoint_needs_the_owner():
    _product("dup_f1", USER, "HR-3", "Cloudtail", age_days=3)
    _product("dup_f2", USER, "HR-3", "Cloudtail")
    _flag("dup_f2", "HR-3", "Cloudtail")
    assert TestClient(app).post("/warranties/dup_f2/duplicate", json={"action": "keep_both"}).status_code == 401
