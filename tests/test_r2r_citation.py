"""Right to Repair portal: a secondary citation on admin-entered knowledge-base facts only (no lookups)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import VerifiedTermsDB
from app.main import app
from app.services import knowledge_base, terms_lookup
from app.services.summary_engine import build_evidence_summary

PORTAL = "https://righttorepairindia.gov.in/product-details/4"
BASE = {"company": "Samsung", "category": "refrigerator", "product_line": "fridge", "region": "IN",
        "duration_months": 12, "part_periods": [{"part": "compressor", "months": 120}], "exclusion_keys": ["power"],
        "route_keys": ["authorized_centre"], "source_url": "https://www.samsung.com/in/support/warranty/",
        "checked_on": "2026-10-01"}
LABEL = "Also listed on the Government of India's Right to Repair portal"


def _admin():
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        db.query(VerifiedTermsDB).filter_by(company="Samsung").delete()
        db.commit()


@pytest.mark.parametrize("url,ok", [
    (PORTAL, True), ("https://righttorepairindia.gov.in/product/3", True),
    ("http://righttorepairindia.gov.in/product-details/4", False),
    ("https://righttorepairindia.gov.in.evil.example/product-details/4", False),
    ("https://righttorepairindia.gov.in/faq", False), ("", False),
])
def test_only_portal_product_pages_are_accepted(url, ok):
    assert knowledge_base.valid_portal_url(url) is ok


def test_citation_travels_from_the_entry_to_the_customer_evidence(monkeypatch):
    calls = []
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("no fetch")))
    admin, auth = _admin()
    resp = admin.post("/admin/knowledge-base/quick", json={**BASE, "portal_url": PORTAL}, headers=auth)
    assert resp.status_code == 200 and resp.json()["entries"][0]["portal_url"] == PORTAL
    assert calls == []  # the portal is never fetched
    with SessionLocal() as db:
        result = terms_lookup.lookup_terms(db, brand="Samsung", category="refrigerator", region="IN",
                                           model_code="RT37A4513BX", product_name="Samsung Double Door Refrigerator")
    assert result.source_url == BASE["source_url"] and result.also_listed_url == PORTAL  # brand page stays the source
    w = SimpleNamespace(id="w", brand="Samsung", product_name="Samsung Refrigerator", model_code="RT37A4513BX",
                        alternatives={"terms_source_type": "knowledge_base", "terms_source_url": BASE["source_url"],
                                      "terms_also_listed_url": PORTAL, "terms_last_refreshed_at": "2026-10-01T00:00:00"})
    evidence = build_evidence_summary(w)
    assert evidence["also_listed"] == {"label": LABEL, "url": PORTAL}


def test_no_citation_without_a_hand_checked_entry():
    w = SimpleNamespace(id="w", brand="Samsung", product_name="Galaxy", model_code="SM-M175F",
                        alternatives={"terms_source_type": "default_rules", "terms_also_listed_url": PORTAL})
    assert build_evidence_summary(w)["also_listed"] is None


def test_bad_portal_link_is_refused_and_portal_cannot_be_the_main_source():
    admin, auth = _admin()
    bad = admin.post("/admin/knowledge-base/quick", json={**BASE, "portal_url": "https://example.com/x"}, headers=auth)
    assert bad.status_code == 422 and "righttorepairindia.gov.in" in bad.json()["detail"]
    as_source = admin.post("/admin/knowledge-base/quick", json={**BASE, "source_url": PORTAL}, headers=auth)
    assert as_source.status_code == 422  # the brand's own page must be the source


def test_screens_show_the_label():
    admin, _ = _admin()
    admin.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert 'id="portalUrl"' in admin.get("/ui/admin/knowledge-base").text
    html = admin.get("/ui/neo-dashboard").text
    assert "evidence.also_listed" in html and "righttorepairindia" in html
