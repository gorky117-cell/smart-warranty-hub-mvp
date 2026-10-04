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
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: [])  # no live search in these tests
    with SessionLocal() as db:
        db.query(WarrantyTermsCacheDB).filter(WarrantyTermsCacheDB.brand.in_(["Samsung", "LG"])).delete(synchronize_session=False)
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
