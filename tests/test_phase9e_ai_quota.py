import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_quota


def test_ai_quota_consumes_daily_units(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUOTA_ENABLED", "1")
    monkeypatch.setenv("AI_DAILY_QUOTA_PER_USER", "2")
    monkeypatch.setenv("AI_QUOTA_FILE", str(tmp_path / "ai_quota.json"))

    first = ai_quota.check_and_consume("quota_user", feature="summary")
    second = ai_quota.check_and_consume("quota_user", feature="agent")

    assert first["remaining"] == 1
    assert second["remaining"] == 0
    usage = ai_quota.usage_for("quota_user")
    assert usage["used"] == 2
    assert usage["features"] == {"agent": 1, "summary": 1}


def test_ai_quota_blocks_when_daily_limit_exceeded(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUOTA_ENABLED", "1")
    monkeypatch.setenv("AI_DAILY_QUOTA_PER_USER", "1")
    monkeypatch.setenv("AI_QUOTA_FILE", str(tmp_path / "ai_quota.json"))

    ai_quota.check_and_consume("quota_user", feature="summary")

    with pytest.raises(HTTPException) as exc:
        ai_quota.check_and_consume("quota_user", feature="summary")

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "ai_quota_exceeded"


def test_ai_quota_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUOTA_ENABLED", "0")
    monkeypatch.setenv("AI_DAILY_QUOTA_PER_USER", "1")
    monkeypatch.setenv("AI_QUOTA_FILE", str(tmp_path / "ai_quota.json"))

    ai_quota.check_and_consume("quota_user")
    ai_quota.check_and_consume("quota_user")

    assert ai_quota.usage_for("quota_user")["enabled"] is False


def test_llm_route_enforces_ai_quota_before_generation(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("AI_QUOTA_ENABLED", "1")
    monkeypatch.setenv("AI_DAILY_QUOTA_PER_USER", "1")
    monkeypatch.setenv("AI_QUOTA_FILE", str(tmp_path / "ai_quota.json"))
    monkeypatch.setattr("app.main.generate_text", lambda prompt, model=None: ("ok", None))
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/llm/generate", json={"prompt": "hello"}, headers=headers)
    second = client.post("/llm/generate", json={"prompt": "hello again"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["error"] == "ai_quota_exceeded"


def test_ai_usage_endpoint_reports_current_user(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("AI_QUOTA_ENABLED", "1")
    monkeypatch.setenv("AI_DAILY_QUOTA_PER_USER", "3")
    monkeypatch.setenv("AI_QUOTA_FILE", str(tmp_path / "ai_quota.json"))
    ai_quota.check_and_consume("admin", feature="summary")
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    token = login.json()["access_token"]

    resp = client.get("/ai/usage", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["used"] == 1
    assert resp.json()["remaining"] == 2
