from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .web_search import search_web
from .oem_domains import load_oem_domains, load_verified_domains, save_verified_domains


KEYWORDS = ("warranty", "support", "service", "manual", "register", "terms")


def _normalize_domain(domain: str) -> str:
    domain = (domain or "").strip()
    if not domain:
        return ""
    if "://" not in domain:
        domain = "https://" + domain
    try:
        host = urlparse(domain).hostname or ""
    except Exception:
        host = domain
    return host.lower().strip()


def _fetch_text(url: str, timeout: int = 6) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "SmartWarrantyHub/1.0"})
        if resp.status_code >= 400:
            return None
        return resp.text[:6000]
    except Exception:
        return None


def _contains_brand(text: str, brand: str) -> bool:
    if not text or not brand:
        return False
    return brand.lower() in text.lower()


def _contains_keywords(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k in low for k in KEYWORDS)


def _verify_domain(brand: str, domain: str) -> Tuple[bool, str]:
    host = _normalize_domain(domain)
    if not host:
        return False, "invalid_domain"
    html = _fetch_text(f"https://{host}")
    if not html:
        return False, "unreachable"
    if not _contains_brand(html, brand):
        return False, "brand_not_found"
    if not _contains_keywords(html):
        return False, "keywords_not_found"
    return True, "verified"


def _score_candidate(host: str, brand: str, region: Optional[str], oem_domains: Dict[str, List[str]]) -> int:
    score = 0
    if brand and brand.lower() in host:
        score += 10
    doms = oem_domains.get(brand, [])
    if any(host.endswith(d) for d in doms):
        score += 15
    if region and host.endswith(f".{region.lower()}"):
        score += 4
    return score


def verify_or_suggest(
    *,
    brand: str,
    domain: str,
    region: Optional[str] = None,
) -> Dict[str, object]:
    brand = (brand or "").strip()
    domain = (domain or "").strip()
    if not brand:
        return {"ok": False, "verified": False, "reason": "missing_brand", "suggestions": []}

    verified = load_verified_domains()
    oem_domains = load_oem_domains()

    # If already verified
    host = _normalize_domain(domain)
    if host and host in [d.lower() for d in verified.get(brand, [])]:
        return {"ok": True, "verified": True, "domain": host, "reason": "already_verified"}

    # First attempt: verify user-provided domain
    if host:
        ok, reason = _verify_domain(brand, host)
        if ok:
            arr = verified.get(brand, [])
            if host not in arr:
                arr.append(host)
            verified[brand] = arr
            save_verified_domains(verified)
            return {"ok": True, "verified": True, "domain": host, "reason": "verified"}

    # Suggest domains with bounded attempts
    max_queries = int(os.getenv("OEM_VERIFY_MAX_QUERIES", "3"))
    max_results = int(os.getenv("OEM_VERIFY_MAX_RESULTS", "5"))
    max_candidates = int(os.getenv("OEM_VERIFY_MAX_CANDIDATES", "8"))
    max_attempts = int(os.getenv("OEM_VERIFY_MAX_ATTEMPTS", "4"))

    queries = [
        f"{brand} official website",
        f"{brand} warranty support",
        f"{brand} manual warranty site",
        f"{brand} {region} official website" if region else "",
    ]
    queries = [q for q in queries if q][:max_queries]

    candidates: Dict[str, int] = {}
    for q in queries:
        results = search_web(q, count=max_results)
        for item in results:
            url = item.get("url") or ""
            host = _normalize_domain(url)
            if not host:
                continue
            candidates[host] = max(candidates.get(host, 0), _score_candidate(host, brand, region, oem_domains))

    ranked = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:max_candidates]

    attempts = 0
    for host, _score in ranked:
        if attempts >= max_attempts:
            break
        attempts += 1
        ok, reason = _verify_domain(brand, host)
        if ok:
            arr = verified.get(brand, [])
            if host not in arr:
                arr.append(host)
            verified[brand] = arr
            save_verified_domains(verified)
            return {"ok": True, "verified": True, "domain": host, "reason": "verified_from_search"}

    return {
        "ok": True,
        "verified": False,
        "reason": "not_verified",
        "suggestions": [h for h, _ in ranked],
    }
