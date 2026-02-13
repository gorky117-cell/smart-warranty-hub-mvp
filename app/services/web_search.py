from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests


def _get_with_retry(url: str, *, headers=None, params=None, timeout: int = 6, retries: int = 2):
    last = None
    for _ in range(max(retries, 1)):
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            last = exc
    if last:
        raise last
    return None


def _post_with_retry(url: str, *, headers=None, json_body=None, timeout: int = 6, retries: int = 2):
    last = None
    for _ in range(max(retries, 1)):
        try:
            return requests.post(url, headers=headers, json=json_body, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            last = exc
    if last:
        raise last
    return None


def _bing_endpoint() -> str:
    return os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")

def _brave_endpoint() -> str:
    return os.getenv("BRAVE_SEARCH_ENDPOINT", "https://api.search.brave.com/res/v1/web/search")

def _google_endpoint() -> str:
    return os.getenv("GOOGLE_CSE_ENDPOINT", "https://www.googleapis.com/customsearch/v1")

def _serper_endpoint() -> str:
    return os.getenv("SERPER_ENDPOINT", "https://google.serper.dev/search")

def _serpapi_endpoint() -> str:
    return os.getenv("SERPAPI_ENDPOINT", "https://serpapi.com/search.json")


def _quota_path() -> Path:
    return Path(os.getenv("SEARCH_QUOTA_FILE", "data/search_quota.json"))


def _load_quota() -> dict:
    path = _quota_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_quota(data: dict) -> None:
    path = _quota_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(str(val).strip())
    except Exception:
        return default


def _provider_configured(provider: str) -> bool:
    provider = (provider or "").strip().lower()
    if provider == "brave":
        return bool(os.getenv("BRAVE_SEARCH_KEY"))
    if provider == "serper":
        return bool(os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY"))
    if provider == "serpapi":
        return bool(os.getenv("SERPAPI_KEY"))
    if provider == "google":
        return bool(os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_CX"))
    if provider == "bing":
        return bool(os.getenv("BING_SEARCH_KEY"))
    return False


def _quota_allow(provider: str) -> bool:
    provider = (provider or "").strip().lower()
    daily_limit_global = _env_int("SEARCH_DAILY_LIMIT", 0)
    monthly_limit_global = _env_int("SEARCH_MONTHLY_LIMIT", 0)
    daily_limit = _env_int(f"SEARCH_DAILY_LIMIT_{provider.upper()}", daily_limit_global)
    monthly_limit = _env_int(f"SEARCH_MONTHLY_LIMIT_{provider.upper()}", monthly_limit_global)
    if daily_limit <= 0 and monthly_limit <= 0:
        return True
    now = datetime.utcnow()
    day_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")
    data = _load_quota()
    p = data.setdefault(provider, {})
    day_count = int(p.get(day_key, 0))
    month_count = int(p.get(month_key, 0))
    if daily_limit > 0 and day_count >= daily_limit:
        return False
    if monthly_limit > 0 and month_count >= monthly_limit:
        return False
    # reserve one
    p[day_key] = day_count + 1
    p[month_key] = month_count + 1
    data[provider] = p
    _save_quota(data)
    return True

def bing_search(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
    """
    Run a Bing Web Search query and return raw result items.
    Requires BING_SEARCH_KEY env var.
    """
    key = os.getenv("BING_SEARCH_KEY")
    if not key:
        return []
    try:
        resp = _get_with_retry(
            _bing_endpoint(),
            headers={"Ocp-Apim-Subscription-Key": key},
            params={"q": query, "count": count, "textDecorations": False, "textFormat": "Raw"},
            timeout=timeout,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = (data.get("webPages") or {}).get("value") or []
    return items


def brave_search(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
    """
    Run a Brave Search API query and return normalized result items.
    Requires BRAVE_SEARCH_KEY env var.
    """
    key = os.getenv("BRAVE_SEARCH_KEY")
    if not key:
        return []
    try:
        resp = _get_with_retry(
            _brave_endpoint(),
            headers={
                "X-Subscription-Token": key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            params={"q": query, "count": count},
            timeout=timeout,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    results = (data.get("web") or {}).get("results") or []
    normalized = []
    for r in results:
        url = r.get("url")
        if url:
            normalized.append({"url": url, "title": r.get("title"), "description": r.get("description")})
    return normalized


def serper_search(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
    """
    Run Serper search query.
    Requires SERPER_API_KEY (or SERPER_KEY) env var.
    """
    key = os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY")
    if not key:
        return []
    try:
        resp = _post_with_retry(
            _serper_endpoint(),
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json_body={"q": query, "num": min(count, 10)},
            timeout=timeout,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = data.get("organic") or []
    normalized = []
    for r in items:
        url = r.get("link")
        if url:
            normalized.append({"url": url, "title": r.get("title"), "description": r.get("snippet")})
    return normalized


def google_search(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
    """
    Run a Google Programmable Search (Custom Search JSON API) query.
    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX env vars.
    """
    key = os.getenv("GOOGLE_CSE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_CX")
    if not key or not cx:
        return []
    try:
        resp = _get_with_retry(
            _google_endpoint(),
            params={"q": query, "key": key, "cx": cx, "num": min(count, 10)},
            timeout=timeout,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = data.get("items") or []
    normalized = []
    for r in items:
        url = r.get("link")
        if url:
            normalized.append({"url": url, "title": r.get("title"), "description": r.get("snippet")})
    return normalized


def serpapi_search(query: str, count: int = 5, timeout: int = 6) -> List[Dict]:
    """
    Run SerpAPI search query.
    Requires SERPAPI_KEY env var.
    """
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return []
    try:
        resp = _get_with_retry(
            _serpapi_endpoint(),
            params={"q": query, "api_key": key, "num": min(count, 10)},
            timeout=timeout,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = data.get("organic_results") or []
    normalized = []
    for r in items:
        url = r.get("link")
        if url:
            normalized.append({"url": url, "title": r.get("title"), "description": r.get("snippet")})
    return normalized


def _try_provider(provider: str, query: str, count: int, timeout: int) -> List[Dict]:
    if provider == "brave":
        return brave_search(query, count=count, timeout=timeout)
    if provider == "serper":
        return serper_search(query, count=count, timeout=timeout)
    if provider == "serpapi":
        return serpapi_search(query, count=count, timeout=timeout)
    if provider == "google":
        return google_search(query, count=count, timeout=timeout)
    if provider == "bing":
        return bing_search(query, count=count, timeout=timeout)
    return []


def search_web(query: str, count: int = 5, timeout: int = 6, provider: Optional[str] = None) -> List[Dict]:
    """
    Provider can be 'serper', 'serpapi', 'brave', 'google', 'bing', or 'auto'.
    Auto prefers Serper, then SerpAPI, then Brave, then Google, then Bing.
    You can override order via TERMS_SEARCH_AUTO_ORDER, example:
      TERMS_SEARCH_AUTO_ORDER=serper,brave,google,serpapi,bing
    """
    provider = (provider or os.getenv("TERMS_SEARCH_PROVIDER", "auto")).strip().lower()
    # explicit provider
    if provider in ("serper", "serpapi", "brave", "google", "bing"):
        if not _provider_configured(provider):
            return []
        if not _quota_allow(provider):
            return []
        return _try_provider(provider, query, count, timeout)

    # auto fallback order: serper -> serpapi -> brave -> google -> bing
    default_order = ["serper", "serpapi", "brave", "google", "bing"]
    raw_order = (os.getenv("TERMS_SEARCH_AUTO_ORDER", "") or "").strip().lower()
    providers: List[str] = []
    if raw_order:
        seen = set()
        for p in [x.strip() for x in raw_order.split(",") if x.strip()]:
            if p in default_order and p not in seen:
                seen.add(p)
                providers.append(p)
        for p in default_order:
            if p not in seen:
                providers.append(p)
    else:
        providers = default_order

    for p in providers:
        if not _provider_configured(p):
            continue
        if not _quota_allow(p):
            continue
        results = _try_provider(p, query, count, timeout)
        if results:
            return results
    return []
