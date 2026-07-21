from fastapi.testclient import TestClient

from app.main import app
from app.services.csrf import CSRF_COOKIE_NAME


def _login(client: TestClient):
    return client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"accept": "application/json"},
    )


def test_login_sets_csrf_cookie(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)

    resp = _login(client)

    assert resp.status_code == 200
    assert client.cookies.get(CSRF_COOKIE_NAME)


def test_cookie_authenticated_post_requires_csrf_header(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    assert _login(client).status_code == 200

    resp = client.post("/auth/logout")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF token missing or invalid"


def test_cookie_authenticated_post_accepts_matching_csrf_header(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    assert _login(client).status_code == 200
    csrf = client.cookies.get(CSRF_COOKIE_NAME)

    resp = client.post("/auth/logout", headers={"X-CSRF-Token": csrf})

    assert resp.status_code == 200
    assert resp.json()["status"] == "logged_out"


def test_bearer_authenticated_post_does_not_require_csrf_header(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    login = _login(client)
    token = login.json()["access_token"]

    sample_path = tmp_path / "invoice.txt"
    sample_path.write_text("Brand: Acmeco Model: ZX-100 Purchase date: 2025-01-01", encoding="utf-8")
    with sample_path.open("rb") as fh:
        resp = client.post(
            "/artifacts/upload",
            files={"file": ("invoice.txt", fh, "text/plain")},
            data={"type": "invoice"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json().get("job_id")
