from fastapi.testclient import TestClient

from app.main import app
from app.services.request_context import REQUEST_ID_HEADER


def test_response_includes_generated_request_id(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)

    resp = client.get("/health/full")

    assert resp.status_code in (200, 503)
    request_id = resp.headers.get(REQUEST_ID_HEADER)
    assert request_id
    assert request_id.startswith("req_")


def test_response_reuses_supplied_request_id(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)

    resp = client.get("/health/full", headers={REQUEST_ID_HEADER: "phase9d-test-id"})

    assert resp.headers.get(REQUEST_ID_HEADER) == "phase9d-test-id"


def test_csrf_rejection_includes_request_id(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )
    assert login.status_code == 200

    resp = client.post("/auth/logout", headers={REQUEST_ID_HEADER: "csrf-missing-test"})

    assert resp.status_code == 403
    assert resp.headers.get(REQUEST_ID_HEADER) == "csrf-missing-test"


def test_request_log_does_not_include_body_or_authorization(monkeypatch, caplog):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    caplog.set_level("INFO", logger="swh.request")

    resp = client.get(
        "/health/full",
        headers={
            REQUEST_ID_HEADER: "body-redaction-test",
            "Authorization": "Bearer sensitive-token",
        },
    )

    assert resp.headers.get(REQUEST_ID_HEADER) == "body-redaction-test"
    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "body-redaction-test" in logs
    assert "sensitive-token" not in logs
    assert "Authorization" not in logs
