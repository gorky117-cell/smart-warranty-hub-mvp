from pathlib import Path

from app.services import warranty_discovery as wd


def _empty_sources(tmp_path: Path) -> Path:
    p = tmp_path / "warranty_sources.json"
    p.write_text("[]", encoding="utf-8")
    return p


def test_strict_preflight_skips_search_when_no_alive_domain(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(wd, "_PREFLIGHT_STRICT", True)
    monkeypatch.setattr(wd, "_ALLOW_BROAD_FALLBACK", False)
    monkeypatch.setattr(wd, "_SEARCH_MAX_QUERIES", 1)
    monkeypatch.setattr(wd, "_SEARCH_MAX_RESULTS", 3)
    monkeypatch.setattr(wd, "_OFFICIAL_ONLY", False)
    monkeypatch.setattr(wd, "load_oem_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "load_verified_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "_domain_alive", lambda _domain, timeout: False)

    calls = []

    def _fake_search(query: str, count: int = 5, timeout: int = 6):
        calls.append(query)
        return []

    monkeypatch.setattr(wd, "search_web", _fake_search)

    results = wd.discover_sources(
        brand="Samsung",
        model_code="ABC-100",
        product_name="TV",
        region="IN",
        data_path=_empty_sources(tmp_path),
    )

    assert results == []
    assert calls == []


def test_strict_preflight_uses_site_query_when_alive(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(wd, "_PREFLIGHT_STRICT", True)
    monkeypatch.setattr(wd, "_ALLOW_BROAD_FALLBACK", False)
    monkeypatch.setattr(wd, "_SEARCH_MAX_QUERIES", 1)
    monkeypatch.setattr(wd, "_SEARCH_MAX_RESULTS", 3)
    monkeypatch.setattr(wd, "_OFFICIAL_ONLY", False)
    monkeypatch.setattr(wd, "load_oem_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "load_verified_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "_domain_alive", lambda _domain, timeout: True)

    calls = []

    def _fake_search(query: str, count: int = 5, timeout: int = 6):
        calls.append(query)
        return [{"url": "https://www.samsung.com/in/support/warranty/"}]

    monkeypatch.setattr(wd, "search_web", _fake_search)

    results = wd.discover_sources(
        brand="Samsung",
        model_code="ABC-100",
        product_name="TV",
        region="IN",
        data_path=_empty_sources(tmp_path),
    )

    assert results
    assert calls
    assert all(q.startswith("site:samsung.com ") for q in calls)
    assert results[0].official is True


def test_non_strict_can_broad_fallback_when_site_queries_fail(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(wd, "_PREFLIGHT_STRICT", False)
    monkeypatch.setattr(wd, "_ALLOW_BROAD_FALLBACK", True)
    monkeypatch.setattr(wd, "_SEARCH_MAX_QUERIES", 1)
    monkeypatch.setattr(wd, "_SEARCH_MAX_RESULTS", 3)
    monkeypatch.setattr(wd, "_OFFICIAL_ONLY", False)
    monkeypatch.setattr(wd, "load_oem_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "load_verified_domains", lambda: {"Samsung": ["samsung.com"]})
    monkeypatch.setattr(wd, "_domain_alive", lambda _domain, timeout: True)

    calls = []

    def _fake_search(query: str, count: int = 5, timeout: int = 6):
        calls.append(query)
        if query.startswith("site:samsung.com "):
            return []
        return [{"url": "https://www.samsung.com/in/support/warranty/"}]

    monkeypatch.setattr(wd, "search_web", _fake_search)

    results = wd.discover_sources(
        brand="Samsung",
        model_code="ABC-100",
        product_name="TV",
        region="IN",
        data_path=_empty_sources(tmp_path),
    )

    assert results
    assert any(q.startswith("site:samsung.com ") for q in calls)
    assert any(not q.startswith("site:samsung.com ") for q in calls)
