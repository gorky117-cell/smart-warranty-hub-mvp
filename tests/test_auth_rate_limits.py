"""Sign-in and sign-up stay rate limited although they skip the cookie-session CSRF check (P2.6)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import rate_limiter


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_SIGNUP_MAX", "2")
    rate_limiter.reset_rate_limits()
    yield
    rate_limiter.reset_rate_limits()


def _client(ip):
    client = TestClient(app, follow_redirects=False)
    client.headers["x-forwarded-for"] = ip
    client.cookies.set("access_token", "stale")  # CSRF is skipped here; the limit must still apply
    return client


def test_login_form_is_limited_with_a_friendly_message(limited):
    client = _client("198.51.100.1")
    for _ in range(3):
        assert client.post("/auth/login", data={"username": "x", "password": "y"}).headers["location"].startswith("/login?error=invalid")
    resp = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login?error=rate_limited")


def test_login_api_is_limited_with_429(limited):
    client = _client("198.51.100.2")
    for _ in range(3):
        client.post("/auth/login", data={"username": "x", "password": "y"}, headers={"accept": "application/json"})
    resp = client.post("/auth/login", data={"username": "x", "password": "y"}, headers={"accept": "application/json"})
    assert resp.status_code == 429 and resp.headers["retry-after"]


def test_signup_form_is_limited_with_a_friendly_message(limited):
    client = _client("198.51.100.3")
    for _ in range(2):
        assert "signup=rate_limited" not in client.post("/auth/signup/form", data={"username": "ab", "password": "1"}).headers["location"]
    resp = client.post("/auth/signup/form", data={"username": "ab", "password": "1"})
    assert resp.status_code == 303 and "signup=rate_limited" in resp.headers["location"]


def test_signup_api_is_limited_with_429(limited):
    client = _client("198.51.100.4")
    payload = {"username": "ratelimit_probe", "password": "secret123", "role": "user"}
    for _ in range(2):
        assert client.post("/auth/signup", json=payload).status_code != 429
    assert client.post("/auth/signup", json=payload).status_code == 429


def test_limits_are_per_client(limited):
    for ip in ("198.51.100.5", "198.51.100.6"):
        client = _client(ip)
        resp = client.post("/auth/signup/form", data={"username": "ab", "password": "1"})
        assert "signup=rate_limited" not in resp.headers["location"]
