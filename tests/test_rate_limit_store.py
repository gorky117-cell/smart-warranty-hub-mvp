"""Rate limits survive deploys (backlog #21): hits are kept in the database, hashed, with a memory fallback."""
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.db import SessionLocal
from app.db_models import RateLimitHitDB
from app.services import rate_limiter


def _request(ip="192.0.2.77"):
    return Request({"type": "http", "method": "POST", "path": "/t", "headers": [(b"x-forwarded-for", ip.encode())],
                    "client": ("10.0.0.1", 1), "server": ("testserver", 80), "scheme": "http"})


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_SEC", "60")
    rate_limiter.reset_rate_limits()
    yield
    rate_limiter.reset_rate_limits()


def _simulate_restart():
    rate_limiter._BUCKETS.clear()  # a new process starts with empty memory


def test_limit_survives_a_restart():
    req = _request()
    rate_limiter.check_rate_limit("login", req)
    _simulate_restart()
    rate_limiter.check_rate_limit("login", req)
    _simulate_restart()
    with pytest.raises(HTTPException) as exc:
        rate_limiter.check_rate_limit("login", req)
    assert exc.value.status_code == 429 and 1 <= int(exc.value.headers["Retry-After"]) <= 60


def test_window_slides_and_old_hits_do_not_count():
    req = _request("192.0.2.78")
    with SessionLocal() as db:
        bucket = rate_limiter._hashed("login:ip:192.0.2.78")
        db.add_all([RateLimitHitDB(bucket=bucket, ts=time.time() - 120) for _ in range(5)])
        db.commit()
    rate_limiter.check_rate_limit("login", req)
    rate_limiter.check_rate_limit("login", req)
    with pytest.raises(HTTPException):
        rate_limiter.check_rate_limit("login", req)


def test_no_ip_or_name_is_stored():
    rate_limiter.check_rate_limit("login", _request("192.0.2.79"))
    rate_limiter.check_rate_limit("password_reset_account", _request(), "acct-user-name")
    with SessionLocal() as db:
        buckets = [row.bucket for row in db.query(RateLimitHitDB).all()]
    assert len(buckets) == 2
    for bucket in buckets:
        assert len(bucket) == 64 and "192.0.2" not in bucket and "user" not in bucket


def test_falls_back_to_memory_when_the_database_fails(monkeypatch):
    import app.db as db_module

    def broken():
        raise RuntimeError("database down")

    monkeypatch.setattr(db_module, "SessionLocal", broken)
    req = _request("192.0.2.80")
    rate_limiter.check_rate_limit("login", req)
    rate_limiter.check_rate_limit("login", req)
    with pytest.raises(HTTPException):
        rate_limiter.check_rate_limit("login", req)


def test_memory_backend_can_be_chosen(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    req = _request("192.0.2.81")
    rate_limiter.check_rate_limit("login", req)
    with SessionLocal() as db:
        assert db.query(RateLimitHitDB).count() == 0
    _simulate_restart()  # memory only: a restart forgets
    rate_limiter.check_rate_limit("login", req)
    rate_limiter.check_rate_limit("login", req)
