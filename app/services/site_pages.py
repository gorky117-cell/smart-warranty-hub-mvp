"""Public site pages, search-engine rules and the sitemap.

Only the pages in PUBLIC_PAGES may be indexed. Every other response (the customer app, the brand portal, the
admin pages and the API) carries ``X-Robots-Tag: noindex, nofollow``. robots.txt does not list app or admin
paths: a crawler must be able to fetch a page to see its noindex, and listing the admin address would reveal it.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Dict

SITE_URL = "https://www.smartwarrantyhub.com"
NOINDEX = "noindex, nofollow"

# Path -> template under templates/ (the homepage keeps its own route in main.py).
PUBLIC_PAGES: Dict[str, str] = {
    "/": "public_site.html",
    "/for-brands": "pages/for_brands.html",
    "/about": "pages/about.html",
    "/contact": "pages/contact.html",
    "/privacy": "pages/privacy.html",
    "/terms": "pages/terms.html",
    "/bot": "pages/bot.html",
    "/login": "login.html",
}
# Files that are fine for search engines and share previews to fetch.
_INDEXABLE_FILES = ("/robots.txt", "/sitemap.xml", "/favicon.ico")
_INDEXABLE_PREFIXES = ("/static/",)


def is_indexable(path: str) -> bool:
    path = path.rstrip("/") or "/"
    if path in PUBLIC_PAGES or path in _INDEXABLE_FILES:
        return True
    if path.startswith("/google") and path.endswith(".html"):  # Search Console verification file
        return True
    return path.startswith(_INDEXABLE_PREFIXES)


def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /auth/\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def sitemap_xml(now: datetime | None = None) -> str:
    day = (now or datetime.utcnow()).strftime("%Y-%m-%d")
    rows = []
    for path in PUBLIC_PAGES:
        priority = "1.0" if path == "/" else "0.6"
        rows.append(
            f"<url><loc>{escape(SITE_URL + path)}</loc><lastmod>{day}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>{priority}</priority></url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(rows) + "</urlset>"
    )
