"""Terms cache fixes (cache fixes 1-6). Synthetic rows only."""

from datetime import datetime, timedelta

import pytest

from app.db import SessionLocal
from app.db_models import WarrantyTermsCacheDB
from app.services import terms_cache, terms_lookup

TV_URL = "https://www.samsung.com/in/support/warranty/tv/"
PHONE_URL = "https://www.samsung.com/in/support/warranty/mobile/"


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")  # admin logins across the suite
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: [])  # no live search in these tests
    from app.db_models import WarrantyDB

    with SessionLocal() as db:
        db.query(WarrantyTermsCacheDB).filter(WarrantyTermsCacheDB.brand.in_(["Samsung", "LG"])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_reuse_%")).delete(synchronize_session=False)
        db.commit()
    yield


def _row(db, *, url, line, model=None, months=12, age_days=1, brand="Samsung", category="electronics", region="IN", **extra):
    row = WarrantyTermsCacheDB(
        brand=brand, category=category, region=region, model_code=model, product_line=line, source_url=url,
        fetched_at=datetime.utcnow() - timedelta(days=age_days), duration_months=months,
        terms=[f"{months} months"], exclusions=["Physical damage"], claim_steps=["Call support"], **extra,
    )
    db.add(row)
    db.commit()
    return row


def _lookup(db, product, model=None, category="electronics", force=False):
    return terms_lookup.lookup_terms(
        db, brand="Samsung", category=category, region="IN", model_code=model, product_name=product, force_refresh=force
    )


def test_scope_comes_from_the_product():
    assert terms_cache.product_scope("QA55Q60D", "Samsung 55 inch QLED TV") == ("QA55Q60D", "tv")
    assert terms_cache.product_scope("SM-S928B", "Samsung Galaxy S24 Ultra") == ("SMS928B", "smartphone")
    assert terms_cache.product_scope(None, None) == (None, None)


def test_samsung_tv_terms_never_answer_a_samsung_phone():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, source_type="official")
        phone = _lookup(db, "Samsung Galaxy S24 Ultra", model="SM-S928B")
        assert phone.source_url != TV_URL and phone.duration_months != 24
        tv = _lookup(db, "Samsung 65 inch Crystal UHD TV", model="UA65DU7700")
        assert tv.source_url == TV_URL and tv.duration_months == 24  # same line, different model: allowed


def test_same_model_entry_is_preferred_within_a_line():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, age_days=5, source_type="official")
        _row(db, url=TV_URL + "other", line="tv", model="UA65DU7700", months=12, age_days=1, source_type="official")
        assert _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D").duration_months == 24


# --- cache fix 2: other users' saved warranties -------------------------------------------------------------

from app.db_models import WarrantyDB  # noqa: E402
from app.models import CanonicalWarranty  # noqa: E402
from app.services import summary_engine  # noqa: E402


def _saved(db, wid, *, model, product, source_type, url, months=24):
    db.query(WarrantyDB).filter_by(id=wid).delete()
    db.add(WarrantyDB(
        id=wid, brand="Samsung", model_code=model, product_name=product, region_code="IN", coverage_months=months,
        terms=[f"{months} months"], exclusions=["Liquid damage"], claim_steps=["Call support"],
        alternatives={"terms_source_type": source_type, "terms_source_url": url},
    ))
    db.commit()


def test_estimate_from_another_users_record_is_never_reused():
    with SessionLocal() as db:
        _saved(db, "wty_reuse_default", model="SM-A155F", product="Samsung Galaxy A15", source_type="default_rules",
               url="internal://default_rules", months=36)
        result = _lookup(db, "Samsung Galaxy A15", model="SM-A155F", category="mobile")
        assert result.duration_months != 36 and result.source_url != "internal://warranty_db"


def test_official_record_is_reused_with_its_real_source_and_label():
    with SessionLocal() as db:
        _saved(db, "wty_reuse_official", model="SM-A156B", product="Samsung Galaxy A15 5G", source_type="approved_oem_source", url=PHONE_URL)
        result = _lookup(db, "Samsung Galaxy A15 5G", model="SM-A156B", category="mobile")
        assert result.duration_months == 24 and result.source_url == PHONE_URL
        assert terms_lookup.classify_terms_source_url(result.source_url, "Samsung") == "approved_oem_source"


def test_official_record_of_another_product_line_or_brand_only_is_not_reused():
    with SessionLocal() as db:
        _saved(db, "wty_reuse_tv", model="QA55Q60D", product="Samsung 55 inch QLED TV", source_type="approved_oem_source", url=TV_URL, months=24)
        # same model code typed on a phone invoice (OCR mix-up): different product line -> not reused
        assert _lookup(db, "Samsung Galaxy phone", model="QA55Q60D").source_url != TV_URL
        # brand alone (no model or product name) never matches a saved record
        assert terms_lookup.lookup_terms(db, brand="Samsung", category="electronics", region="IN").source_url != TV_URL


def test_legacy_internal_reuse_is_not_labelled_confirmed():
    warranty = CanonicalWarranty(id="w", product_name="TV", brand="Samsung",
                                 alternatives={"terms_source_type": "internal_warranty_db", "terms_source_url": "internal://warranty_db"})
    evidence = summary_engine.build_evidence_summary(warranty)
    assert evidence["status"] == "not_confirmed" and "not confirmed" in evidence["status_label"]


# --- cache fixes 3 and 4: newest official entry; only verified official results cached ----------------------

from app.services.warranty_discovery import DiscoverySource  # noqa: E402
from app.services.warranty_parser import ParsedTerms  # noqa: E402


def test_a_default_row_never_hides_a_good_entry():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, age_days=10, source_type="official")
        _row(db, url=None, line="tv", model="QA55Q60D", months=12, age_days=0, source_type="default")
        _row(db, url="https://tv-reviews.example/samsung", line="tv", model="QA55Q60D", months=36, age_days=0, source_type="non_official")
        served = _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D")
        assert served.source_url == TV_URL and served.duration_months == 24


def test_failed_refresh_keeps_the_last_good_entry():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, age_days=3, source_type="official")
        before = db.query(WarrantyTermsCacheDB).filter_by(brand="Samsung").count()
        refreshed = _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D", force=True)  # discovery finds nothing
        assert refreshed.source_url == TV_URL and refreshed.duration_months == 24
        assert db.query(WarrantyTermsCacheDB).filter_by(brand="Samsung").count() == before  # no default row on top


def test_legacy_rows_count_as_official_only_if_the_url_verifies():
    with SessionLocal() as db:
        _row(db, url="https://samsung-deals.example/warranty", line="tv", model="QA55Q60D", months=36, source_type=None)
        assert _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D").duration_months != 36
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, source_type=None)
        assert _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D").duration_months == 24


def _scrape(monkeypatch, url):
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: [DiscoverySource(url=url, source_type="oem_warranty", score=90, official=True)])
    monkeypatch.setattr(terms_lookup, "parse_terms_from_url", lambda u, **_kw: (ParsedTerms(
        duration_months=24, terms=["Warranty of 24 months from the date of purchase."], exclusions=["Liquid damage"],
        claim_steps=["Call support"], raw_text="This TV carries a warranty of 24 months from the date of purchase.",
        confidence=0.8,
    ), None))


def test_verified_official_result_is_cached_with_its_metadata(monkeypatch):
    _scrape(monkeypatch, TV_URL)
    with SessionLocal() as db:
        result = _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D", force=True)
        assert result.checked_at and result.needs_refresh is False
        row = db.query(WarrantyTermsCacheDB).filter_by(brand="Samsung", source_url=TV_URL).one()
        assert (row.source_type, row.model_code, row.product_line, row.confidence) == ("official", "QA55Q60D", "tv", 0.8)
        assert row.grounded is not None


def test_non_official_scrape_is_not_cached(monkeypatch):
    url = "https://www.samsung-warranty-help.example/tv"
    _scrape(monkeypatch, url)
    monkeypatch.setattr(terms_lookup.oem_source_policy, "is_approved_oem_url", lambda u, b: False)
    with SessionLocal() as db:
        _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D", force=True)
        assert db.query(WarrantyTermsCacheDB).filter_by(brand="Samsung", source_url=url).count() == 0


# --- cache fix 5: 30-day expiry, "checked on <date>", older entries flagged ---------------------------------


def test_entries_older_than_30_days_are_not_served_but_kept_as_last_good():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, age_days=31, source_type="official")
        stale = _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D")
        # discovery finds nothing in the test, so the old entry comes back as last good, flagged
        assert stale.source_url == TV_URL and stale.needs_refresh is True
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", months=24, age_days=29, source_type="official")
        fresh = _lookup(db, "Samsung 55 inch QLED TV", model="QA55Q60D")
        assert fresh.needs_refresh is False and fresh.checked_at


def _evidence(checked_at, flagged=False):
    warranty = CanonicalWarranty(id="w", product_name="TV", brand="Samsung", alternatives={
        "terms_source_type": "approved_oem_source", "terms_source_url": "https://www.samsung.com/in/support/warranty/",
        "terms_last_refreshed_at": checked_at, "terms_needs_refresh": flagged,
    })
    return summary_engine.build_evidence_summary(warranty)


def test_customer_label_says_when_it_was_checked_and_flags_old_checks():
    recent = (datetime.utcnow() - timedelta(days=3)).isoformat()
    evidence = _evidence(recent)
    assert evidence["status_label"].endswith(f"checked on {recent[:10]}") and evidence["needs_refresh"] is False
    old = (datetime.utcnow() - timedelta(days=45)).isoformat()
    evidence = _evidence(old)
    assert evidence["status_label"].endswith(f"checked on {old[:10]}, needs refresh")
    assert evidence["requires_oem_verification"] is True and "may have changed since" in evidence["note"]


def test_reused_official_record_carries_its_checked_date():
    with SessionLocal() as db:
        _saved(db, "wty_reuse_dated", model="SM-A166B", product="Samsung Galaxy A16", source_type="approved_oem_source", url=PHONE_URL)
        row = db.query(WarrantyDB).filter_by(id="wty_reuse_dated").one()
        row.alternatives = {**row.alternatives, "terms_last_refreshed_at": (datetime.utcnow() - timedelta(days=40)).isoformat()}
        db.commit()
        result = _lookup(db, "Samsung Galaxy A16", model="SM-A166B", category="mobile")
        assert result.source_url == PHONE_URL and result.needs_refresh is True and result.checked_at


# --- cache fix 6: admin-only counts --------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _client_token(username, password):
    client = TestClient(app)
    resp = client.post("/auth/login", data={"username": username, "password": password}, headers={"accept": "application/json"})
    return client, resp.json().get("access_token")


def test_admin_count_endpoint():
    with SessionLocal() as db:
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", age_days=2, source_type="official")
        _row(db, url=TV_URL, line="tv", model="QA55Q60D", age_days=40, source_type="official")
        _row(db, url=None, line="tv", age_days=0, source_type="default")
        _row(db, url="https://x.example/w", line="smartphone", age_days=0, source_type="non_official")
        expected_total = db.query(WarrantyTermsCacheDB).count()
    client, token = _client_token("admin", "admin123")
    stats = client.get("/admin/terms-cache/stats", headers={"Authorization": f"Bearer {token}"}).json()
    assert stats["rows"] == expected_total
    assert stats["official_rows"] >= 2 and stats["fresh_official_rows"] >= 1 and stats["stale_official_rows"] >= 1
    assert stats["default_rows"] >= 1 and stats["non_official_rows"] >= 1 and stats["distinct_keys"] >= 2
    assert set(stats) >= {"rows", "real_source_rows", "fresh_official_rows", "distinct_keys"}


def test_count_endpoint_is_admin_only():
    from app.db_models import UserDB
    from app.deps import hash_password

    client = TestClient(app)
    assert client.get("/admin/terms-cache/stats").status_code in (401, 403)
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username="cache_stats_user").first():
            db.add(UserDB(username="cache_stats_user", role="user", hashed_password=hash_password("secret123")))
            db.commit()
    client, token = _client_token("cache_stats_user", "secret123")
    assert token
    assert client.get("/admin/terms-cache/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 403
