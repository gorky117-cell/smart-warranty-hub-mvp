"""Start-up schema upgrade: additions only, and a failure never stops the app (cache/knowledge base off)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app import schema_upgrade
from app.db import Base, engine as app_engine
from app.services import terms_lookup

LEGACY_CACHE_DDL = (
    "CREATE TABLE warranty_terms_cache (id INTEGER PRIMARY KEY AUTOINCREMENT, brand VARCHAR, category VARCHAR, "
    "region VARCHAR, source_url VARCHAR, fetched_at DATETIME, duration_months INTEGER, raw_text TEXT, terms JSON, "
    "exclusions JSON, claim_steps JSON)"
)


@pytest.fixture(autouse=True)
def _restore_status():
    saved = dict(schema_upgrade.STATUS)
    yield
    schema_upgrade.STATUS.clear()
    schema_upgrade.STATUS.update(saved)
    schema_upgrade.run_startup_upgrade(app_engine)  # leave the shared test database upgraded and ready


def _legacy_engine(tmp_path):
    """A database as production has it before this change: old cache table, no knowledge-base tables."""
    eng = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    skip = {"warranty_terms_cache", *schema_upgrade.NEW_TABLES}
    Base.metadata.create_all(bind=eng, tables=[t for t in Base.metadata.sorted_tables if t.name not in skip])
    with eng.begin() as conn:
        conn.execute(text(LEGACY_CACHE_DDL))
        conn.execute(text("INSERT INTO warranty_terms_cache (brand, category, region, source_url, fetched_at, duration_months) "
                          "VALUES ('Samsung', 'mobile', 'IN', 'https://www.samsung.com/in/support/warranty/', CURRENT_TIMESTAMP, 12)"))
    return eng


def test_upgrade_adds_only_what_is_missing(tmp_path):
    eng = _legacy_engine(tmp_path)
    status = schema_upgrade.run_startup_upgrade(eng)
    assert status["error"] is None and status["cache_ready"] and status["knowledge_base_ready"]
    cols = {c["name"] for c in inspect(eng).get_columns("warranty_terms_cache")}
    assert set(schema_upgrade.EXPECTED_COLUMNS["warranty_terms_cache"]) <= cols
    with eng.connect() as conn:  # existing row untouched
        assert conn.execute(text("SELECT duration_months FROM warranty_terms_cache")).scalar() == 12
    assert schema_upgrade.run_startup_upgrade(eng)["added"] == {}  # second run: nothing to do


def test_failed_upgrade_is_logged_and_lookups_fall_back(tmp_path, monkeypatch, capsys):
    eng = _legacy_engine(tmp_path)

    def boom(_engine):
        raise RuntimeError("permission denied for table warranty_terms_cache")

    monkeypatch.setattr(schema_upgrade, "ensure_columns", boom)
    monkeypatch.setattr(schema_upgrade, "create_new_tables", boom)
    status = schema_upgrade.run_startup_upgrade(eng)  # must not raise
    assert status["cache_ready"] is False and status["knowledge_base_ready"] is False
    assert "permission denied" in status["error"]
    assert "SCHEMA UPGRADE FAILED - app starting anyway" in capsys.readouterr().out

    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: [])
    with Session(bind=eng) as db:  # the old-schema database: the cache table lacks the new columns
        result = terms_lookup.lookup_terms(db, brand="Samsung", category="mobile", region="IN",
                                           model_code="SM-S928B", product_name="Samsung Galaxy S24", force_refresh=False)
        assert result.duration_months  # default rules, as before the cache existed
        assert db.execute(text("SELECT count(*) FROM warranty_terms_cache")).scalar() == 1  # nothing written


def test_app_still_boots_when_the_upgrade_fails(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("OCR_WARMUP", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")

    def boom(_engine):
        raise RuntimeError("lock timeout")

    monkeypatch.setattr(schema_upgrade, "create_new_tables", boom)
    monkeypatch.setattr(schema_upgrade, "check_ready", lambda _engine: {"cache_ready": False, "knowledge_base_ready": False})
    from app.main import app

    with TestClient(app) as client:  # runs the real start-up (lifespan -> init_db -> upgrade)
        assert schema_upgrade.STATUS["error"] == "RuntimeError: lock timeout"
        assert client.get("/api/health").status_code == 200
        token = client.post("/auth/login", data={"username": "admin", "password": "admin123"},
                            headers={"accept": "application/json"}).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        stats = client.get("/admin/terms-cache/stats", headers=auth).json()
        assert stats["schema"]["cache_ready"] is False and "lock timeout" in stats["schema"]["error"]
        assert client.get("/admin/knowledge-base", headers=auth).status_code == 503
