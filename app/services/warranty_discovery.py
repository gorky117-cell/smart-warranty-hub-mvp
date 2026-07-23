from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import os
import socket
from urllib.parse import urlparse

import requests

from .web_search import search_web
from . import oem_source_policy

@dataclass
class DiscoverySource:
    url: str
    source_type: str  # oem_warranty | oem_product | oem_manual_pdf | retail
    score: int
    official: bool = False
    brand: Optional[str] = None
    model_code: Optional[str] = None
    product_name: Optional[str] = None
    region: Optional[str] = None


_DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "warranty_sources.json"
from .oem_domains import load_oem_domains, load_verified_domains

_TYPE_SCORES = {
    "oem_warranty": 90,
    "oem_product": 70,
    "oem_manual_pdf": 60,
    "retail": 40,
}
_SEARCH_MAX_QUERIES = int(os.getenv("TERMS_SEARCH_MAX_QUERIES", "2"))
_SEARCH_MAX_RESULTS = int(os.getenv("TERMS_SEARCH_MAX_RESULTS", "5"))
_SEARCH_TIMEOUT = int(os.getenv("TERMS_SEARCH_TIMEOUT_SEC", "6"))
_OFFICIAL_ONLY = os.getenv("TERMS_OFFICIAL_ONLY", "false").strip().lower() in ("1", "true", "yes")
_PREFLIGHT_STRICT = os.getenv("TERMS_PREFLIGHT_STRICT", "true").strip().lower() in ("1", "true", "yes")
_ALLOW_BROAD_FALLBACK = os.getenv("TERMS_ALLOW_BROAD_FALLBACK", "false").strip().lower() in ("1", "true", "yes")
_PREFLIGHT_MAX_DOMAINS = int(os.getenv("TERMS_PREFLIGHT_MAX_DOMAINS", "4"))
_PREFLIGHT_TIMEOUT = int(os.getenv("TERMS_PREFLIGHT_TIMEOUT_SEC", "4"))
_ALLOW_LOCAL_DEV_SOURCES = os.getenv("TERMS_ALLOW_LOCAL_DEV_SOURCES", "false").strip().lower() in ("1", "true", "yes")
_DOMAIN_BOOTSTRAP_ENABLED = os.getenv("TERMS_DOMAIN_BOOTSTRAP_ENABLED", "true").strip().lower() in ("1", "true", "yes")
_DOMAIN_BOOTSTRAP_MAX_RESULTS = int(os.getenv("TERMS_DOMAIN_BOOTSTRAP_MAX_RESULTS", "5"))
_DOMAIN_BOOTSTRAP_MAX_DOMAINS = int(os.getenv("TERMS_DOMAIN_BOOTSTRAP_MAX_DOMAINS", "3"))

_DOMAIN_REJECT_MARKERS = (
    "amazon.",
    "flipkart.",
    "jiomart.",
    "meesho.",
    "myntra.",
    "snapdeal.",
    "youtube.",
    "facebook.",
    "instagram.",
    "linkedin.",
    "wikipedia.",
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""

def _region_score(region: Optional[str], url: str) -> int:
    if not region:
        return 0
    reg = region.strip().lower()
    host = _host(url)
    score = 0
    if reg and reg in url.lower():
        score += 8
    # Check country code in region like "US-CA" or "IN"
    country = reg.split("-")[0] if reg else reg
    if country and host.endswith(f".{country}"):
        score += 6
    return score


def _domains_for_brand(domain_map: Dict[str, List[str]], brand: Optional[str]) -> List[str]:
    return oem_source_policy.domains_for_brand(domain_map, brand)


def _host_matches_any(host: str, domains: List[str]) -> bool:
    return oem_source_policy.host_matches_any(host, domains)


def _domain_alive(domain: str, timeout: int) -> bool:
    host = _normalize(domain)
    if not host:
        return False
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False

    headers = {"User-Agent": "SmartWarrantyHub/1.0"}
    try:
        resp = requests.get(f"https://{host}", timeout=timeout, headers=headers, allow_redirects=True)
        if resp.status_code < 500:
            return True
    except requests.exceptions.RequestException:
        pass

    try:
        resp = requests.get(f"http://{host}", timeout=timeout, headers=headers, allow_redirects=True)
        if resp.status_code < 500:
            return True
    except requests.exceptions.RequestException:
        pass
    return False


def _classify_url(url: str) -> str:
    lower = url.lower()
    if "warranty" in lower or "terms" in lower:
        return "oem_warranty"
    if lower.endswith(".pdf") or "manual" in lower:
        return "oem_manual_pdf"
    if "product" in lower or "support" in lower:
        return "oem_product"
    return "retail"


def _load_sources(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _verified_match(brand: Optional[str], host: str, verified: Dict[str, List[str]]) -> bool:
    if not brand or not host:
        return False
    doms = _domains_for_brand(verified, brand)
    return _host_matches_any(host, doms)


def _normalize(val: Optional[str]) -> str:
    return (val or "").strip().lower()


def _preflight_domains(brand: Optional[str], oem_domains: Dict[str, List[str]], verified_domains: Dict[str, List[str]]) -> List[str]:
    verified = _domains_for_brand(verified_domains, brand)
    official = _domains_for_brand(oem_domains, brand)
    candidates: List[str] = []
    for d in verified + official:
        if d and d not in candidates:
            candidates.append(d)
    if not candidates:
        return []
    alive: List[str] = []
    for d in candidates[: max(0, _PREFLIGHT_MAX_DOMAINS)]:
        if _domain_alive(d, timeout=_PREFLIGHT_TIMEOUT):
            alive.append(d)
    return alive


def _brand_token_in_host(brand: Optional[str], host: str) -> bool:
    brand_norm = _normalize(brand)
    host_norm = _normalize(host).replace("-", "")
    if not brand_norm or not host_norm:
        return False
    return brand_norm.replace(" ", "") in host_norm


def _reject_bootstrap_host(host: str) -> bool:
    clean = _normalize(host)
    return any(marker in clean for marker in _DOMAIN_REJECT_MARKERS)


def _bootstrap_candidate_domains(brand: Optional[str], region: Optional[str]) -> List[str]:
    if not _DOMAIN_BOOTSTRAP_ENABLED or not brand:
        return []
    queries = [
        f"{brand} official website",
        f"{brand} warranty support official",
    ]
    if region:
        queries.append(f"{brand} {region} official website")
    candidates: Dict[str, int] = {}
    for q in queries[:2]:
        for item in search_web(q, count=_DOMAIN_BOOTSTRAP_MAX_RESULTS, timeout=_SEARCH_TIMEOUT):
            host = _host(item.get("url") or "")
            if not host or _reject_bootstrap_host(host):
                continue
            if not _brand_token_in_host(brand, host):
                continue
            score = 10
            if region and host.endswith(f".{region.lower()}"):
                score += 4
            if host.startswith("www."):
                score += 1
            candidates[host] = max(candidates.get(host, 0), score)
    ranked = [host for host, _score in sorted(candidates.items(), key=lambda item: item[1], reverse=True)]
    alive: List[str] = []
    for host in ranked:
        if len(alive) >= max(0, _DOMAIN_BOOTSTRAP_MAX_DOMAINS):
            break
        if _domain_alive(host, timeout=_PREFLIGHT_TIMEOUT):
            alive.append(host)
    return alive


def _match_score(entry: Dict, brand: str, model_code: Optional[str], product_name: Optional[str]) -> int:
    score = 0
    if _normalize(entry.get("brand")) == _normalize(brand):
        score += 20
    if model_code and _normalize(entry.get("model_code")) == _normalize(model_code):
        score += 15
    if product_name and _normalize(entry.get("product_name")) == _normalize(product_name):
        score += 10
    return score


def discover_sources(
    brand: Optional[str],
    model_code: Optional[str],
    product_name: Optional[str],
    region: Optional[str] = None,
    *,
    mode: str = "auto+manual",
    allow_retail: bool = True,
    data_path: Optional[Path] = None,
) -> List[DiscoverySource]:
    """
    Discover candidate warranty sources from:
    1) curated local source file entries
    2) configured online search providers.
    """
    if "auto" not in mode:
        return []

    path = data_path or _DEFAULT_DATA_PATH
    raw = _load_sources(path)
    oem_domains = load_oem_domains()
    verified_domains = load_verified_domains()
    official_for_brand = _domains_for_brand(oem_domains, brand)
    preflight_alive_domains = _preflight_domains(brand, oem_domains, verified_domains)
    if not preflight_alive_domains and not official_for_brand:
        preflight_alive_domains = _bootstrap_candidate_domains(brand, region)
        official_for_brand = preflight_alive_domains[:]
    results: List[DiscoverySource] = []
    for entry in raw:
        entry_brand = _normalize(entry.get("brand"))
        if brand and entry_brand and entry_brand != _normalize(brand):
            continue
        if not brand:
            entry_model = _normalize(entry.get("model_code"))
            entry_product = _normalize(entry.get("product_name"))
            model_match = bool(model_code and entry_model and entry_model == _normalize(model_code))
            product_match = bool(product_name and entry_product and entry_product == _normalize(product_name))
            if not (model_match or product_match):
                continue
        if not allow_retail and entry.get("source_type") == "retail":
            continue
        url = str(entry.get("url") or "")
        is_local_source = oem_source_policy.is_local_source(url)
        if is_local_source and not oem_source_policy.local_dev_sources_allowed():
            continue
        host = _host(url)
        entry_official_domains = _domains_for_brand(oem_domains, entry.get("brand") or "")
        official = _host_matches_any(host, entry_official_domains) if entry_official_domains else bool(entry.get("official", False))
        verified = _verified_match(entry.get("brand") or "", host, verified_domains)
        if _OFFICIAL_ONLY and brand and not official:
            continue
        if region and entry.get("region") and _normalize(entry.get("region")) != _normalize(region):
            continue
        base = _TYPE_SCORES.get(entry.get("source_type") or "", 30)
        score = base + _match_score(entry, brand, model_code, product_name) + _region_score(region, url)
        score += 12 if official else 0
        score += 15 if verified else 0
        results.append(
            DiscoverySource(
                url=url,
                source_type=str(entry.get("source_type") or "oem_warranty"),
                score=score,
                official=official,
                brand=entry.get("brand"),
                model_code=entry.get("model_code"),
                product_name=entry.get("product_name"),
                region=entry.get("region"),
            )
        )

    # Online search (if API key present)
    queries: List[str] = []
    if brand and model_code:
        queries.append(f"{brand} {model_code} warranty terms claim process")
        queries.append(f"{brand} {model_code} warranty policy pdf")
    if brand and product_name:
        queries.append(f"{brand} {product_name} warranty terms")
    if brand:
        queries.append(f"{brand} warranty terms conditions")
    if (not brand) and model_code:
        queries.append(f"{model_code} warranty terms")
        queries.append(f"{model_code} warranty policy pdf")
    if (not brand) and product_name:
        queries.append(f"{product_name} warranty terms")

    # Preserve order and uniqueness.
    uniq_queries: List[str] = []
    seen_queries = set()
    for q in queries:
        k = _normalize(q)
        if not k or k in seen_queries:
            continue
        seen_queries.add(k)
        uniq_queries.append(q)
    queries = uniq_queries[: max(_SEARCH_MAX_QUERIES, 0)]

    if queries:
        def _append_search_items(search_query: str) -> int:
            added = 0
            items = search_web(search_query, count=_SEARCH_MAX_RESULTS, timeout=_SEARCH_TIMEOUT)
            for item in items:
                url = item.get("url") or ""
                if not url:
                    continue
                source_type = _classify_url(url)
                if not allow_retail and source_type == "retail":
                    continue
                host = _host(url)
                official = _host_matches_any(host, official_for_brand) if official_for_brand else (_normalize(brand) in host if brand else False)
                verified = _verified_match(brand, host, verified_domains)
                if _OFFICIAL_ONLY and brand and not official:
                    continue
                base = _TYPE_SCORES.get(source_type, 30)
                score = base + (10 if official else 0) + (15 if verified else 0) + _region_score(region, url)
                results.append(
                    DiscoverySource(
                        url=url,
                        source_type=source_type,
                        score=score,
                        official=official,
                        brand=brand,
                        model_code=model_code,
                        product_name=product_name,
                        region=region,
                    )
                )
                added += 1
            return added

        site_query_hits = 0
        if preflight_alive_domains:
            for q in queries:
                for domain in preflight_alive_domains:
                    site_query_hits += _append_search_items(f"site:{domain} {q}")

        should_run_broad = oem_source_policy.broad_search_allowed(
            brand=brand,
            site_query_hits=site_query_hits,
            preflight_alive=bool(preflight_alive_domains),
            allow_broad_fallback=_ALLOW_BROAD_FALLBACK,
            preflight_strict=_PREFLIGHT_STRICT,
        )
        if should_run_broad:
            for q in queries:
                _append_search_items(q)

    results = [r for r in results if r.url]
    results.sort(key=lambda x: x.score, reverse=True)
    # Deduplicate by URL, keep highest score
    seen = set()
    deduped: List[DiscoverySource] = []
    for r in results:
        if r.url in seen:
            continue
        seen.add(r.url)
        deduped.append(r)
    return deduped
