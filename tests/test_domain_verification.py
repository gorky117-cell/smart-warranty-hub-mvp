"""Domain verification (fix run B8): registry + DNS + HTTPS + same-brand redirects + brand evidence.
Network is mocked."""

from types import SimpleNamespace

import pytest
import requests

from app.services import oem_domain_verify as v


def _resp(url, status=200, html="", history=()):
    return SimpleNamespace(url=url, status_code=status, history=list(history), headers={"content-type": "text/html; charset=utf-8"},
                           content=html.encode("utf-8"), text=html)


@pytest.fixture
def net(monkeypatch):
    pages = {}
    monkeypatch.setattr(v, "load_oem_domains", lambda: {"Acme": ["acme.com"], "Zeta Home": ["zetahome.in"]}, raising=False)
    monkeypatch.setattr("app.services.oem_domains.load_oem_domains", lambda: {"Acme": ["acme.com"], "Zeta Home": ["zetahome.in"]})
    monkeypatch.setattr(v.socket, "getaddrinfo", lambda host, *a, **k: [] if host != "nodns.com" and host != "acme-nodns.com" else (_ for _ in ()).throw(OSError()))

    def fake_get(url, **_k):
        if url in pages:
            result = pages[url]
            if isinstance(result, Exception):
                raise result
            return result
        return _resp(url, status=404)

    monkeypatch.setattr(v, "_get", fake_get)
    return pages


def test_brand_in_title_verifies(net):
    net["https://acme.com"] = _resp("https://www.acme.com/in/", html="<html><head><title>ACME India | Home</title></head><body>x</body></html>")
    detail = v.verify_domain_detail("Acme", "acme.com")
    assert detail["verified"] and detail["steps"]["brand_evidence"] == "title_or_metadata"


def test_brand_in_og_site_name_and_multiword_brand(net):
    html = '<head><title>Welcome</title><meta property="og:site_name" content="Zeta Home Appliances"></head>'
    net["https://zetahome.in"] = _resp("https://zetahome.in/", html=html)
    assert v.verify_domain_detail("Zeta Home", "zetahome.in")["verified"]


def test_body_text_alone_is_not_evidence(net):
    net["https://acme.com"] = _resp("https://acme.com/", html="<head><title>Home</title></head><body>Acme warranty support</body>")
    detail = v.verify_domain_detail("Acme", "acme.com")
    assert not detail["verified"] and detail["reason"] == "no_brand_evidence"


def test_bot_blocked_homepage_verified_by_support_page(net):
    net["https://acme.com"] = _resp("https://acme.com/", status=403)
    net["https://acme.com/support"] = _resp("https://www.acme.com/in/support/")
    detail = v.verify_domain_detail("Acme", "acme.com")
    assert detail["verified"] and detail["steps"]["brand_evidence"] == "support_page:/support"


def test_redirect_to_another_brand_fails(net):
    hop = _resp("https://acme.com/")
    net["https://acme.com"] = _resp("https://parked-domains.example/", html="<title>Acme for sale</title>", history=[hop])
    assert v.verify_domain_detail("Acme", "acme.com")["reason"] == "redirect_to_other_brand"


def test_unmapped_domain_dns_and_https_failures(net):
    assert v.verify_domain_detail("Acme", "randomshop.com")["reason"] == "not_mapped_to_brand"
    assert v.verify_domain_detail("Acme", "acme-nodns.com")["reason"] == "dns_failed"
    net["https://acme.com"] = requests.exceptions.ConnectTimeout()
    assert v.verify_domain_detail("Acme", "acme.com")["reason"] == "https_failed"
    net["https://acme.com"] = _resp("https://acme.com/", status=500)
    assert v.verify_domain_detail("Acme", "acme.com")["reason"] == "https_status_500"


def test_verify_or_suggest_writes_only_passing_domains(net, monkeypatch):
    saved = {}
    monkeypatch.setattr(v, "load_verified_domains", lambda: {})
    monkeypatch.setattr(v, "save_verified_domains", lambda data: saved.update(data))
    monkeypatch.setattr(v, "search_web", lambda *a, **k: [])
    net["https://acme.com"] = _resp("https://acme.com/", html="<title>Acme</title>")
    assert v.verify_or_suggest(brand="Acme", domain="acme.com")["verified"] is True
    assert saved == {"Acme": ["acme.com"]}
    saved.clear()
    assert v.verify_or_suggest(brand="Acme", domain="randomshop.com")["verified"] is False
    assert saved == {}
