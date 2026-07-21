from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .oem_domains import load_oem_domains, load_verified_domains


def _env_true(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def is_production() -> bool:
    env = (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("FASTAPI_ENV")
        or ""
    ).strip().lower()
    return env in ("prod", "production")


def normalize_host(url_or_host: Optional[str]) -> str:
    raw = (url_or_host or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        return (urlparse(raw).hostname or "").lower().strip()
    except Exception:
        return ""


def _normalize_brand(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def domains_for_brand(domain_map: Dict[str, List[str]], brand: Optional[str]) -> List[str]:
    wanted = _normalize_brand(brand)
    if not wanted:
        return []
    out: List[str] = []
    for key, values in (domain_map or {}).items():
        if _normalize_brand(key) != wanted:
            continue
        for value in values or []:
            host = normalize_host(value)
            if host and host not in out:
                out.append(host)
    return out


def host_matches_any(host: str, domains: List[str]) -> bool:
    clean_host = normalize_host(host)
    if not clean_host:
        return False
    for domain in domains or []:
        clean_domain = normalize_host(domain)
        if clean_domain and (clean_host == clean_domain or clean_host.endswith(f".{clean_domain}")):
            return True
    return False


def is_local_source(url: Optional[str]) -> bool:
    raw = (url or "").strip()
    if not raw:
        return False
    lower = raw.lower()
    if lower.startswith("test_data/") or lower.startswith("file://"):
        return True
    try:
        return Path(raw).exists()
    except Exception:
        return False


def local_dev_sources_allowed() -> bool:
    return _env_true("TERMS_ALLOW_LOCAL_DEV_SOURCES", "0")


def is_approved_oem_url(url: Optional[str], brand: Optional[str]) -> bool:
    if is_local_source(url):
        return local_dev_sources_allowed()
    host = normalize_host(url)
    if not host or not brand:
        return False
    approved = domains_for_brand(load_verified_domains(), brand) + domains_for_brand(load_oem_domains(), brand)
    return host_matches_any(host, approved)


def broad_search_allowed(
    *,
    brand: Optional[str],
    site_query_hits: int = 0,
    preflight_alive: bool = False,
    allow_broad_fallback: Optional[bool] = None,
    preflight_strict: Optional[bool] = None,
) -> bool:
    if not brand:
        return (not is_production()) or _env_true("TERMS_ALLOW_UNKNOWN_BRAND_SEARCH", "0")
    if preflight_alive and site_query_hits > 0:
        return False
    explicit = _env_true("TERMS_ALLOW_BROAD_FALLBACK", "0") if allow_broad_fallback is None else bool(allow_broad_fallback)
    if is_production():
        return explicit and _env_true("TERMS_ALLOW_PRODUCTION_BROAD_SEARCH", "0")
    if explicit:
        return True
    strict = _env_true("TERMS_PREFLIGHT_STRICT", "1") if preflight_strict is None else bool(preflight_strict)
    return not strict


def manual_url_allowed(url: Optional[str], brand: Optional[str]) -> bool:
    if not is_production():
        return True
    if _env_true("TERMS_ALLOW_PRODUCTION_MANUAL_URL", "0"):
        return True
    return is_approved_oem_url(url, brand)


def policy_snapshot(brand: Optional[str] = None, url: Optional[str] = None) -> Dict[str, object]:
    return {
        "production": is_production(),
        "official_only": _env_true("TERMS_OFFICIAL_ONLY", "0"),
        "preflight_strict": _env_true("TERMS_PREFLIGHT_STRICT", "1"),
        "broad_search_default": "disabled",
        "broad_search_allowed": broad_search_allowed(brand=brand),
        "manual_url_allowed": manual_url_allowed(url, brand) if url else None,
        "approved_oem_url": is_approved_oem_url(url, brand) if url else None,
        "local_dev_sources_allowed": local_dev_sources_allowed(),
    }
