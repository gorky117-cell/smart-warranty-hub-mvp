from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urlparse

from .oem_domains import load_oem_domains, load_verified_domains


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
    for key, values in domain_map.items():
        if _normalize(key) == wanted:
            return [_normalize(v) for v in (values or []) if _normalize(v)]
    return []


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
        verified = _matches_domain(host, verified_domains)
        official = verified or _matches_domain(host, official_domains)
        if src_type == "approved_oem_source" and official:
            status = "approved_oem_source"
            label = "Approved OEM source"
            note = "Terms came from an approved OEM source path."
            confidence = 0.88
        elif verified:
            status = "verified_official"
            label = "Verified official source"
            note = "Terms came from a verified OEM domain."
            confidence = 0.9
        elif official:
            status = "official"
            label = "Official OEM domain"
            note = "Terms came from a known OEM domain. Verify before claim submission."
            confidence = 0.85
        else:
            status = "external_unverified"
            label = "External source, not verified"
            note = "Terms came from an external source that is not in the approved OEM source list."
            confidence = 0.55
        return {
            "status": status,
            "label": label,
            "note": note,
            "confidence": confidence,
            "source_url": src_url,
            "host": host,
            "official": official,
            "verified": verified,
            "requires_oem_verification": not verified,
        }

    if src_type == "internal_warranty_db":
        return {
            "status": "internal_record",
            "label": "Saved warranty record",
            "note": "Terms came from an existing saved warranty record.",
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
            "label": "Local cache",
            "note": "Terms came from the local terms cache. Refresh from OEM source if claim certainty is required.",
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
            "label": "Default rules only",
            "note": "Terms are estimated from category/default rules and are not confirmed by an OEM source.",
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
            "label": "Invoice only",
            "note": "Invoice data was found, but official warranty terms have not been confirmed.",
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
            "label": "Synthetic approved test source",
            "note": "Terms came from a synthetic source fixture for testing only. Verify with OEM before relying on it for a claim.",
            "confidence": 0.6,
            "source_url": src_url,
            "host": host,
            "official": False,
            "verified": False,
            "requires_oem_verification": True,
        }

    return {
        "status": "missing",
        "label": "No approved source",
        "note": "Source evidence is missing. Do not treat these warranty terms as confirmed.",
        "confidence": 0.3,
        "source_url": src_url,
        "host": host,
        "official": False,
        "verified": False,
        "requires_oem_verification": True,
    }
