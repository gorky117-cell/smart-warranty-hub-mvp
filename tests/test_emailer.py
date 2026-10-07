"""E-mail sending: Resend or SMTP chosen by config, tags, Reply-To, never raises, no addresses in logs."""
import logging

import pytest

from app.services import emailer

ADDRESS = "buyer.person@example.com"
_ENV = ("EMAIL_ENABLED", "EMAIL_PROVIDER", "RESEND_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS",
        "SMTP_STARTTLS", "SMTP_SSL", "MAIL_FROM", "MAIL_REPLY_TO")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


def _capture_resend(monkeypatch, status_code=200):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _Response(status_code)

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    return calls


class _FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


def test_provider_selection(monkeypatch):
    assert emailer.selected_provider() is None
    assert emailer.email_status()["reason"] == "neither RESEND_API_KEY nor SMTP_HOST is set"
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    assert emailer.selected_provider() == "smtp"
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    assert emailer.selected_provider() == "resend"  # auto prefers Resend
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    assert emailer.selected_provider() == "smtp"
    monkeypatch.delenv("SMTP_HOST")
    assert emailer.selected_provider() is None
    assert "SMTP_HOST" in emailer.email_status()["reason"]
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    assert emailer.email_configured()
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    assert not emailer.email_configured()


def test_resend_payload_has_tags_reply_to_and_both_bodies(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    calls = _capture_resend(monkeypatch)
    ok = emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="plain", body_html="<p>html</p>",
                            message_type="password_reset")
    assert ok
    call = calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test"
    body = call["json"]
    assert body["from"] == "Smart Warranty Hub <noreply@smartwarrantyhub.com>"
    assert body["reply_to"] == "support@smartwarrantyhub.com"
    assert body["to"] == [ADDRESS]
    assert body["text"] == "plain" and body["html"] == "<p>html</p>"
    assert {"name": "app", "value": "swh"} in body["tags"]
    assert {"name": "type", "value": "password_reset"} in body["tags"]


def test_mail_from_and_reply_to_come_from_config(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Team <team@example.org>")
    monkeypatch.setenv("MAIL_REPLY_TO", "help@example.org")
    calls = _capture_resend(monkeypatch)
    emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="x")
    assert calls[0]["json"]["from"] == "Team <team@example.org>"
    assert calls[0]["json"]["reply_to"] == "help@example.org"


def test_smtp_sends_text_and_html_with_reply_to(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    _FakeSMTP.sent = []
    monkeypatch.setattr(emailer.smtplib, "SMTP", _FakeSMTP)
    ok = emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="plain", body_html="<p>html</p>",
                            message_type="password_reset")
    assert ok
    msg = _FakeSMTP.sent[0]
    assert msg["Reply-To"] == "support@smartwarrantyhub.com"
    assert msg["X-SWH-Type"] == "password_reset"
    types = [part.get_content_type() for part in msg.walk()]
    assert "text/plain" in types and "text/html" in types


def test_failures_never_raise_and_logs_hold_no_address(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    # Not configured.
    assert emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="x", message_type="password_reset") is False
    # Provider rejects.
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    _capture_resend(monkeypatch, status_code=422)
    assert emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="x") is False

    # Provider raises with the address in the error text.
    def boom(*a, **k):
        raise RuntimeError(f"could not deliver to {ADDRESS}")

    monkeypatch.setattr(emailer.requests, "post", boom)
    assert emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="x") is False
    # SMTP failure.
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    def smtp_boom(*a, **k):
        raise OSError(f"refused {ADDRESS}")

    monkeypatch.setattr(emailer.smtplib, "SMTP", smtp_boom)
    assert emailer.send_email(to_email=ADDRESS, subject="Hi", body_text="x") is False
    assert caplog.records
    assert ADDRESS not in caplog.text and "re_test" not in caplog.text


def test_invalid_recipient_is_refused(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    calls = _capture_resend(monkeypatch)
    assert emailer.send_email(to_email="a@b.com\r\nBcc: x@y.com", subject="Hi", body_text="x") is False
    assert emailer.send_email(to_email="not-an-address", subject="Hi", body_text="x") is False
    assert calls == []


def test_existing_messages_carry_their_type(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    calls = _capture_resend(monkeypatch)
    emailer.send_welcome_email(to_email=ADDRESS, username="u", role="user")
    emailer.send_login_alert_email(to_email=ADDRESS, username="u")
    emailer.send_product_registered_email(to_email=ADDRESS, username="u", warranty_id="w1")
    types = [next(t["value"] for t in c["json"]["tags"] if t["name"] == "type") for c in calls]
    assert types == ["welcome", "login_alert", "product_registered"]
