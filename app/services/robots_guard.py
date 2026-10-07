"""robots.txt check before SWH reads any web page: brand pages for warranty terms (terms source order, step 1),
the review crawler and issue feeds. Search-provider APIs (web_search.py) are API calls, not page reads.

- 200: the file's rules decide, for our user agent.
- 404 / 410: no robots file - allowed (the usual convention).
- 401 / 403, server errors, timeouts or no network: NOT allowed (we could not see the rules).
Results are cached per host for 24 hours. Only robots.txt is fetched here; the page itself is read by the
caller only when this returns True.
"""
from __future__ import annotations

import time
import urllib.robotparser
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

USER_AGENT = "SmartWarrantyHub"
_TTL_SEC = 24 * 3600
_CACHE: Dict[str, Tuple[float, Optional[urllib.robotparser.RobotFileParser], str]] = {}


def _load(origin: str) -> Tuple[Optional[urllib.robotparser.RobotFileParser], str]:
    try:
        resp = requests.get(f"{origin}/robots.txt", timeout=8, headers={"User-Agent": f"{USER_AGENT}/1.0"})
    except Exception as exc:
        return None, f"robots.txt not readable ({exc.__class__.__name__})"
    if resp.status_code in (404, 410):
        return urllib.robotparser.RobotFileParser(), "no robots.txt"
    if resp.status_code != 200:
        return None, f"robots.txt answered {resp.status_code}"
    parser = urllib.robotparser.RobotFileParser()
    parser.parse((resp.text or "").splitlines())
    return parser, "robots.txt read"


def check(url: Optional[str], user_agent: str = USER_AGENT) -> Tuple[bool, str]:
    """(allowed, reason) for reading ``url`` as ``user_agent`` (rules for "*" apply when none name it)."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "not a web address"
    origin = f"{parsed.scheme}://{parsed.netloc}"
    cached = _CACHE.get(origin)
    if not cached or time.time() - cached[0] > _TTL_SEC:
        parser, reason = _load(origin)
        cached = (time.time(), parser, reason)
        _CACHE[origin] = cached
    _ts, parser, reason = cached
    if parser is None:
        return False, reason
    if reason == "no robots.txt":
        return True, reason
    allowed = parser.can_fetch(user_agent or USER_AGENT, url)
    return allowed, "allowed by robots.txt" if allowed else "disallowed by robots.txt"


class RobotsDisallowed(requests.exceptions.RequestException):
    """Raised instead of fetching a page robots.txt does not allow (callers already handle RequestException)."""


def guarded_get(url: str, **kwargs):
    """requests.get, but only where robots.txt allows; otherwise RobotsDisallowed."""
    ok, reason = check(url)
    if not ok:
        raise RobotsDisallowed(reason)
    return requests.get(url, **kwargs)


def site_answered(url: Optional[str]) -> bool:
    """True when the site answered the robots.txt request at all (any HTTP status) - proof it is alive."""
    _ok, reason = check(url)
    return reason in ("no robots.txt", "robots.txt read", "allowed by robots.txt", "disallowed by robots.txt") \
        or reason.startswith("robots.txt answered")


def allowed(url: Optional[str]) -> bool:
    return check(url)[0]


def reset_cache() -> None:
    _CACHE.clear()
