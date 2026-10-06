from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import urlparse

from .oem_domains import load_manual_confirmed_domains, load_oem_domains, load_verified_domains


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _host(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _domains_for_brand(domain_map: Dict[str, list], brand: Optional[str]) -> list[str]:
    wanted = _normalize(brand)
    if not wanted:
        return []
    from .brand_families import is_unresolved_family

    if is_unresolved_family(brand):
        # A name shared by unrelated companies ("Bajaj", "Honda", "Bajaj Finserv") is not a company: no site is
        # its official one. Only the company chosen from the product category has official domains.
        return []
    for key, values in domain_map.items():
        if _normalize(key) == wanted:
            return [_normalize(v) for v in (values or []) if _normalize(v)]
    return []


def _display_brand(domain_map: Dict[str, list], brand: Optional[str]) -> str:
    wanted = _normalize(brand)
    for key in domain_map:
        if _normalize(key) == wanted:
            return key
    return (brand or "").strip()


# Country from the page address: a path segment (/in/, /en-in/, /uk/) or a country domain (.co.in, .in).
_COUNTRY_NAMES = {
    "in": "India", "us": "US", "uk": "UK", "gb": "UK", "ae": "UAE", "sg": "Singapore", "au": "Australia",
    "ca": "Canada", "my": "Malaysia", "sa": "Saudi Arabia", "nz": "New Zealand", "za": "South Africa",
    "bd": "Bangladesh", "lk": "Sri Lanka", "np": "Nepal", "ph": "Philippines", "id": "Indonesia",
}


def country_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    for part in [p.lower() for p in (parsed.path or "").split("/") if p]:
        codes = part.split("-") if "-" in part and len(part) == 5 else [part]  # "en-in" and "us-en"
        for code in codes:
            if code in _COUNTRY_NAMES:
                return _COUNTRY_NAMES[code]
    host = (parsed.hostname or "").lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[tld]
    if host.endswith("india.com") or "india" in host.split(".")[0]:
        return "India"
    return None


def official_page_label(brand: Optional[str], url: Optional[str]) -> str:
    """'From Samsung India's official warranty page' (country when the page address shows one)."""
    name = re.sub(r"\s+India$", "", (brand or "the brand").strip()) or "the brand"
    country = country_from_url(url)
    owner = f"{name} {country}" if country else name
    return f"From {owner}'s official warranty page"


def brand_page_url(company: Optional[str]) -> Optional[str]:
    """The brand's own website (verified, else manually confirmed), for "Estimated, please check" links.
    None for unknown brands and for shared names that are not a company ("Bajaj")."""
    for domains in (_domains_for_brand(load_verified_domains(), company),
                    _domains_for_brand(load_manual_confirmed_domains(), company)):
        if domains:
            return f"https://{domains[0]}"
    return None


def _matches_domain(host: str, domains: list[str]) -> bool:
    if not host:
        return False
    normalized_host = _normalize(host)
    for domain in domains:
        if normalized_host == domain or normalized_host.endswith(f".{domain}"):
            return True
    return False


def classify_terms_source(
    *,
    brand: Optional[str],
    source_url: Optional[str],
    source_type: Optional[str],
) -> Dict[str, object]:
    """
    Additive evidence classifier for customer-facing trust labels.
    It does not fetch, scrape, or modify warranty terms.
    """
    src_type = _normalize(source_type) or "unknown"
    src_url = source_url or None
    host = _host(src_url)

    if src_type in ("scraped", "approved_oem_source") and src_url:
        official_domains = _domains_for_brand(load_oem_domains(), brand)
        verified_domains = _domains_for_brand(load_verified_domains(), brand)
        manual_map = load_manual_confirmed_domains()
        verified = _matches_domain(host, verified_domains)
        manual = not verified and _matches_domain(host, _domains_for_brand(manual_map, brand))
        official = verified or manual or _matches_domain(host, official_domains)
        if src_type == "approved_oem_source" and official:
            status = "approved_oem_source"
            label = official_page_label(_display_brand(load_oem_domains(), brand), src_url)
            note = "Terms came from the brand's official warranty page."
            confidence = 0.88
        elif verified:
            status = "verified_official"
            # The check proves the website belongs to the brand, not that the scraped terms are correct.
            label = official_page_label(_display_brand(load_verified_domains(), brand), src_url)
            note = "Terms came from a website confirmed to belong to the brand."
            confidence = 0.9
        elif manual:
            status = "manually_confirmed_official"
            label = official_page_label(_display_brand(manual_map, brand), src_url) + " (manually confirmed)"
            note = "Terms came from a website a person confirmed belongs to the brand."
            confidence = 0.88
        elif official:
            status = "official"
            label = "From the brand's website"
            note = "These terms came from the brand's website. Please check them before making a claim."
            confidence = 0.85
        else:
            status = "external_unverified"
            label = "From another website - not confirmed"
            note = "These terms came from a website that is not the brand's own. Please check them with the brand."
            confidence = 0.55
        return {
            "status": status,
            "label": label,
            "note": note,
            "confidence": confidence,
            "source_url": src_url,
            "host": host,
            "official": official,
            "verified": verified or manual,
            "manually_confirmed": manual,
            "requires_oem_verification": not (verified or manual),
        }

    if src_type == "internal_warranty_db":
        return {
            "status": "internal_record",
            "label": "From a saved product",
            "note": "These terms came from a product already saved here.",
            "confidence": 0.8,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": False,
        }

    if src_type == "internal_terms_cache":
        return {
            "status": "cache",
            "label": "Saved copy of the terms",
            "note": "These terms come from a copy we saved earlier. Please check the brand's website before making a claim.",
            "confidence": 0.7,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": True,
        }

    if src_type == "default_rules":
        return {
            "status": "default_rules",
            "label": "Estimated, please check",
            "note": "We could not find this brand's own warranty terms, so these are typical terms for this kind of product. Please check your warranty card.",
            "confidence": 0.45,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": True,
        }

    if src_type == "invoice_only":
        return {
            "status": "invoice_only",
            "label": "Not confirmed yet",
            "note": "We read your invoice but have not found the brand's warranty terms yet.",
            "confidence": 0.35,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": True,
        }

    if src_type == "synthetic_approved":
        return {
            "status": "synthetic_test_source",
            "label": "Test data - not real terms",
            "note": "These terms are test data, not the brand's real terms.",
            "confidence": 0.6,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": True,
        }

    return {
        "status": "missing",
        "label": "Not confirmed yet",
        "note": "We don't know where these terms came from yet, so please don't rely on them for a claim.",
        "confidence": 0.3,
        "source_url": src_url,
        "host": host,
        "official": False,
        "verified": False,
        "requires_oem_verification": True,
    }
