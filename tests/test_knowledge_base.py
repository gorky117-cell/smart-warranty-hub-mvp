"""Knowledge base v1: hand-checked terms first; locked entries never overwritten. Synthetic entries only."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import AuditLogDB, NotificationDB, UserDB, VerifiedTermsDB, VerifiedTermsReviewDB
from app.main import app
from app.models import CanonicalWarranty
from app.services import knowledge_base as kb
from app.services import summary_engine, terms_lookup
from app.services.warranty_parser import ParsedTerms

PHONE_URL = "https://www.samsung.com/in/support/warranty/mobile/"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")  # many logins across the suite
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: pytest.fail("knowledge base must answer first"))
    with SessionLocal() as db:
        db.query(VerifiedTermsReviewDB).delete()
        db.query(VerifiedTermsDB).delete()
        db.commit()
    yield


def _entry(db, *, scope="model:SMS928B", locked=True, months=12, region="IN", category=None, url=PHONE_URL):
    return kb.create_entry(db, {
        "company": "Samsung", "region": region, "category": category, "product_scope": scope, "source_url": url,
        "page_fingerprint": kb.page_fingerprint("Samsung mobile warranty 12 months"), "duration_months": months,
        "terms": ["12 months from purchase"], "exclusions": ["Liquid damage"], "claim_steps": ["Visit a service centre"],
        "locked": locked,
    }, admin="admin")


def test_lookup_uses_the_checked_entry_first_even_when_forced():
    with SessionLocal() as db:
        _entry(db)
        result = terms_lookup.lookup_terms(db, brand="Samsung", category="mobile", region="IN", model_code="SM-S928B",
                                           product_name="Samsung Galaxy S24 Ultra", force_refresh=True)
        assert result.source_kind == "knowledge_base" and result.duration_months == 12 and result.checked_at


def test_scope_region_and_category_matching():
    with SessionLocal() as db:
        _entry(db, scope="line:smartphone", months=12, region=None)
        _entry(db, scope="model:SMS928B", months=24, region="IN")
        find = lambda **kw: kb.find_entry(db, company="samsung", category="mobile", **kw)  # noqa: E731
        assert find(region="IN", model_code="SM-S928B", product_name="Galaxy S24 Ultra").duration_months == 24  # model first
        assert find(region="AE", model_code="SM-A155F", product_name="Samsung Galaxy A15").duration_months == 12  # line, any region
        assert find(region="IN", model_code="QA55Q60D", product_name="Samsung 55 inch QLED TV") is None  # TV: other line
        assert find(region="IN", model_code=None, product_name=None) is None  # never brand-wide


def _parsed(months, exclusions=("Liquid damage",), text="Samsung mobile warranty 12 months"):
    return lambda url: (ParsedTerms(duration_months=months, terms=["12 months from purchase"], exclusions=list(exclusions),
                                    claim_steps=["Visit a service centre"], raw_text=text, confidence=0.9), None)


def test_recheck_of_a_locked_entry_saves_a_review_and_notifies_admins():
    with SessionLocal() as db:
        entry = _entry(db)
        before = entry.duration_months
        out = kb.recheck(db, entry, admin="admin", parse=_parsed(24, text="Samsung mobile warranty 24 months"))
        assert out["outcome"] == "review_created" and "duration 12 -> 24 months" in out["differences"]
        db.refresh(entry)
        assert entry.duration_months == before  # locked: never overwritten
        review = db.query(VerifiedTermsReviewDB).filter_by(entry_id=entry.id).one()
        assert review.status == "pending" and review.duration_months == 24
        admins = db.query(UserDB).filter_by(role="admin").count()
        assert db.query(NotificationDB).filter_by(warranty_id=f"kb:{entry.id}", audience="admin").count() == admins >= 1
        assert db.query(AuditLogDB).filter(AuditLogDB.action == "kb_recheck_review").count() >= 1


def test_recheck_same_page_changes_nothing_and_unlocked_entries_update():
    with SessionLocal() as db:
        entry = _entry(db)
        assert kb.recheck(db, entry, admin="admin", parse=_parsed(12))["outcome"] == "unchanged"
        unlocked = _entry(db, scope="model:SMA155F", locked=False)
        out = kb.recheck(db, unlocked, admin="admin", parse=_parsed(24, text="Samsung mobile warranty 24 months"))
        db.refresh(unlocked)
        assert out["outcome"] == "updated" and unlocked.duration_months == 24


def test_reviews_cannot_be_accepted_into_a_locked_entry():
    with SessionLocal() as db:
        entry = _entry(db)
        kb.recheck(db, entry, admin="admin", parse=_parsed(24, text="changed page"))
        review = db.query(VerifiedTermsReviewDB).filter_by(entry_id=entry.id).one()
        with pytest.raises(PermissionError):
            kb.resolve_review(db, review, accept=True, admin="admin")
        kb.set_lock(db, entry, False, admin="admin")
        kb.resolve_review(db, review, accept=True, admin="admin")
        db.refresh(entry)
        assert entry.duration_months == 24 and review.status == "accepted"
        assert db.query(AuditLogDB).filter(AuditLogDB.action.in_(["kb_unlock", "kb_review_accepted"])).count() >= 2


def test_customers_see_checked_on_date():
    warranty = CanonicalWarranty(id="w", product_name="Galaxy", brand="Samsung", alternatives={
        "terms_source_type": "knowledge_base", "terms_source_url": PHONE_URL, "terms_last_refreshed_at": "2026-09-01T10:00:00"})
    evidence = summary_engine.build_evidence_summary(warranty)
    assert evidence["status"] == "confirmed" and evidence["status_label"] == "Checked on 2026-09-01"
    assert evidence["needs_refresh"] is False and "hand-checked" in evidence["note"]


# --- admin endpoints ------------------------------------------------------------------------------------------


def _admin():
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_admin_endpoints_create_lock_unlock_and_list():
    client, auth = _admin()
    body = {"company": "Samsung", "region": "IN", "model_code": "SM-S928B", "source_url": PHONE_URL,
            "duration_months": 12, "terms": ["12 months"], "exclusions": ["Liquid damage"], "claim_steps": ["Call"]}
    created = client.post("/admin/knowledge-base", json=body, headers=auth)
    assert created.status_code == 200 and created.json()["product_scope"] == "model:SMS928B" and created.json()["locked"] is True
    entry_id = created.json()["id"]
    assert client.post(f"/admin/knowledge-base/{entry_id}/unlock", headers=auth).json()["locked"] is False
    assert client.post(f"/admin/knowledge-base/{entry_id}/lock", headers=auth).json()["locked"] is True
    assert [e["id"] for e in client.get("/admin/knowledge-base", headers=auth).json()["entries"]] == [entry_id]
    bad = client.post("/admin/knowledge-base", json={**body, "source_url": "https://samsung-deals.example/w"}, headers=auth)
    assert bad.status_code == 422  # must be an official page of the company
    no_scope = client.post("/admin/knowledge-base", json={**body, "model_code": None}, headers=auth)
    assert no_scope.status_code == 422  # model or product line required
    with SessionLocal() as db:
        actions = {a.action for a in db.query(AuditLogDB).filter(AuditLogDB.detail.like(f"entry={entry_id} %")).all()}
    assert {"kb_create", "kb_lock", "kb_unlock"} <= actions


def test_admin_endpoints_are_admin_only():
    from app.deps import hash_password

    client = TestClient(app)
    assert client.get("/admin/knowledge-base").status_code in (401, 403)
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username="kb_plain_user").first():
            db.add(UserDB(username="kb_plain_user", role="user", hashed_password=hash_password("secret123")))
            db.commit()
    token = client.post("/auth/login", data={"username": "kb_plain_user", "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/admin/knowledge-base", headers=auth).status_code == 403
    assert client.post("/admin/knowledge-base/1/unlock", headers=auth).status_code == 403


def test_pipeline_records_knowledge_base_terms(monkeypatch):
    from app.models import ArtifactType
    from app.services import invoice_pipeline
    from app.services.canonical import canonicalize_artifact
    from app.services.ingestion import ingest_artifact
    from app.storage import store

    monkeypatch.setenv("OEM_AUTO_VERIFY", "false")
    with SessionLocal() as db:
        _entry(db, months=12, region=None)  # applies in any region
    text = "Tax Invoice\nInvoice No: INV-9\nDate: 02-03-2026\n1 Samsung Galaxy S24 Ultra SM-S928B Mobile 1 Nos 1,29,999.00"
    artifact = ingest_artifact(ArtifactType.invoice, content=text, use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)
    with SessionLocal() as db:
        job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=None)
    invoice_pipeline.run_job(job.id)
    store.warranties.pop(warranty.id, None)
    canonical = store.get_warranty_db(warranty.id)
    assert canonical.coverage_months == 12 and canonical.alternatives["terms_source_type"] == "knowledge_base"
    assert summary_engine.build_evidence_summary(canonical)["status_label"].startswith("Checked on ")
