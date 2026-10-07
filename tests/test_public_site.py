"""Public site (batch 5): titles, previews, the owner's wording, footer pages, noindex, sitemap and robots.txt."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import site_pages

HTML = {"accept": "text/html"}
TITLE = "Smart Warranty Hub - The after-purchase bridge between you and your brands"
DESCRIPTION = (
    "Upload your invoice once. Track warranties, get care tips and early warnings for phones, appliances and "
    "EV batteries, and stay connected to your brands."
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def home(client):
    r = client.get("/", headers=HTML)
    assert r.status_code == 200
    return r.text


def _meta(html, attr, name):
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def test_homepage_title_description_and_previews(home):
    assert f"<title>{TITLE}</title>" in home
    assert _meta(home, "name", "description") == DESCRIPTION
    assert _meta(home, "property", "og:title") == TITLE
    assert _meta(home, "property", "og:description") == DESCRIPTION
    assert _meta(home, "name", "twitter:title") == TITLE
    assert _meta(home, "name", "twitter:description") == DESCRIPTION
    assert _meta(home, "name", "twitter:card") == "summary_large_image"
    assert _meta(home, "property", "og:image") == "https://www.smartwarrantyhub.com/static/brand/og-image.png"
    assert _meta(home, "property", "og:url") == "https://www.smartwarrantyhub.com/"
    assert '<link rel="canonical" href="https://www.smartwarrantyhub.com/">' in home
    assert _meta(home, "name", "robots") == "index,follow"
    assert 'rel="icon" href="/static/brand/favicon.svg"' in home


def test_share_image_and_favicons_are_served(client):
    for path, kind in (
        ("/static/brand/og-image.png", "image/png"),
        ("/static/brand/apple-touch-icon.png", "image/png"),
        ("/static/brand/favicon.svg", "image/svg+xml"),
        ("/favicon.ico", "image/x-icon"),
    ):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["content-type"].startswith(kind), path
        assert len(r.content) > 100


def test_hero_wording(home):
    for text in (
        "The after-purchase bridge between you and your brands.",
        "Upload once. We track warranties, guide care and spot problems early, for phones, appliances and EV "
        "batteries, and keep you connected to your brands.",
        "Add your first product",
        "For brands and service partners",
        "Your AC",
        "Warranty facts - checked",
        "Clean the filter before summer",
        "Brand updates - with your consent",
        "Patent pending (India &amp; PCT)",
        "Your data stays private",
    ):
        assert text in home, text
    chips = re.search(r'<ul class="chips"[^>]*>(.*?)</ul>', home, re.S).group(1)
    assert re.findall(r"<li>(.*?)</li>", chips) == [
        "Warranty", "Care tips", "Early warnings", "Claims", "EV batteries", "Brand insights"
    ]
    # The example card is HTML with a text alternative, not an image.
    assert 'class="product-card" role="img" aria-label="' in home


def test_who_we_help_has_five_tabs_with_pilot_goals(home):
    tabs = re.findall(r'role="tab" id="tab-(\w+)"[^>]*>([^<]+)</button>', home)
    assert [label for _, label in tabs] == [
        "Customers", "Brands (OEMs)", "Insurers &amp; TPAs", "Retailers", "Suppliers &amp; service partners"
    ]
    for key, _ in tabs:
        panel = re.search(rf'<div class="tab-panel" role="tabpanel" id="panel-{key}".*?\n      </div>', home, re.S)
        assert panel, key
        body = panel.group(0)
        assert "<h3>Pain points</h3>" in body and "<h3>How SWH helps</h3>" in body
        assert '<div class="goals"><span class="goal-label">Pilot goal</span>' in body
    assert home.count('role="tabpanel"') == 5
    assert home.count(' hidden>') == 4  # only the first tab is open at load
    for text in (
        "No more than 1 in 5 alerts turns out to be unnecessary.",
        "Issue signals at least 14 days before a service spike.",
        "Pattern checks that flag claims for human review (never automatic rejection).",
        "20% fewer escalations per 1,000 units sold.",
        "Critical parts out of stock less than 5% of the time.",
        "Pilot goals are targets we will measure with our first partners against their current numbers. "
        "Measured results will be published after the pilots.",
    ):
        assert text in home, text


def test_sections_in_order_and_old_content_removed(home):
    order = ["Who we help", "How it works", "Beyond warranty", "For brands, TPAs, retailers and service partners",
             "Trust and privacy"]
    positions = [home.index(f">{title}</h2>") for title in order]
    assert positions == sorted(positions)
    assert "Care tips and health signals for your EV battery." in home
    assert 'href="mailto:support@smartwarrantyhub.com?subject=Pilot%20partner">Become a pilot partner</a>' in home
    for gone in ("Simple, Smart Warranty Support", "Platform Modules", "OCR ingestion", "RAG", "canonical mapping",
                 "Neo Dashboard", "OEM Dashboard", "Admin Hub", "Scheduler", "/ui/", "/sitemap.xml"):
        assert gone not in home, gone


def test_public_nav_and_footer(client):
    for path in ("/", "/about", "/for-brands"):
        html = client.get(path, headers=HTML).text
        nav = re.search(r'<nav class="topnav"[^>]*>(.*?)</nav>', html, re.S).group(1)
        assert re.findall(r">([^<]+)</a>", nav) == ["For brands", "Sign in"], path
        footer = re.search(r'<footer class="footer">(.*?)</footer>', html, re.S).group(1)
        links = re.findall(r'<a href="(/[^"]*)">([^<]+)</a>', footer)
        assert links == [("/about", "About"), ("/contact", "Contact"), ("/privacy", "Privacy"),
                         ("/terms", "Terms"), ("/bot", "/bot"), ("/for-brands", "For brands")], path


@pytest.mark.parametrize("path", ["/about", "/contact", "/privacy", "/terms", "/bot", "/for-brands"])
def test_footer_pages_are_indexable_with_own_title(client, path):
    r = client.get(path, headers=HTML)
    assert r.status_code == 200
    assert "x-robots-tag" not in r.headers
    title = re.search(r"<title>(.*?)</title>", r.text).group(1)
    assert title.endswith(" - Smart Warranty Hub")
    assert f'<link rel="canonical" href="https://www.smartwarrantyhub.com{path}">' in r.text
    assert _meta(r.text, "name", "description")


def test_bot_page_explains_robots_and_user_agent(client):
    html = client.get("/bot", headers=HTML).text
    assert "SmartWarrantyHub" in html and "robots.txt" in html
    assert "User-agent: SmartWarrantyHub\nDisallow: /" in html


@pytest.mark.parametrize("path", [
    "/ui/neo-dashboard", "/ui/oem-dashboard", "/ui/admin-hub", "/ui/scheduler", "/ui/admin/knowledge-base",
    "/api/health", "/warranties/list", "/admin/knowledge-base", "/forgot-password",
])
def test_app_admin_and_api_responses_are_noindex(client, path):
    r = client.get(path, headers=HTML, follow_redirects=False)
    assert r.headers.get("x-robots-tag") == "noindex, nofollow", path


def test_is_indexable_only_for_public_pages():
    for path in ("/", "/about", "/for-brands", "/login", "/robots.txt", "/static/site.css", "/favicon.ico"):
        assert site_pages.is_indexable(path), path
    for path in ("/ui/neo-dashboard", "/partners/login", "/admin/x", "/oem/questions/active", "/auth/login",
                 "/api/health", "/account/email"):
        assert not site_pages.is_indexable(path), path


def test_sitemap_lists_only_public_pages(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and "xml" in r.headers["content-type"]
    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    assert locs == [f"https://www.smartwarrantyhub.com{p}" for p in site_pages.PUBLIC_PAGES]
    for path in locs:
        assert site_pages.is_indexable(path.replace("https://www.smartwarrantyhub.com", ""))
    assert "/ui/" not in r.text and "health" not in r.text


def test_robots_txt_points_to_sitemap_and_hides_admin(client):
    body = client.get("/robots.txt").text
    assert "Sitemap: https://www.smartwarrantyhub.com/sitemap.xml" in body
    assert "admin" not in body.lower()


def test_design_tokens_present(client):
    css = client.get("/static/site.css").text
    for token in ("--navy: #0F1B3D", "--navy-2: #1E3A8A", "--blue: #2563EB", "--green: #0F9F8F",
                  "--amber: #F59E0B", "--red: #DC2626", "--bg: #F5F8FF", "--ink: #0F172A", "--muted: #475569"):
        assert token in css, token
    assert "focus-visible" in css
    # Pilot goals use teal, never amber or red.
    goals = re.search(r"\.goals \{[^}]*\}", css).group(0)
    assert "amber" not in goals and "red" not in goals
