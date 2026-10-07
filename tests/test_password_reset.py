"""Forgot password: one-time hashed tokens, 30-minute expiry, same answer for unknown e-mails, rate limits,
every session signed out, no addresses or tokens in logs. The mail service (Resend HTTP API) is mocked."""
import itertools
import logging
import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import EmailDailyCountDB, PasswordResetTokenDB, UserDB, UserSessionCutoffDB
from app.deps import hash_password
from app.main import app
from app.services import emailer, password_reset, rate_limiter

_ips = itertools.count(1)
_users = itertools.count(1)


class _Response:
    status_code = 200


@pytest.fixture
def mail(monkeypatch):
    """Resend configured, its HTTP API mocked; returns the list of sent payloads."""
    for name in ("EMAIL_ENABLED", "EMAIL_PROVIDER", "SMTP_HOST", "MAIL_FROM", "MAIL_REPLY_TO"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    rate_limiter.reset_rate_limits()
    sent = []

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.append(json)
        return _Response()

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    _set_sent_today(0)
    yield sent
    rate_limiter.reset_rate_limits()
    _set_sent_today(0)


def _set_sent_today(n):
    emailer._MEMORY_COUNTS.clear()
    with SessionLocal() as db:
        db.query(EmailDailyCountDB).filter_by(day=emailer._utc_day()).delete()
        if n:
            db.add(EmailDailyCountDB(day=emailer._utc_day(), sent=n))
        db.commit()


def _client():
    client = TestClient(app, follow_redirects=False)
    client.headers["x-forwarded-for"] = f"203.0.113.{next(_ips)}"
    return client


def _user(password="old-pass-1"):
    n = next(_users)
    username, email = f"reset_user_{n}", f"Reset.User{n}@Example.com"
    with SessionLocal() as db:
        db.query(UserDB).filter_by(username=username).delete()
        db.query(UserSessionCutoffDB).filter_by(username=username).delete()
        db.query(PasswordResetTokenDB).filter_by(username=username).delete()
        db.add(UserDB(username=username, role="user", hashed_password=hash_password(password), email=email))
        db.commit()
    return username, email


def _token_from(mail_payload):
    match = re.search(r"/reset-password#token=([A-Za-z0-9_-]+)", mail_payload["text"])
    assert match, "reset link missing from the e-mail"
    return match.group(1)


def _sign_in(username, password):
    resp = _client().post("/auth/login", data={"username": username, "password": password}, headers={"accept": "application/json"})
    return resp.status_code, (resp.json().get("access_token") if resp.status_code == 200 else None)


def _session_ok(token):
    resp = TestClient(app).get("/auth/session", headers={"authorization": f"Bearer {token}"})
    return resp.json()["authenticated"]


def test_sign_in_page_links_to_forgot_password():
    html = TestClient(app).get("/login").text
    assert 'href="/forgot-password"' in html and "Forgot password?" in html


def test_normal_reset(mail):
    username, email = _user()
    client = _client()
    page = client.get("/forgot-password")
    assert page.status_code == 200 and 'data-email-ready="1"' in page.text and 'data-mode="forgot"' in page.text
    resp = client.post("/auth/password/forgot", data={"email": email.lower()})  # any letter case
    assert resp.status_code == 303 and resp.headers["location"] == "/forgot-password?sent=1"
    assert len(mail) == 1
    message = mail[0]
    assert message["to"] == [email]
    assert message["from"] == "Smart Warranty Hub <noreply@smartwarrantyhub.com>"
    assert message["reply_to"] == "support@smartwarrantyhub.com"
    assert {"name": "app", "value": "swh"} in message["tags"] and {"name": "type", "value": "password_reset"} in message["tags"]
    for words in ("30 minutes", "only once", "If this wasn't you, ignore this email", username):
        assert words in message["text"] and words in message["html"]
    token = _token_from(message)
    assert f"#token={token}" in message["html"]

    assert client.post("/auth/password/reset/check", json={"token": token}).json() == {"status": "ok"}
    resp = client.post("/auth/password/reset", json={"token": token, "password": "new-pass-2", "confirm": "new-pass-2"})
    assert resp.json() == {"status": "ok"}
    assert resp.headers["cache-control"] == "no-store"
    assert _sign_in(username, "old-pass-1")[0] == 401
    assert _sign_in(username, "new-pass-2")[0] == 200


def test_token_is_stored_hashed_only(mail):
    username, email = _user()
    _client().post("/auth/password/forgot", data={"email": email})
    token = _token_from(mail[-1])
    with SessionLocal() as db:
        rows = db.query(PasswordResetTokenDB).filter_by(username=username).all()
    assert len(rows) == 1 and rows[0].token_hash != token and token not in rows[0].token_hash
    assert rows[0].expires_at - rows[0].created_at == timedelta(minutes=30)


def test_expired_link(mail):
    username, _email = _user()
    with SessionLocal() as db:
        token = password_reset.issue_token(db, username, now=datetime.utcnow() - timedelta(minutes=31))
    client = _client()
    assert client.post("/auth/password/reset/check", json={"token": token}).json() == {"status": "expired"}
    assert client.post("/auth/password/reset", json={"token": token, "password": "new-pass-2"}).json() == {"status": "expired"}
    assert _sign_in(username, "old-pass-1")[0] == 200  # password unchanged
    # The page explains it in plain words and offers a new link.
    page = client.get("/reset-password").text
    assert "This link has expired" in page and 'href="/forgot-password"' in page
    # Still valid one second before the 30 minutes are up.
    with SessionLocal() as db:
        fresh = password_reset.issue_token(db, username, now=datetime.utcnow() - timedelta(minutes=29, seconds=59))
        assert password_reset.check_token(db, fresh)[0] == "ok"


def test_reused_link_and_older_links_die(mail):
    username, email = _user()
    client = _client()
    client.post("/auth/password/forgot", data={"email": email})
    first = _token_from(mail[-1])
    client.post("/auth/password/forgot", data={"email": email})
    second = _token_from(mail[-1])
    assert first != second
    # Asking again retired the first link.
    assert client.post("/auth/password/reset/check", json={"token": first}).json() == {"status": "used"}
    assert client.post("/auth/password/reset", json={"token": first, "password": "new-pass-2"}).json() == {"status": "used"}
    assert client.post("/auth/password/reset", json={"token": second, "password": "new-pass-2"}).json() == {"status": "ok"}
    # The link works once.
    assert client.post("/auth/password/reset", json={"token": second, "password": "other-pass-3"}).json() == {"status": "used"}
    assert _sign_in(username, "new-pass-2")[0] == 200
    assert _sign_in(username, "other-pass-3")[0] == 401
    page = client.get("/reset-password").text
    assert "This link was already used" in page
    assert client.post("/auth/password/reset/check", json={"token": "made-up"}).json() == {"status": "invalid"}


def test_unknown_email_gets_the_same_answer(mail):
    _username, email = _user()
    known = _client().post("/auth/password/forgot", data={"email": email})
    sent_for_known = len(mail)
    unknown = _client().post("/auth/password/forgot", data={"email": "nobody-here@example.com"})
    assert unknown.status_code == known.status_code == 303
    assert unknown.headers["location"] == known.headers["location"] == "/forgot-password?sent=1"
    assert len(mail) == sent_for_known  # nothing sent for the unknown address
    sent_page = _client().get("/forgot-password?sent=1").text
    assert "If an account uses that email address" in sent_page


def test_new_password_follows_the_password_rules(mail):
    username, email = _user()
    client = _client()
    client.post("/auth/password/forgot", data={"email": email})
    token = _token_from(mail[-1])
    weak = client.post("/auth/password/reset", json={"token": token, "password": "abc", "confirm": "abc"}).json()
    assert weak["status"] == "weak" and "6 characters" in weak["message"]
    mismatch = client.post("/auth/password/reset", json={"token": token, "password": "abcdef1", "confirm": "abcdef2"}).json()
    assert mismatch["status"] == "mismatch"
    # Neither attempt used up the link.
    assert client.post("/auth/password/reset", json={"token": token, "password": "abcdef1", "confirm": "abcdef1"}).json()["status"] == "ok"


def test_every_session_is_signed_out(mail):
    username, email = _user()
    _, phone = _sign_in(username, "old-pass-1")
    _, laptop = _sign_in(username, "old-pass-1")
    assert _session_ok(phone) and _session_ok(laptop)
    browser = _client()
    login = browser.post("/auth/login", data={"username": username, "password": "old-pass-1"})
    assert login.status_code == 303 and browser.get("/auth/session").json()["authenticated"]

    other = _client()
    other.post("/auth/password/forgot", data={"email": email})
    token = _token_from(mail[-1])
    assert other.post("/auth/password/reset", json={"token": token, "password": "new-pass-2"}).json()["status"] == "ok"

    assert not _session_ok(phone) and not _session_ok(laptop)
    assert not browser.get("/auth/session").json()["authenticated"]
    assert TestClient(app).get("/notifications", headers={"authorization": f"Bearer {phone}"}).status_code == 401
    # The stale cookie no longer blocks the sign-in page, and a new sign-in works.
    assert browser.get("/login").status_code == 200
    status, fresh = _sign_in(username, "new-pass-2")
    assert status == 200 and _session_ok(fresh)


def test_change_password_signs_out_other_sessions_only(mail):
    username, _email = _user()
    _, other_device = _sign_in(username, "old-pass-1")
    _, this_device = _sign_in(username, "old-pass-1")
    resp = TestClient(app).post(
        "/auth/password/change",
        json={"current_password": "old-pass-1", "new_password": "new-pass-2"},
        headers={"authorization": f"Bearer {this_device}"},
    )
    assert resp.status_code == 200
    assert not _session_ok(other_device) and not _session_ok(this_device)
    assert _session_ok(resp.json()["access_token"])  # this device continues with the new session
    short = TestClient(app).post(
        "/auth/password/change",
        json={"current_password": "new-pass-2", "new_password": "abc"},
        headers={"authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert short.status_code == 400


def test_rate_limit_per_client(mail, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_MAX", "3")
    client = _client()
    for n in range(3):
        assert client.post("/auth/password/forgot", data={"email": f"someone{n}@example.com"}).headers["location"] == "/forgot-password?sent=1"
    resp = client.post("/auth/password/forgot", data={"email": "someone9@example.com"})
    assert resp.status_code == 303 and resp.headers["location"] == "/forgot-password?error=rate_limited"
    # Link checks and new-password submissions are limited per client too.
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_SUBMIT_MAX", "2")
    guesser = _client()
    for _ in range(2):
        assert guesser.post("/auth/password/reset/check", json={"token": "guess"}).status_code == 200
    assert guesser.post("/auth/password/reset", json={"token": "guess", "password": "abcdefg"}).status_code == 429


def test_rate_limit_per_account(mail):
    _username, email = _user()
    for _ in range(3):  # default: 3 links per account per hour, from any client
        assert _client().post("/auth/password/forgot", data={"email": email}).headers["location"] == "/forgot-password?sent=1"
    assert len(mail) == 3
    resp = _client().post("/auth/password/forgot", data={"email": email.upper()})
    assert resp.headers["location"] == "/forgot-password?sent=1"  # same answer...
    assert len(mail) == 3  # ...but no fourth e-mail


def test_email_not_configured_shows_a_clear_message(mail, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY")
    _username, email = _user()
    client = _client()
    page = client.get("/forgot-password")
    assert page.status_code == 200 and 'data-email-ready="0"' in page.text
    assert "Password reset is not available right now" in page.text and "support@smartwarrantyhub.com" in page.text
    resp = client.post("/auth/password/forgot", data={"email": email})
    assert resp.status_code == 303 and resp.headers["location"] == "/forgot-password"
    assert mail == []
    with SessionLocal() as db:
        assert db.query(PasswordResetTokenDB).filter_by(username=_username).count() == 0


def test_mail_failure_never_crashes(mail, monkeypatch):
    _username, email = _user()

    def boom(*a, **k):
        raise ConnectionError("resend unreachable")

    monkeypatch.setattr(emailer.requests, "post", boom)
    resp = _client().post("/auth/password/forgot", data={"email": email})
    assert resp.status_code == 303 and resp.headers["location"] == "/forgot-password?sent=1"


def test_invalid_email_is_asked_again(mail):
    resp = _client().post("/auth/password/forgot", data={"email": "not an email"})
    assert resp.headers["location"] == "/forgot-password?error=email"


def test_no_addresses_tokens_or_links_in_logs(mail, caplog):
    caplog.set_level(logging.DEBUG)
    username, email = _user()
    client = _client()
    client.post("/auth/password/forgot", data={"email": email})
    token = _token_from(mail[-1])
    client.post("/auth/password/reset/check", json={"token": token})
    client.post("/auth/password/reset", json={"token": token, "password": "new-pass-2"})
    client.post("/auth/password/forgot", data={"email": "nobody-here@example.com"})
    text = caplog.text
    assert token not in text and email not in text and email.lower() not in text
    assert "nobody-here@example.com" not in text and "reset-password#" not in text and "re_test_key" not in text


def test_reset_pages_are_not_cached_or_indexed():
    for path in ("/forgot-password", "/reset-password"):
        resp = TestClient(app).get(path)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store"
        assert resp.headers["referrer-policy"] == "no-referrer"
        assert "noindex" in resp.text
    assert 'data-mode="reset"' in TestClient(app).get("/reset-password").text


def test_reset_email_goes_out_after_the_daily_guard_stops_other_mail(mail):
    _username, email = _user()
    _set_sent_today(95)
    assert _client().post("/auth/password/forgot", data={"email": email}).headers["location"] == "/forgot-password?sent=1"
    assert len(mail) == 1 and {"name": "type", "value": "password_reset"} in mail[0]["tags"]
    assert emailer.send_welcome_email(to_email=email, username=_username, role="user") is False
    assert len(mail) == 1
