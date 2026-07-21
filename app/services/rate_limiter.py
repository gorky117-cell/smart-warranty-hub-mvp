import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class RateLimit:
    max_requests: int
    window_seconds: int


_LOCK = threading.Lock()
_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)


DEFAULT_LIMITS: dict[str, RateLimit] = {
    "login": RateLimit(10, 10 * 60),
    "upload": RateLimit(20, 60 * 60),
    "ai": RateLimit(30, 60 * 60),
    "agent": RateLimit(20, 60 * 60),
}


def _env_truthy(name: str, default: str = "1") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    value = (os.getenv(name) or "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def limit_for(scope: str) -> RateLimit:
    base = DEFAULT_LIMITS[scope]
    prefix = f"RATE_LIMIT_{scope.upper()}"
    return RateLimit(
        max_requests=_env_int(f"{prefix}_MAX", base.max_requests),
        window_seconds=_env_int(f"{prefix}_WINDOW_SEC", base.window_seconds),
    )


def client_key(request: Request, user_id: str | None = None) -> str:
    if user_id:
        return f"user:{user_id}"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def check_rate_limit(scope: str, request: Request, user_id: str | None = None) -> None:
    if not _env_truthy("RATE_LIMIT_ENABLED", "1"):
        return
    limit = limit_for(scope)
    now = time.monotonic()
    cutoff = now - limit.window_seconds
    bucket_key = f"{scope}:{client_key(request, user_id)}"
    with _LOCK:
        bucket = _BUCKETS[bucket_key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit.max_requests:
            retry_after = max(1, int(limit.window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    with _LOCK:
        _BUCKETS.clear()
