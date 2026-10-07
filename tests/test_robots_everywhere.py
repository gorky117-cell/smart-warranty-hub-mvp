"""Every read of a brand's website obeys robots.txt: terms pages, the background domain check, the discovery
probe and the OEM page adapters."""

import socket

import pytest

from app.services import oem_adapters, oem_domain_verify, robots_guard, warranty_discovery


class _Resp:
    def __init__(self, status, text="", url="https://www.example.com/"):
        self.status_code, self.text, self.url, self.content = status, text, url, text.encode()
        self.history, self.headers, self.encoding, self.apparent_encoding = [], {"content-type": "text/html"}, "utf-8", "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    robots_guard.reset_cache()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [("ok",)])  # DNS answers in these tests
    yield
    robots_guard.reset_cache()


def _web(monkeypatch, robots_status, robots_text=""):
    pages = []

    def get(url, **kw):
        if url.endswith("/robots.txt"):
            return _Resp(robots_status, robots_text, url)
        pages.append(url)
        return _Resp(200, "<html><head><title>Samsung India</title></head></html>", url)

    monkeypatch.setattr(robots_guard.requests, "get", get)
    return pages


DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


def test_domain_check_never_loads_a_disallowed_site(monkeypatch):
    pages = _web(monkeypatch, 200, DISALLOW_ALL)
    detail = oem_domain_verify.verify_domain_detail("Samsung", "samsung.com")
    assert detail["verified"] is False and detail["reason"] == "robots_disallowed" and pages == []


def test_domain_check_still_works_where_allowed(monkeypatch):
    pages = _web(monkeypatch, 200, "User-agent: *\nAllow: /\n")
    detail = oem_domain_verify.verify_domain_detail("Samsung", "samsung.com")
    assert detail["verified"] is True and pages == ["https://samsung.com"]


@pytest.mark.parametrize("robots_status,text,alive,loaded", [
    (200, DISALLOW_ALL, True, False),        # answered robots.txt: alive, home page not loaded
    (403, "", True, False),                  # answered (blocked): alive, not loaded
    (200, "User-agent: *\nAllow: /\n", True, True),
])
def test_discovery_probe_obeys_robots(monkeypatch, robots_status, text, alive, loaded):
    pages = _web(monkeypatch, robots_status, text)
    monkeypatch.setattr(warranty_discovery.requests, "get", robots_guard.requests.get)
    assert warranty_discovery._domain_alive("example-brand.com", timeout=5) is alive
    assert bool(pages) is loaded


def test_discovery_probe_site_down(monkeypatch):
    def get(url, **kw):
        raise robots_guard.requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(robots_guard.requests, "get", get)
    assert warranty_discovery._domain_alive("example-brand.com", timeout=5) is False


def test_oem_adapter_is_blocked_by_robots(monkeypatch):
    pages = _web(monkeypatch, 200, DISALLOW_ALL)
    adapter = next(iter(oem_adapters._ADAPTERS.values()))
    url = f"https://www.{adapter.approved_domains[0]}/in/support/warranty/"
    result = adapter.fetch(url=url, model="X")
    assert result["status"] == "blocked" and result["reason"].startswith("robots_disallowed") and pages == []


# Backlog #13: the review crawler and issue feeds use the same check (fail closed).
import json  # noqa: E402

from app.services import oem_issue_feeds, review_crawler  # noqa: E402


@pytest.mark.parametrize("robots_status,text,allowed", [
    (200, DISALLOW_ALL, False),
    (200, "User-agent: SmartWarrantyHubBot\nDisallow: /\n", False),   # rule for the crawler's own name
    (200, "User-agent: OtherBot\nDisallow: /\n", True),               # rule for another agent only
    (403, "", False),                                                 # could not read the rules: not read
    (404, "", True),
])
def test_review_crawler_obeys_robots(monkeypatch, robots_status, text, allowed):
    monkeypatch.delenv("REVIEW_ROBOTS_RESPECT", raising=False)
    pages = _web(monkeypatch, robots_status, text)
    monkeypatch.setattr(review_crawler.requests, "get", robots_guard.requests.get)
    html, err, _status = review_crawler._fetch("https://reviews.example.com/p/1")
    if allowed:
        assert html and err is None and pages == ["https://reviews.example.com/p/1"]
    else:
        assert html is None and err == "robots_disallowed" and pages == []


def test_review_crawler_cannot_switch_robots_off(monkeypatch):
    monkeypatch.setenv("REVIEW_ROBOTS_RESPECT", "false")
    pages = _web(monkeypatch, 200, DISALLOW_ALL)
    monkeypatch.setattr(review_crawler.requests, "get", robots_guard.requests.get)
    assert review_crawler._robots_allowed("https://reviews.example.com/p/2") is False
    assert review_crawler._fetch("https://reviews.example.com/p/2")[1] == "robots_disallowed" and pages == []


def test_issue_feeds_obey_robots(monkeypatch, tmp_path):
    feeds = tmp_path / "feeds.json"
    feeds.write_text(json.dumps([{"url": "https://feeds.example.com/issues.json", "region": "IN"}]))
    pages = _web(monkeypatch, 200, DISALLOW_ALL)
    assert oem_issue_feeds.ingest_oem_issue_feeds(None, feed_path=feeds) == 0
    assert pages == []
