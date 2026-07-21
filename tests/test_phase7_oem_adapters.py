from app.services import oem_adapters
from app.services.oem import fetch_oem_page


class _FakeResponse:
    status_code = 200
    text = """
    <html>
      <body>
        <section class="warranty-coverage">Coverage: 24 months warranty.</section>
        <section class="terms">Exclusions: liquid damage. Claim steps: Contact support.</section>
      </body>
    </html>
    """

    def raise_for_status(self):
        return None


def test_samsung_adapter_allows_only_approved_domains():
    adapter = oem_adapters.get_adapter("Samsung")

    assert adapter is not None
    assert adapter.allows_url("https://www.samsung.com/in/support/warranty/")
    assert not adapter.allows_url("https://example.com/samsung-warranty")


def test_oem_fetch_uses_samsung_controlled_adapter(monkeypatch):
    calls = []

    def _fake_get(url, headers=None, timeout=20):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(oem_adapters.requests, "get", _fake_get)

    artifact = fetch_oem_page(
        "https://www.samsung.com/in/support/warranty/",
        "Samsung",
        "ABC-100",
        "IN",
    )

    assert artifact.source == "oem-fetch"
    assert "SourceType: approved_oem_adapter" in artifact.content
    assert "Coverage: 24 months warranty." in artifact.content
    assert calls and calls[0]["url"].startswith("https://www.samsung.com/")


def test_oem_fetch_blocks_samsung_url_outside_adapter_domains():
    try:
        fetch_oem_page("https://example.com/samsung-warranty", "Samsung", "ABC-100", "IN")
    except ValueError as exc:
        assert "url_not_allowed_for_adapter" in str(exc)
    else:
        raise AssertionError("expected adapter to block unapproved domain")
