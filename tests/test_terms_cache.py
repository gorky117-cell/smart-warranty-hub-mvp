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
