"""Owner review of PR #3, item 3: a brand/OEM account sees counts only for its own brand; admin sees all."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import BehaviourProfile, OemAccountBrandDB, UserDB, WarrantyDB
from app.deps import hash_password
from app.main import app

BRAND_A, BRAND_B = "AcmeCool", "BetaFreeze"

# Every OEM endpoint that returns counts and takes a brand.
COUNT_ENDPOINTS = [
    "/oem/risk-stats", "/oem/telemetry-stats", "/oem/aggregate-insights", "/oem/forecast",
    "/oem/issues/summary", "/oem/questions/answer-stats", "/oem/recommendations/stats",
]


def _user(name, role, brands=None):
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=name).first():
            db.add(UserDB(username=name, role=role, hashed_password=hash_password("secret123"), email=f"{name}@example.com"))
        db.query(OemAccountBrandDB).filter_by(username=name).delete()
        for brand in brands or []:
            db.add(OemAccountBrandDB(username=name, brand=brand))
        db.commit()


def _client(name, password="secret123"):
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": name, "password": password}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _accounts(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _user("brand_a_staff", "oem", [BRAND_A])
    _user("brand_two", "oem", [BRAND_A, BRAND_B])
    _user("brand_unlinked", "oem", [])
    _user("tpa_a", "tpa", [BRAND_A])
    with SessionLocal() as db:
        for wid, brand in (("ba_w1", BRAND_A), ("ba_w2", BRAND_B)):
            db.query(WarrantyDB).filter_by(id=wid).delete()
            db.add(WarrantyDB(id=wid, brand=brand, product_name="Split AC", model_code="M1", created_at=datetime.utcnow()))
        db.commit()


@pytest.mark.parametrize("path", COUNT_ENDPOINTS)
def test_brand_a_asking_for_brand_b_is_refused(path):
    client, headers = _client("brand_a_staff")
    resp = client.get(path, params={"brand": BRAND_B}, headers=headers)
    assert resp.status_code == 403 and "own brand" in resp.json()["detail"]


@pytest.mark.parametrize("path", COUNT_ENDPOINTS)
def test_brand_a_asking_for_its_own_brand_any_case(path):
    client, headers = _client("brand_a_staff")
    for brand in (BRAND_A, BRAND_A.lower()):
        assert client.get(path, params={"brand": brand}, headers=headers).status_code == 200


@pytest.mark.parametrize("path", COUNT_ENDPOINTS)
def test_no_brand_means_its_own_brand(path, monkeypatch):
    from app.main import brand_access

    seen = []
    real = brand_access.scoped_brand
    monkeypatch.setattr(brand_access, "scoped_brand", lambda db, cur, req: seen.append(real(db, cur, req)) or seen[-1])
    client, headers = _client("brand_a_staff")
    assert client.get(path, headers=headers).status_code == 200
    assert seen == [BRAND_A]


@pytest.mark.parametrize("path", COUNT_ENDPOINTS)
def test_unlinked_account_and_tpa(path):
    client, headers = _client("brand_unlinked")
    resp = client.get(path, params={"brand": BRAND_A}, headers=headers)
    assert resp.status_code == 403 and "not linked" in resp.json()["detail"]
    tpa, tpa_headers = _client("tpa_a")
    assert tpa.get(path, params={"brand": BRAND_B}, headers=tpa_headers).status_code == 403


def test_account_with_two_brands_must_choose():
    client, headers = _client("brand_two")
    assert client.get("/oem/risk-stats", headers=headers).status_code == 422
    assert client.get("/oem/risk-stats", params={"brand": BRAND_B}, headers=headers).status_code == 200


@pytest.mark.parametrize("path", COUNT_ENDPOINTS)
def test_admin_sees_any_brand_and_all(path):
    client, headers = _client("admin", "admin123")
    assert client.get(path, params={"brand": BRAND_B}, headers=headers).status_code == 200
    assert client.get(path, headers=headers).status_code == 200


def test_lists_without_a_brand_filter_only_show_the_own_brand():
    client, headers = _client("brand_a_staff")
    brands = {item["brand"] for item in client.get("/oem/products", headers=headers).json()["items"]}
    assert BRAND_A in brands and BRAND_B not in brands
    with SessionLocal() as db:
        db.query(BehaviourProfile).filter(BehaviourProfile.warranty_id.in_(["ba_w1", "ba_w2"])).delete(synchronize_session=False)
        for wid in ("ba_w1", "ba_w2"):
            db.add(BehaviourProfile(user_id=f"u_{wid}", warranty_id=wid, behaviour_score=0.5, care_score=0.5,
                                    responsiveness_score=0.5))
        db.commit()
    rows = client.get("/oem/behaviour-stats", headers=headers).json()["items"]
    assert {r["brand"] for r in rows} == {BRAND_A}
    admin_rows = _client("admin", "admin123")
    rows = admin_rows[0].get("/oem/behaviour-stats", headers=admin_rows[1]).json()["items"]
    assert {BRAND_A, BRAND_B} <= {r["brand"] for r in rows}
    admin, admin_headers = _client("admin", "admin123")
    admin_brands = {item["brand"] for item in admin.get("/oem/products", headers=admin_headers).json()["items"]}
    assert {BRAND_A, BRAND_B} <= admin_brands


def test_customers_still_cannot_use_oem_endpoints():
    _user("plain_customer", "user")
    client, headers = _client("plain_customer")
    assert client.get("/oem/risk-stats", params={"brand": BRAND_A}, headers=headers).status_code == 403


def test_only_admin_links_accounts_to_brands():
    admin, headers = _client("admin", "admin123")
    resp = admin.put("/admin/oem-accounts/brand_unlinked/brands", json={"brands": [" BetaFreeze ", "BetaFreeze"]}, headers=headers)
    assert resp.status_code == 200 and resp.json()["brands"] == [BRAND_B]
    assert admin.get("/admin/oem-accounts/brand_unlinked/brands", headers=headers).json()["brands"] == [BRAND_B]
    assert admin.put("/admin/oem-accounts/plain_customer/brands", json={"brands": ["X"]}, headers=headers).status_code == 404
    staff, staff_headers = _client("brand_a_staff")
    assert staff.put("/admin/oem-accounts/brand_a_staff/brands", json={"brands": [BRAND_B]}, headers=staff_headers).status_code == 403
