"""Outgoing e-mail through Resend (HTTP API) or SMTP, chosen by configuration.

Configuration (names only; values live in Railway / the local .env, never in the repo):
- EMAIL_ENABLED     "false" switches all e-mail off (default on).
- EMAIL_PROVIDER    "resend", "smtp" or "auto" (default): auto uses Resend when RESEND_API_KEY is set,
                    otherwise SMTP when SMTP_HOST is set, otherwise nothing is sent.
- RESEND_API_KEY    Resend API key (provider "resend").
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_STARTTLS, SMTP_SSL   (provider "smtp").
- MAIL_FROM         sender, default "Smart Warranty Hub <noreply@smartwarrantyhub.com>".
- MAIL_REPLY_TO     Reply-To, default "support@smartwarrantyhub.com".
- APP_BASE_URL      links in e-mails, default https://www.smartwarrantyhub.com.
- SIGNIN_ALERT_EMAILS  "1" sends an alert e-mail on every sign-in (default off).

Rules: sending never raises (callers get True/False); logs never contain e-mail addresses, links,
tokens or provider responses - only the message type, provider and outcome. Resend messages carry the
tags app=swh and type=<message type>.
"""
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import requests


logger = logging.getLogger(__name__)

DEFAULT_FROM = "Smart Warranty Hub <noreply@smartwarrantyhub.com>"
DEFAULT_REPLY_TO = "support@smartwarrantyhub.com"
RESEND_API_URL = "https://api.resend.com/emails"
_EMAIL_RE = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[^@\s<>,;\"']+$")
# Resend tag values: ASCII letters, numbers, underscores and dashes only.
_TAG_RE = re.compile(r"[^A-Za-z0-9_-]")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _app_base_url() -> str:
    return (os.getenv("APP_BASE_URL") or "https://www.smartwarrantyhub.com").rstrip("/")


def app_base_url() -> str:
    return _app_base_url()


def is_valid_address(value: Optional[str]) -> bool:
    return bool(value) and len(value) <= 254 and bool(_EMAIL_RE.match(value.strip()))


def selected_provider() -> Optional[str]:
    """'resend', 'smtp' or None (nothing configured)."""
    choice = (os.getenv("EMAIL_PROVIDER") or "auto").strip().lower()
    has_resend = bool((os.getenv("RESEND_API_KEY") or "").strip())
    has_smtp = bool((os.getenv("SMTP_HOST") or "").strip())
    if choice == "resend":
        return "resend" if has_resend else None
    if choice == "smtp":
        return "smtp" if has_smtp else None
    if has_resend:
        return "resend"
    if has_smtp:
        return "smtp"
    return None


def email_status() -> dict:
    """What is configured, as names and booleans only (safe for admin pages and logs)."""
    enabled = _bool_env("EMAIL_ENABLED", True)
    provider = selected_provider()
    if not enabled:
        reason = "EMAIL_ENABLED is off"
    elif not provider:
        choice = (os.getenv("EMAIL_PROVIDER") or "auto").strip().lower()
        reason = {
            "resend": "EMAIL_PROVIDER is resend but RESEND_API_KEY is not set",
            "smtp": "EMAIL_PROVIDER is smtp but SMTP_HOST is not set",
        }.get(choice, "neither RESEND_API_KEY nor SMTP_HOST is set")
    else:
        reason = None
    return {"enabled": enabled, "provider": provider, "configured": bool(enabled and provider), "reason": reason}


def email_configured() -> bool:
    return email_status()["configured"]


def _tag(value: str) -> str:
    return (_TAG_RE.sub("_", value or "general") or "general")[:256]


def _send_resend(*, to_email: str, subject: str, body_text: str, body_html: Optional[str], message_type: str,
                 from_email: str, reply_to: str) -> bool:
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body_text,
        "reply_to": reply_to,
        "tags": [{"name": "app", "value": "swh"}, {"name": "type", "value": _tag(message_type)}],
    }
    if body_html:
        payload["html"] = body_html
    response = requests.post(
        RESEND_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {(os.getenv('RESEND_API_KEY') or '').strip()}"},
        timeout=15,
    )
    if 200 <= response.status_code < 300:
        return True
    logger.warning("E-mail not sent: type=%s provider=resend status=%s", message_type, response.status_code)
    return False


def _send_smtp(*, to_email: str, subject: str, body_text: str, body_html: Optional[str], message_type: str,
               from_email: str, reply_to: str) -> bool:
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip())
    username = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    use_tls = _bool_env("SMTP_STARTTLS", True)
    use_ssl = _bool_env("SMTP_SSL", False)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["X-SWH-Type"] = _tag(message_type)
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls(context=ssl.create_default_context())
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    return True


def send_email(
    *,
    to_email: Optional[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    message_type: str = "general",
) -> bool:
    """Send one e-mail. Never raises; returns True only when the provider accepted it."""
    if not to_email:
        return False
    status = email_status()
    if not status["configured"]:
        logger.info("E-mail not sent: type=%s (%s)", message_type, status["reason"])
        return False
    to_email = to_email.strip()
    if not is_valid_address(to_email):
        logger.warning("E-mail not sent: type=%s (invalid recipient address)", message_type)
        return False
    kwargs = dict(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        message_type=message_type,
        from_email=(os.getenv("MAIL_FROM") or DEFAULT_FROM).strip(),
        reply_to=(os.getenv("MAIL_REPLY_TO") or DEFAULT_REPLY_TO).strip(),
    )
    provider = status["provider"]
    try:
        sent = _send_resend(**kwargs) if provider == "resend" else _send_smtp(**kwargs)
    except Exception as exc:  # the exception text can contain the address, so only its class is logged
        logger.warning("E-mail not sent: type=%s provider=%s error=%s", message_type, provider, exc.__class__.__name__)
        return False
    if sent:
        logger.info("E-mail sent: type=%s provider=%s", message_type, provider)
    return sent


def send_welcome_email(*, to_email: Optional[str], username: str, role: str) -> bool:
    role_label = (role or "user").strip().lower()
    if role_label == "user":
        title = "Welcome to Smart Warranty Hub"
        body = (
            f"Hi {username},\n\n"
            "Welcome to Smart Warranty Hub.\n"
            "Why this is important: your warranty details, reminders, and risk alerts stay in one place so you can act early and avoid claim issues.\n\n"
            f"Open your dashboard: {_app_base_url()}/ui/neo-dashboard\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        )
    elif role_label == "oem":
        title = "Welcome OEM Team - Smart Warranty Hub"
        body = (
            f"Hi {username},\n\n"
            "Welcome onboard. Your OEM workspace is ready for issue trends, forecasts, and actions.\n\n"
            f"Open OEM dashboard: {_app_base_url()}/ui/oem-dashboard\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        )
    elif role_label == "tpa":
        title = "Welcome TPA Team - Smart Warranty Hub"
        body = (
            f"Hi {username},\n\n"
            "Welcome onboard. Good to have your TPA team connected for faster and cleaner post-purchase operations.\n\n"
            f"Open platform: {_app_base_url()}/login\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        )
    else:
        title = "Welcome to Smart Warranty Hub"
        body = (
            f"Hi {username},\n\n"
            "Welcome onboard.\n\n"
            f"Open platform: {_app_base_url()}/login\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        )
    return send_email(to_email=to_email, subject=title, body_text=body, message_type="welcome")


def signin_alerts_enabled() -> bool:
    """Sign-in alert e-mails are off unless SIGNIN_ALERT_EMAILS=1 (they would go out on every sign-in)."""
    return _bool_env("SIGNIN_ALERT_EMAILS", False)


def send_login_alert_email(*, to_email: Optional[str], username: str) -> bool:
    if not signin_alerts_enabled():
        return False
    return send_email(
        to_email=to_email,
        subject="Sign-in alert - Smart Warranty Hub",
        body_text=(
            f"Hi {username},\n\n"
            "Your Smart Warranty Hub account was just signed in.\n"
            "If this was not you, please change your password immediately.\n\n"
            f"Change password after login: {_app_base_url()}/ui/neo-dashboard\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        ),
        message_type="login_alert",
    )


def send_product_registered_email(
    *,
    to_email: Optional[str],
    username: str,
    warranty_id: str,
) -> bool:
    return send_email(
        to_email=to_email,
        subject="Product registered - Smart Warranty Hub",
        body_text=(
            f"Hi {username},\n\n"
            "Your product has been registered successfully.\n"
            f"Warranty ID: {warranty_id}\n\n"
            f"Open Neo Dashboard: {_app_base_url()}/ui/neo-dashboard\n\n"
            "Regards,\n"
            "Team Smart Warranty Hub"
        ),
        message_type="product_registered",
    )
