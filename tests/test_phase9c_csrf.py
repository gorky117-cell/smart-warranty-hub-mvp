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


def test_stale_access_cookie_does_not_block_form_login(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", "stale")

    resp = client.post("/auth/login", data={"username": "admin", "password": "admin123"})

    assert resp.status_code == 303
    assert any(
        h.startswith("access_token=") and not h.startswith("access_token=stale")
        for h in resp.headers.get_list("set-cookie")
    )


def test_stale_access_cookie_does_not_block_failed_login_redirect(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", "stale")

    resp = client.post("/auth/login", data={"username": "x", "password": "y"})

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login?error=invalid")


def test_login_page_clears_stale_access_cookie():
    client = TestClient(app)
    client.cookies.set("access_token", "stale")

    resp = client.get("/login")

    assert resp.status_code == 200
    assert any(h.startswith("access_token=") and "Max-Age=0" in h for h in resp.headers.get_list("set-cookie"))


def test_login_page_keeps_valid_session(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    assert _login(client).status_code == 200

    resp = client.get("/login")

    assert resp.status_code == 200
    assert not any(h.startswith("access_token=") for h in resp.headers.get_list("set-cookie"))


# --- Consolidated run step 6: stale/expired session cookies on sign-in and sign-up -----------------


def _expired_token():
    from datetime import datetime, timedelta

    import jwt

    from app import deps

    payload = {"sub": "admin", "role": "admin", "exp": datetime.utcnow() - timedelta(hours=1)}
    return jwt.encode(payload, deps.SECRET_KEY, algorithm=deps.ALGORITHM)


def _cookie_headers(resp, name):
    return [h for h in resp.headers.get_list("set-cookie") if h.startswith(f"{name}=")]


def test_expired_cookie_does_not_block_form_login(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", _expired_token())
    resp = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 303 and not resp.headers["location"].startswith("/login")
    assert _cookie_headers(resp, "access_token") and _cookie_headers(resp, CSRF_COOKIE_NAME)


def test_login_page_replaces_expired_session_with_fresh_csrf_token():
    client = TestClient(app)
    client.cookies.set("access_token", _expired_token())
    client.cookies.set(CSRF_COOKIE_NAME, "old-token")
    resp = client.get("/login")
    assert resp.status_code == 200
    assert any("Max-Age=0" in h for h in _cookie_headers(resp, "access_token"))
    fresh = _cookie_headers(resp, CSRF_COOKIE_NAME)
    assert fresh and "Max-Age=0" not in fresh[0] and not fresh[0].startswith(f"{CSRF_COOKIE_NAME}=old-token")


def test_no_cookie_login_page_sets_nothing_and_login_works(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    resp = client.get("/login")
    assert resp.status_code == 200 and not resp.headers.get_list("set-cookie")
    assert client.post("/auth/login", data={"username": "admin", "password": "admin123"}).status_code == 303


def test_failed_login_with_stale_cookie_is_friendly_and_clears_it(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", "stale")
    resp = client.post("/auth/login", data={"username": "x", "password": "y"})
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login?error=invalid")
    assert any("Max-Age=0" in h for h in _cookie_headers(resp, "access_token"))


def test_signup_form_with_stale_cookie_is_not_blocked(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", "stale")
    resp = client.post("/auth/signup/form", data={"username": "ab", "password": "123"})
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login?")


def test_login_logout_login(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    assert client.post("/auth/login", data={"username": "admin", "password": "admin123"}).status_code == 303
    csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert client.post("/auth/logout", headers={"x-csrf-token": csrf}).status_code == 200
    resp = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 303 and _cookie_headers(resp, "access_token")


def test_csrf_still_enforced_elsewhere_and_browsers_get_a_friendly_redirect(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app, follow_redirects=False)
    assert _login(client).status_code == 200
    api = client.post("/auth/logout", headers={"accept": "application/json"})
    assert api.status_code == 403 and api.json()["detail"] == "CSRF token missing or invalid"
    page = client.post("/auth/logout", headers={"accept": "text/html,application/xhtml+xml"})
    assert page.status_code == 303 and page.headers["location"] == "/login?error=session_expired"
    assert client.get("/auth/session").json()["authenticated"] is True  # rejected request changed nothing
