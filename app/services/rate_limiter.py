"""Sliding-window rate limits.

Hits are stored in the database (table rate_limit_hits) by default, so limits survive deploys and are shared
by every app instance. RATE_LIMIT_BACKEND=memory keeps them in this process only (the old behaviour). If the
database cannot be used, the in-memory limiter takes over for that request; a limit never crashes a request.
Bucket keys are stored as SHA-256 hashes: no IP addresses, usernames or e-mail addresses in the table.
"""
import hashlib
import logging
import os
import random
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


logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
# Rows older than this are deleted now and then (longer than any configured window is kept).
_KEEP_SECONDS = 2 * 24 * 3600
_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)


DEFAULT_LIMITS: dict[str, RateLimit] = {
    "login": RateLimit(10, 10 * 60),
    # Sign-up skips the cookie-session CSRF check (consolidated run P2.6), so it is always rate limited.
    "signup": RateLimit(5, 60 * 60),
    "upload": RateLimit(20, 60 * 60),
    "ai": RateLimit(30, 60 * 60),
    "agent": RateLimit(20, 60 * 60),
    # Forgot password: requests per client, reset e-mails per account (keyed by a hash of the address),
    # and link checks / new-password submissions per client.
    "password_reset_request": RateLimit(5, 15 * 60),
    "password_reset_account": RateLimit(3, 60 * 60),
    "password_reset_submit": RateLimit(10, 15 * 60),
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


def _backend() -> str:
    return (os.getenv("RATE_LIMIT_BACKEND") or "db").strip().lower()


def _too_many(limit: RateLimit, oldest: float, now: float) -> HTTPException:
    retry_after = max(1, int(limit.window_seconds - (now - oldest)))
    return HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Please retry later.",
        headers={"Retry-After": str(retry_after)},
    )


def _check_memory(bucket_key: str, limit: RateLimit) -> None:
    now = time.time()
    cutoff = now - limit.window_seconds
    with _LOCK:
        bucket = _BUCKETS[bucket_key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit.max_requests:
            raise _too_many(limit, bucket[0], now)
        bucket.append(now)


def _hashed(bucket_key: str) -> str:
    return hashlib.sha256(bucket_key.encode("utf-8")).hexdigest()


def _check_db(bucket_key: str, limit: RateLimit) -> None:
    from sqlalchemy import func

    from ..db import SessionLocal
    from ..db_models import RateLimitHitDB

    now = time.time()
    cutoff = now - limit.window_seconds
    bucket = _hashed(bucket_key)
    with SessionLocal() as db:
        count, oldest = (
            db.query(func.count(RateLimitHitDB.id), func.min(RateLimitHitDB.ts))
            .filter(RateLimitHitDB.bucket == bucket, RateLimitHitDB.ts > cutoff)
            .one()
        )
        if count >= limit.max_requests:
            raise _too_many(limit, float(oldest), now)
        db.add(RateLimitHitDB(bucket=bucket, ts=now))
        if random.random() < 0.02:
            db.query(RateLimitHitDB).filter(RateLimitHitDB.ts < now - _KEEP_SECONDS).delete(synchronize_session=False)
        db.commit()


def check_rate_limit(scope: str, request: Request, user_id: str | None = None) -> None:
    if not _env_truthy("RATE_LIMIT_ENABLED", "1"):
        return
    limit = limit_for(scope)
    bucket_key = f"{scope}:{client_key(request, user_id)}"
    if _backend() != "memory":
        try:
            _check_db(bucket_key, limit)
            return
        except HTTPException:
            raise
        except Exception as exc:  # database unavailable: limit in memory for this request
            logger.warning("Rate limit store unavailable, using memory: %s", exc.__class__.__name__)
    _check_memory(bucket_key, limit)


def reset_rate_limits() -> None:
    """Forget every hit (tests and admin use)."""
    with _LOCK:
        _BUCKETS.clear()
    try:
        from ..db import SessionLocal
        from ..db_models import RateLimitHitDB

        with SessionLocal() as db:
            db.query(RateLimitHitDB).delete(synchronize_session=False)
            db.commit()
    except Exception:
        pass
