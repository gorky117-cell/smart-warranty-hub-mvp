from pathlib import Path
import json

from app.services import warranty_discovery as wd


def _empty_sources(tmp_path: Path) -> Path:
    p = tmp_path / "warranty_sources.json"
    p.write_text("[]", encoding="utf-8")
    return p


def _local_dev_sources(tmp_path: Path) -> Path:
    source_file = tmp_path / "synthetic_acmeco_zx100_warranty.html"
    source_file.write_text(
        """
        <html><body>
          <h1>Synthetic warranty</h1>
          <h2>Coverage</h2>
          <p>Standard warranty coverage is 12 months from purchase date.</p>
          <h2>Exclusions</h2>
          <p>Liquid damage is excluded.</p>
          <h2>Claim steps</h2>
          <p>Keep invoice ready.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    p = tmp_path / "warranty_sources.json"
    p.write_text(
        json.dumps(
            [
                {
                    "brand": "Acmeco",
                    "model_code": "ZX-100",
                    "product_name": "Microwave Oven",
                    "region": "IN",
                    "source_type": "oem_warranty",
                    "url": str(source_file),
                    "official": False,
                    "synthetic": True,
                }
            ]
        ),
        encoding="utf-8",
    )
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


def test_local_dev_sources_are_hidden_unless_enabled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(wd, "_ALLOW_LOCAL_DEV_SOURCES", False)
    monkeypatch.setattr(wd, "_SEARCH_MAX_QUERIES", 0)

    results = wd.discover_sources(
        brand="Acmeco",
        model_code="ZX-100",
        product_name="Microwave Oven",
        region="IN",
        data_path=_local_dev_sources(tmp_path),
    )

    assert results == []


def test_local_dev_sources_can_be_enabled_for_testing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(wd, "_ALLOW_LOCAL_DEV_SOURCES", True)
    monkeypatch.setattr(wd, "_SEARCH_MAX_QUERIES", 0)

    results = wd.discover_sources(
        brand="Acmeco",
        model_code="ZX-100",
        product_name="Microwave Oven",
        region="IN",
        data_path=_local_dev_sources(tmp_path),
    )

    assert results
    assert results[0].source_type == "oem_warranty"
    assert results[0].official is False
