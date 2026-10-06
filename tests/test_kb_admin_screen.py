"""Step 4 of the own-words run: admin knowledge-base screen - quick and bulk entry of structured facts."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB, VerifiedTermsDB
from app.deps import hash_password
from app.main import app
from app.services import kb_quick, terms_lookup, warranty_facts

BASE = {
    "company": "LG", "category": "refrigerator", "product_line": "fridge", "region": "IN", "duration_months": 12,
    "start_rule": "purchase", "covers_defects": True,
    "part_periods": [{"part": "compressor", "months": 120}],
    "exclusion_keys": ["power", "commercial", "pests"],
    "route_keys": ["authorized_centre", "customer_care", "on_site"],
    "source_url": "https://www.lg.com/in/support/warranty", "checked_on": "2026-10-01",
}


def _client(user="admin"):
    client = TestClient(app)
    password = "admin123" if user == "admin" else "secret123"
    token = client.post("/auth/login", data={"username": user, "password": password}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        db.query(VerifiedTermsDB).filter(VerifiedTermsDB.company.in_(["LG", "Samsung", "Voltas", "Racold"])).delete(synchronize_session=False)
        if not db.query(UserDB).filter_by(username="kb_customer").first():
            db.add(UserDB(username="kb_customer", role="user", hashed_password=hash_password("secret123")))
        db.commit()


def test_quick_entry_round_trips_into_the_same_facts():
    lists, months = kb_quick.build_lists(BASE)
    facts = warranty_facts.build(brand="LG", coverage_months=months, **lists)
    assert facts["period"]["text"] == "Covered for 1 year from the purchase date"
    assert [p["text"] for p in facts["part_periods"]] == ["Compressor covered for 10 years"]
    assert {f["key"] for f in facts["exclusions"]} == {"power", "commercial", "pests"}
    assert {f["key"] for f in facts["claim_route"]} == {"service_centre", "customer_care"} and facts["service_mode"] == "on_site"
    install = kb_quick.build_lists({**BASE, "start_rule": "installation", "registration_days": 30, "pro_rata": True})[0]
    facts = warranty_facts.build(brand="LG", coverage_months=12, **install)
    assert facts["start_rule"] == "installation" and facts["registration_days"] == 30 and facts["pro_rata"]


def test_bulk_entry_for_a_whole_category_and_models_then_lookup_uses_it():
    admin, auth = _client()
    resp = admin.post("/admin/knowledge-base/quick", json={**BASE, "models": "GL-T292RPZY\nGL-I292RPZL, GL-T292RPZY"}, headers=auth)
    assert resp.status_code == 200, resp.text
    assert resp.json()["saved"] == 3  # the line + 2 distinct models
    scopes = sorted(e["product_scope"] for e in resp.json()["entries"])
    assert scopes == ["line:fridge", "model:GLI292RPZL", "model:GLT292RPZY"]
    again = admin.post("/admin/knowledge-base/quick", json={**BASE, "duration_months": 24}, headers=auth)
    assert again.json()["saved"] == 1  # same scope updated, not duplicated
    with SessionLocal() as db:
        assert db.query(VerifiedTermsDB).filter_by(company="LG", product_scope="line:fridge").count() == 1
        entry = db.query(VerifiedTermsDB).filter_by(company="LG", product_scope="line:fridge").one()
        assert entry.duration_months == 24 and entry.verified_at.date().isoformat() == "2026-10-01"
        result = terms_lookup.lookup_terms(db, brand="LG", category="refrigerator", region="IN", model_code="GL-B201ALLB",
                                           product_name="LG Single Door Refrigerator")
        assert result.duration_months == 24 and "Compressor covered for 10 years." in result.terms


@pytest.mark.parametrize("change,detail", [
    ({"company": "Nonexistent"}, "OEM registry"),
    ({"company": "Bajaj"}, "verified official website"),      # bare shared name: no official site of its own
    ({"source_url": "https://some-blog.example.com/lg"}, "verified official website"),
    ({"product_line": "", "models": ""}, "never brand-wide"),
    ({"product_line": "spaceship"}, "product_line must be one of"),
    ({"part_periods": [{"part": "flux capacitor", "months": 12}]}, "part must be one of"),
    ({"part_periods": [{"part": "compressor", "months": 121}]}, "whole years"),
    ({"exclusion_keys": ["everything"]}, "unknown exclusion"),
    ({"route_keys": ["pigeon"]}, "unknown claim route"),
    ({"duration_months": 999}, "between 1 and 240"),
    ({"start_rule": "delivery"}, "purchase or installation"),
    ({"checked_on": (datetime.utcnow() + timedelta(days=3)).date().isoformat()}, "future"),
])
def test_bad_entries_are_refused(change, detail):
    admin, auth = _client()
    resp = admin.post("/admin/knowledge-base/quick", json={**BASE, **change}, headers=auth)
    assert resp.status_code == 422 and detail in resp.json()["detail"], resp.text


def test_screen_and_endpoints_are_admin_only():
    customer, auth = _client("kb_customer")
    assert customer.post("/admin/knowledge-base/quick", json=BASE, headers=auth).status_code in (401, 403)
    assert customer.get("/admin/knowledge-base/options", headers=auth).status_code in (401, 403)
    admin, admin_auth = _client()
    options = admin.get("/admin/knowledge-base/options", headers=admin_auth).json()
    assert "compressor" in options["parts"] and "power" in options["exclusions"] and "LG" in options["companies"]
    admin.post("/auth/login", data={"username": "admin", "password": "admin123"})
    html = admin.get("/ui/admin/knowledge-base").text
    assert "Knowledge base: add warranty facts" in html and 'id="models"' in html and 'id="checkedOn"' in html
