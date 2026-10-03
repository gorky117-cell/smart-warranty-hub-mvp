"""Insecure-settings warnings and the HTTPS redirect (fix run B4)."""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import security_status


def _codes(report):
    return {w["code"] for w in report["warnings"]}


def test_allow_insecure_defaults_is_critical_and_values_never_returned(monkeypatch):
    secret_value = "s3cr3t-value-that-must-not-leak"
    monkeypatch.setenv("ALLOW_INSECURE_DEFAULTS", "true")
    monkeypatch.setenv("JWT_SECRET", secret_value)
    monkeypatch.setenv("ADMIN_PASS", "short-pw-9")
    monkeypatch.setenv("ADMIN_USER", "admin")
    report = security_status.security_report()
    assert "allow_insecure_defaults" in _codes(report)
    assert {"jwt_secret_weak", "admin_password_weak"} <= _codes(report)
    assert report["critical"] >= 1
    dumped = json.dumps(report)
    assert secret_value not in dumped
    assert "short-pw-9" not in dumped and "admin123" not in dumped


def test_weak_cookie_and_https_settings_in_production(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_INSECURE_DEFAULTS", "false")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("FORCE_HTTPS_REDIRECT", "0")
    monkeypatch.setenv("ALLOWED_HOSTS", "")
    codes = _codes(security_status.security_report())
    assert {"cookie_not_secure", "cookie_samesite_none", "https_redirect_off", "allowed_hosts_empty"} <= codes
    assert "allow_insecure_defaults" not in codes


def test_strong_settings_produce_no_warnings(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    for name, value in {
        "ALLOW_INSECURE_DEFAULTS": "false", "JWT_SECRET": "x" * 48, "JWT_SALT": "y" * 16, "ADMIN_USER": "ops",
        "ADMIN_PASS": "a-long-unique-passphrase", "COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax",
        "FORCE_HTTPS_REDIRECT": "1", "ALLOWED_HOSTS": "example.app", "RATE_LIMIT_ENABLED": "1",
    }.items():
        monkeypatch.setenv(name, value)
    assert security_status.security_report()["warnings"] == []


def test_https_redirect_only_on_explicit_forwarded_http(monkeypatch):
    monkeypatch.setenv("FORCE_HTTPS_REDIRECT", "1")
    assert security_status.https_redirect_target("http", "swh.example", "/ui?x=1") == "https://swh.example/ui?x=1"
    assert security_status.https_redirect_target("https", "swh.example", "/") is None
    assert security_status.https_redirect_target(None, "swh.example", "/health/full") is None  # internal checks
    monkeypatch.setenv("FORCE_HTTPS_REDIRECT", "0")
    assert security_status.https_redirect_target("http", "swh.example", "/") is None


def test_redirect_middleware_and_admin_only_endpoint(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("FORCE_HTTPS_REDIRECT", "1")
    resp = client.get("/api/health", headers={"x-forwarded-proto": "http"}, follow_redirects=False)
    assert resp.status_code == 308 and resp.headers["location"].startswith("https://")
    assert client.get("/api/health").status_code == 200
    monkeypatch.delenv("FORCE_HTTPS_REDIRECT")

    assert client.get("/admin/security-status").status_code in (401, 403)
    login = client.post("/auth/login", data={"username": "admin", "password": "admin123"}, headers={"accept": "application/json"})
    token = login.json()["access_token"]
    resp = client.get("/admin/security-status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "default_admin_password" in {w["code"] for w in resp.json()["warnings"]}
