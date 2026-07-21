import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services import rate_limiter


def _request(host: str = "203.0.113.10", forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": headers,
            "client": (host, 43210),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_rate_limit_blocks_after_configured_threshold(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_AI_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_AI_WINDOW_SEC", "60")
    rate_limiter.reset_rate_limits()

    req = _request()
    rate_limiter.check_rate_limit("ai", req, "phase9_user")
    rate_limiter.check_rate_limit("ai", req, "phase9_user")

    with pytest.raises(HTTPException) as exc:
        rate_limiter.check_rate_limit("ai", req, "phase9_user")

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"].isdigit()


def test_rate_limit_separates_authenticated_users(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_WINDOW_SEC", "60")
    rate_limiter.reset_rate_limits()

    req = _request()
    rate_limiter.check_rate_limit("upload", req, "user_a")
    rate_limiter.check_rate_limit("upload", req, "user_b")

    with pytest.raises(HTTPException):
        rate_limiter.check_rate_limit("upload", req, "user_a")


def test_rate_limit_uses_forwarded_ip_for_unauthenticated_login(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_SEC", "60")
    rate_limiter.reset_rate_limits()

    req = _request(forwarded_for="198.51.100.44, 10.0.0.1")
    rate_limiter.check_rate_limit("login", req)

    with pytest.raises(HTTPException):
        rate_limiter.check_rate_limit("login", req)


def test_rate_limit_can_be_disabled_for_controlled_local_runs(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("RATE_LIMIT_AGENT_MAX", "1")
    rate_limiter.reset_rate_limits()

    req = _request()
    rate_limiter.check_rate_limit("agent", req, "phase9_user")
    rate_limiter.check_rate_limit("agent", req, "phase9_user")
