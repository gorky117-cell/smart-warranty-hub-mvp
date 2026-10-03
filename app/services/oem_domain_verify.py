from __future__ import annotations

import os
import re
import socket
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .web_search import search_web
from .oem_domains import load_oem_domains, load_verified_domains, save_verified_domains




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


USER_AGENT = "SmartWarrantyHub/1.0 (warranty source verification)"
SUPPORT_PATHS = ("/support", "/warranty", "/support/warranty", "/in/support", "/in/support/warranty", "/service", "/in/service")
_TIMEOUT = 8


def _brand_key(brand: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+india$", "", (brand or "").strip().lower()))


def _same_brand_host(host: str, brand: str, domain: str, brand_domains: List[str]) -> bool:
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == domain or host.endswith("." + domain):
        return True
    if any(host == d or host.endswith("." + d) for d in brand_domains):
        return True
    key = _brand_key(brand)
    return bool(key) and len(key) >= 3 and key in re.sub(r"[^a-z0-9]", "", host)


def _head_text(html: str) -> str:
    """<title> plus brand-bearing meta tags only (never the page body)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    parts = [soup.title.get_text(" ", strip=True) if soup.title else ""]
    for meta in soup.find_all("meta"):
        key = (meta.get("property") or meta.get("name") or "").lower()
        if key in ("og:site_name", "og:title", "application-name", "apple-mobile-web-app-title", "twitter:site",
                   "twitter:title", "description", "og:description", "author", "copyright"):
            parts.append(meta.get("content") or "")
    return " ".join(parts)


def _brand_in(text: str, brand: str) -> bool:
    key = _brand_key(brand)
    return bool(key) and key in re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _get(url: str):
    return requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}, allow_redirects=True)


def verify_domain_detail(brand: str, domain: str) -> Dict[str, object]:
    """Verification steps for one brand/domain; nothing is saved here.

    1. registry mapping (domain listed for the brand, or the brand name in the host);
    2. DNS resolves; 3. HTTPS homepage answers (< 400, or 401/403/429 bot-blocking, then step 5 decides);
    4. every redirect stays on a same-brand host; 5. brand in <title>/metadata, or a reachable
    same-brand support/warranty page.
    """
    from .oem_domains import load_oem_domains, normalize_domain

    host = normalize_domain(domain)
    out: Dict[str, object] = {"brand": brand, "domain": host, "verified": False, "steps": {}}
    if not host:
        out["reason"] = "invalid_domain"
        return out
    registry = load_oem_domains()
    brand_domains = [normalize_domain(d) for d in registry.get(brand, [])]
    in_registry = host in brand_domains
    out["steps"]["registry"] = "listed" if in_registry else "brand_in_host" if _same_brand_host(host, brand, "", []) else "no"
    if out["steps"]["registry"] == "no":
        out["reason"] = "not_mapped_to_brand"
        return out
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        out["steps"]["dns"] = "ok"
    except OSError:
        out["steps"]["dns"] = "fail"
        out["reason"] = "dns_failed"
        return out
    try:
        resp = _get(f"https://{host}")
    except requests.exceptions.RequestException as exc:
        out["steps"]["https"] = exc.__class__.__name__
        out["reason"] = "https_failed"
        return out
    out["steps"]["https"] = resp.status_code
    chain = [urlparse(r.url).hostname or "" for r in list(resp.history) + [resp]]
    if not all(_same_brand_host(h, brand, host, brand_domains) for h in chain if h):
        out["steps"]["redirects"] = chain
        out["reason"] = "redirect_to_other_brand"
        return out
    out["steps"]["redirects"] = "same_brand"
    if resp.status_code < 400:
        try:
            from .warranty_parser import response_text

            if _brand_in(_head_text(response_text(resp)), brand):
                out["steps"]["brand_evidence"] = "title_or_metadata"
                out.update(verified=True, reason="verified")
                return out
        except Exception:
            pass
    elif resp.status_code not in (401, 403, 429):
        out["reason"] = f"https_status_{resp.status_code}"
        return out
    for path in SUPPORT_PATHS:
        try:
            page = _get(f"https://{host}{path}")
        except requests.exceptions.RequestException:
            continue
        final_host = urlparse(page.url).hostname or ""
        if page.status_code < 400 and _same_brand_host(final_host, brand, host, brand_domains):
            out["steps"]["brand_evidence"] = f"support_page:{path}"
            out.update(verified=True, reason="verified")
            return out
    out["reason"] = "no_brand_evidence"
    return out


def _verify_domain(brand: str, domain: str) -> Tuple[bool, str]:
    detail = verify_domain_detail(brand, domain)
    return bool(detail["verified"]), str(detail.get("reason"))


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
