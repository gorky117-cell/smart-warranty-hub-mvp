from app.services.oem import preflight_oem_fetch


def test_oem_fetch_preflight_allows_adapter_domain():
    out = preflight_oem_fetch("https://www.samsung.com/in/support/warranty/", "Samsung")

    assert out["ok"] is True
    assert out["mode"] == "controlled_adapter"
    assert out["reason"] == "approved_adapter_url"


def test_oem_fetch_preflight_blocks_adapter_off_domain():
    out = preflight_oem_fetch("https://example.com/samsung-warranty", "Samsung")

    assert out["ok"] is False
    assert out["mode"] == "controlled_adapter"
    assert out["reason"] == "url_not_allowed_for_adapter"


def test_oem_fetch_preflight_blocks_non_adapter_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("TERMS_ALLOW_PRODUCTION_MANUAL_URL", raising=False)

    out = preflight_oem_fetch("https://example.com/warranty", "UnknownBrand")

    assert out["ok"] is False
    assert out["mode"] == "approved_source_policy"
    assert out["reason"] == "url_not_approved_for_oem_fetch"
