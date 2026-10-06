"""Terms source order (step 1): partner feed -> knowledge base -> website only where robots.txt allows ->
"Estimated, please check" + link to the brand's page; per-brand reuse policy (link_only by default)."""

import json
from types import SimpleNamespace

import pytest

from app.db import SessionLocal
from app.models import TermsResult
from app.services import partner_feed, reuse_policy, robots_guard, terms_lookup, warranty_parser
from app.services.source_trust import brand_page_url
from app.services.summary_engine import build_evidence_summary


class _Resp:
    def __init__(self, status, text="", content_type="text/html"):
        self.status_code, self.text, self.content = status, text, text.encode()
        self.headers = {"content-type": content_type}


@pytest.fixture(autouse=True)
def _fresh():
    robots_guard.reset_cache()
    reuse_policy.reset_cache()
    yield
    robots_guard.reset_cache()
    reuse_policy.reset_cache()


def _fake_web(monkeypatch, robots):
    """robots: (status, text) for /robots.txt; every other page is a small warranty page."""
    calls = []

    def get(url, timeout=None, headers=None, **kw):
        calls.append(url)
        if url.endswith("/robots.txt"):
            if isinstance(robots, Exception):
                raise robots
            return _Resp(*robots)
        return _Resp(200, "<html><body><h2>Warranty</h2><p>The product is covered for 12 months from the date of purchase."
                          " Damage caused by liquid is not covered.</p></body></html>")

    monkeypatch.setattr(robots_guard.requests, "get", get)
    monkeypatch.setattr(warranty_parser.requests, "get", get)
    return calls


@pytest.mark.parametrize("robots,allowed", [
    ((200, "User-agent: *\nAllow: /\n"), True),
    ((200, "User-agent: *\nDisallow: /in/support/\n"), False),
    ((200, "User-agent: SmartWarrantyHub\nDisallow: /\n\nUser-agent: *\nAllow: /\n"), False),
    ((404, ""), True),                         # no robots.txt: allowed
    ((403, "Forbidden"), False),               # could not see the rules: not allowed
    ((503, ""), False),
    (OSError("no network"), False),
])
def test_robots_decides_whether_a_page_is_read(monkeypatch, robots, allowed):
    calls = _fake_web(monkeypatch, robots)
    parsed, err = warranty_parser.parse_terms_from_url("https://www.example-brand.com/in/support/warranty/")
    pages = [c for c in calls if not c.endswith("/robots.txt")]
    if allowed:
        assert err is None and parsed is not None and pages
    else:
        assert parsed is None and err.startswith("robots_disallowed") and pages == []  # the page is never fetched


def test_robots_result_is_cached_per_site(monkeypatch):
    calls = _fake_web(monkeypatch, (200, "User-agent: *\nAllow: /\n"))
    for _ in range(3):
        robots_guard.check("https://www.example-brand.com/a")
    assert sum(c.endswith("/robots.txt") for c in calls) == 1


def test_partner_feed_comes_before_everything(monkeypatch):
    fed = TermsResult(duration_months=24, terms=["From the partner"], exclusions=[], claim_steps=[], source_url="partner://x")
    monkeypatch.setattr(partner_feed, "lookup", lambda **kw: fed)
    with SessionLocal() as db:
        result = terms_lookup.lookup_terms(db, brand="Samsung", category="mobile", region="IN", model_code="SM-M175F",
                                           product_name="Galaxy M17e")
    assert result is fed


def test_partner_feed_placeholder_is_empty():
    assert partner_feed.lookup(company="Samsung", model_code="X", product_line="smartphone", region="IN") is None


def test_reuse_policy_default_and_permissions(monkeypatch, tmp_path):
    assert reuse_policy.policy_for("Samsung") == "link_only"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"default": "link_only", "brands": {
        "Voltas": {"policy": "summary_ok", "granted_by": "Voltas legal (test)", "granted_on": "2026-10-06"},
        "LG": {"policy": "full_text_ok"},  # no who/when: does not count
    }}), encoding="utf-8")
    monkeypatch.setattr(reuse_policy, "_PATH", path)
    reuse_policy.reset_cache()
    assert reuse_policy.policy_for("voltas") == "summary_ok" and reuse_policy.allows("Voltas", "summary_ok")
    assert not reuse_policy.allows("Voltas", "full_text_ok")
    assert reuse_policy.policy_for("LG") == "link_only"


@pytest.mark.parametrize("brand,page", [
    ("Samsung", "https://samsung.com"), ("Bajaj Electricals", "https://bajajelectricals.com"),
    ("Bajaj", None), ("Zyxor", None),
])
def test_brand_page_link(brand, page):
    assert brand_page_url(brand) == page


def test_estimated_terms_carry_a_link_to_the_brands_page():
    w = SimpleNamespace(id="w", brand="Samsung", product_name="Galaxy M17e", model_code="SM-M175F",
                        alternatives={"terms_source_type": "default_rules"}, terms_source_url=None)
    evidence = build_evidence_summary(w)
    assert evidence["status_label"] == "Estimated, please check" and evidence["brand_page_url"] == "https://samsung.com"
