import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _app_base_url() -> str:
    return (os.getenv("APP_BASE_URL") or "https://www.smartwarrantyhub.com").rstrip("/")


def send_email(*, to_email: Optional[str], subject: str, body_text: str) -> bool:
    if not to_email:
        return False
    if not _bool_env("EMAIL_ENABLED", True):
        logger.info("EMAIL_ENABLED is false. Skipping email to %s", to_email)
        return False

    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip())
    username = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    from_email = (os.getenv("MAIL_FROM") or "team@smartwarrantyhub.com").strip()
    use_tls = _bool_env("SMTP_STARTTLS", True)
    use_ssl = _bool_env("SMTP_SSL", False)

    if not host:
        logger.warning("SMTP_HOST is missing. Could not send email to %s", to_email)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
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
    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", to_email, exc)
        return False


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
    return send_email(to_email=to_email, subject=title, body_text=body)


def send_login_alert_email(*, to_email: Optional[str], username: str) -> bool:
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
    )
