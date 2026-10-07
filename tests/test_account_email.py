"""Sign-up requires a valid e-mail; signed-in users without one see a banner and can add it in account settings."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB
from app.deps import hash_password
from app.main import app
from app.services import rate_limiter

_n = itertools.count(1)


@pytest.fixture(autouse=True)
def _open_signup(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("PUBLIC_SIGNUP_ENABLED", "1")
    rate_limiter.reset_rate_limits()


def _user(email=None, password="pass-123"):
    username = f"acct_email_{next(_n)}"
    with SessionLocal() as db:
        db.query(UserDB).filter_by(username=username).delete()
        db.add(UserDB(username=username, role="user", hashed_password=hash_password(password), email=email))
        db.commit()
    resp = TestClient(app).post("/auth/login", data={"username": username, "password": password},
                                headers={"accept": "application/json"})
    return username, {"authorization": f"Bearer {resp.json()['access_token']}"}


def _stored_email(username):
    with SessionLocal() as db:
        return db.query(UserDB).filter_by(username=username).first().email


@pytest.mark.parametrize("email", ["", "   ", "not-an-email", "a@b", "two@@example.com", "x@example.com\nBcc: y@z.com"])
def test_signup_form_refuses_missing_or_invalid_email(email):
    username = f"signup_bad_{next(_n)}"
    resp = TestClient(app, follow_redirects=False).post(
        "/auth/signup/form", data={"username": username, "password": "pass-123", "email": email}
    )
    assert resp.status_code == 303 and "signup=email_invalid" in resp.headers["location"]
    with SessionLocal() as db:
        assert db.query(UserDB).filter_by(username=username).first() is None


def test_signup_form_with_email_creates_the_account():
    username = f"signup_ok_{next(_n)}"
    resp = TestClient(app, follow_redirects=False).post(
        "/auth/signup/form", data={"username": username, "password": "pass-123", "email": " New.Person@Example.com "}
    )
    assert resp.status_code == 303 and "signup=" not in resp.headers["location"]
    assert _stored_email(username) == "New.Person@Example.com"


def test_signup_api_requires_email():
    resp = TestClient(app).post("/auth/signup", json={"username": f"api_{next(_n)}", "password": "pass-123"})
    assert resp.status_code == 400 and "email" in resp.json()["detail"]


def test_sign_up_page_asks_for_email():
    html = TestClient(app).get("/login").text
    assert 'id="signupEmail" name="email" type="email"' in html and "Email (optional)" not in html
    assert "email_invalid" in html


def test_session_reports_whether_an_email_is_set():
    _u, without = _user(email=None)
    _u, with_email = _user(email="has@example.com")
    assert TestClient(app).get("/auth/session", headers=without).json()["has_email"] is False
    assert TestClient(app).get("/auth/session", headers=with_email).json()["has_email"] is True


def test_dashboard_has_banner_and_account_settings_form():
    _u, headers = _user(email=None)
    html = TestClient(app).get("/ui/neo-dashboard", headers=headers).text
    assert "Add your email so you can reset your password later" in html
    assert 'id="accountPanel"' in html and 'id="accountEmailForm"' in html and 'id="accountBtn"' in html


def test_add_email_without_password_when_none_is_set():
    username, headers = _user(email=None)
    assert TestClient(app).get("/account/email", headers=headers).json() == {"email": None}
    bad = TestClient(app).post("/account/email", json={"email": "nope"}, headers=headers)
    assert bad.status_code == 400
    ok = TestClient(app).post("/account/email", json={"email": "added@example.com"}, headers=headers)
    assert ok.status_code == 200 and _stored_email(username) == "added@example.com"
    assert TestClient(app).get("/auth/session", headers=headers).json()["has_email"] is True


def test_changing_an_existing_email_needs_the_current_password():
    username, headers = _user(email="first@example.com")
    resp = TestClient(app).post("/account/email", json={"email": "second@example.com"}, headers=headers)
    assert resp.status_code == 400 and _stored_email(username) == "first@example.com"
    resp = TestClient(app).post("/account/email", json={"email": "second@example.com", "current_password": "wrong"}, headers=headers)
    assert resp.status_code == 400
    resp = TestClient(app).post("/account/email", json={"email": "second@example.com", "current_password": "pass-123"}, headers=headers)
    assert resp.status_code == 200 and _stored_email(username) == "second@example.com"


def test_account_email_needs_sign_in():
    assert TestClient(app).post("/account/email", json={"email": "x@example.com"}).status_code == 401
    assert TestClient(app).get("/account/email").status_code == 401
