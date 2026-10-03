"""Security configuration warnings for the admin hub (fix run B4).

Reports weak or risky settings without changing them and without ever returning a secret value — only
variable names and the kind of problem. Never raises: a failing check is reported as a warning.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from .runtime_safety import env_truthy, insecure_defaults_allowed, is_production

_COMMON_WEAK = {"admin", "admin123", "password", "password123", "changeme", "change-me", "123456", "12345678", "qwerty"}


def _warn(out: List[Dict[str, str]], level: str, code: str, message: str) -> None:
    out.append({"level": level, "code": code, "message": message})


def security_report(db=None) -> Dict[str, object]:
    warnings: List[Dict[str, str]] = []
    prod = is_production()
    try:
        explicit = os.getenv("ALLOW_INSECURE_DEFAULTS")
        if explicit is not None and env_truthy(explicit):
            _warn(warnings, "critical", "allow_insecure_defaults",
                  "ALLOW_INSECURE_DEFAULTS is on: missing JWT secrets and admin credentials fall back to "
                  "built-in public defaults.")
        elif insecure_defaults_allowed():
            _warn(warnings, "warning", "insecure_defaults_by_environment",
                  "Insecure defaults are allowed because the app does not detect a production environment "
                  "(APP_ENV / ENVIRONMENT / RAILWAY_ENVIRONMENT).")

        secret = os.getenv("JWT_SECRET") or ""
        if not secret:
            _warn(warnings, "critical" if insecure_defaults_allowed() else "warning", "jwt_secret_missing",
                  "JWT_SECRET is not set (sessions use a default or a per-restart secret).")
        elif secret.lower() in _COMMON_WEAK or len(secret) < 32:
            _warn(warnings, "warning", "jwt_secret_weak", "JWT_SECRET is shorter than 32 characters or a common value.")
        if not os.getenv("JWT_SALT"):
            _warn(warnings, "warning", "jwt_salt_missing", "JWT_SALT is not set.")

        admin_pass = os.getenv("ADMIN_PASS") or ""
        if not os.getenv("ADMIN_USER") or not admin_pass:
            _warn(warnings, "warning", "admin_credentials_missing", "ADMIN_USER / ADMIN_PASS are not both set.")
        elif admin_pass.lower() in _COMMON_WEAK or len(admin_pass) < 12:
            _warn(warnings, "warning", "admin_password_weak", "ADMIN_PASS is shorter than 12 characters or a common value.")
        if db is not None and _default_admin_password_in_use(db):
            _warn(warnings, "critical", "default_admin_password", "An admin account still accepts the built-in default password.")

        cookie_secure = os.getenv("COOKIE_SECURE")
        if cookie_secure is not None and not env_truthy(cookie_secure):
            _warn(warnings, "critical" if prod else "warning", "cookie_not_secure",
                  "COOKIE_SECURE is off: session cookies may be sent over plain HTTP.")
        samesite = (os.getenv("COOKIE_SAMESITE") or "lax").strip().lower()
        if samesite not in ("lax", "strict", "none"):
            _warn(warnings, "warning", "cookie_samesite_invalid", "COOKIE_SAMESITE has an unknown value; 'lax' is used.")
        elif samesite == "none":
            _warn(warnings, "warning", "cookie_samesite_none",
                  "COOKIE_SAMESITE=none sends session cookies on cross-site requests (needs CSRF protection and Secure).")
        if prod and not env_truthy(os.getenv("FORCE_HTTPS_REDIRECT")):
            _warn(warnings, "warning", "https_redirect_off", "FORCE_HTTPS_REDIRECT is off in production: HTTP requests are not redirected to HTTPS.")
        if prod and not (os.getenv("ALLOWED_HOSTS") or "").strip():
            _warn(warnings, "warning", "allowed_hosts_empty", "ALLOWED_HOSTS is empty: any Host header is accepted.")
        if not env_truthy(os.getenv("RATE_LIMIT_ENABLED", "1")):
            _warn(warnings, "warning", "rate_limit_off", "RATE_LIMIT_ENABLED is off.")
        if os.getenv("SMTP_HOST") and not env_truthy(os.getenv("SMTP_SSL")) and not env_truthy(os.getenv("SMTP_STARTTLS", "1")):
            _warn(warnings, "warning", "smtp_plaintext", "SMTP_SSL and SMTP_STARTTLS are both off: e-mail is sent unencrypted.")
    except Exception as exc:  # pragma: no cover - never break the admin page
        _warn(warnings, "warning", "check_failed", f"A security check failed: {exc.__class__.__name__}")
    order = {"critical": 0, "warning": 1}
    warnings.sort(key=lambda w: order.get(w["level"], 2))
    return {
        "production": prod,
        "ok": not warnings,
        "critical": sum(1 for w in warnings if w["level"] == "critical"),
        "warnings": warnings,
    }


def _default_admin_password_in_use(db) -> bool:
    from ..db_models import UserDB
    from ..deps import verify_password

    for user in db.query(UserDB).filter(UserDB.role == "admin").limit(20).all():
        try:
            if user.hashed_password and verify_password("admin123", user.hashed_password):
                return True
        except Exception:
            continue
    return False


def https_redirect_target(forwarded_proto: Optional[str], host: Optional[str], path_qs: str) -> Optional[str]:
    """URL to redirect to when FORCE_HTTPS_REDIRECT is on and the proxy reports plain HTTP.

    Only acts on an explicit `X-Forwarded-Proto: http`, so internal health checks without the header are
    never redirected.
    """
    if not env_truthy(os.getenv("FORCE_HTTPS_REDIRECT")):
        return None
    if (forwarded_proto or "").split(",")[0].strip().lower() != "http" or not host:
        return None
    return f"https://{host}{path_qs}"
