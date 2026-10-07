"""Forgot password: one-time reset links sent by e-mail.

- The link carries a random token (256 bits) in the URL fragment (`/reset-password#token=...`), so it never
  reaches server or proxy access logs; the page posts it in the request body.
- Only the SHA-256 of the token is stored. A link expires after 30 minutes, works once, and asking for a
  new link retires every earlier unused one.
- Setting the new password signs out every session of that user (deps.revoke_all_sessions).
- The request answer is the same whether or not an account uses the e-mail address.
- Nothing here logs addresses, tokens or links.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from html import escape
from typing import List, Optional, Tuple

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from ..db_models import PasswordResetTokenDB, UserDB
from ..deps import hash_password, password_problem, revoke_all_sessions
from . import emailer

TOKEN_TTL_MINUTES = 30
MAX_ACCOUNTS_PER_EMAIL = 5
# Check / reset outcomes.
OK, EXPIRED, USED, INVALID = "ok", "expired", "used", "invalid"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def account_key(email: str) -> str:
    """Rate-limit key for an e-mail address that does not reveal the address."""
    return "acct-" + hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()[:24]


def accounts_for_email(db: Session, email: str) -> List[UserDB]:
    email = (email or "").strip().lower()
    if not emailer.is_valid_address(email):
        return []
    return (
        db.query(UserDB)
        .filter(UserDB.email.isnot(None), func.lower(func.trim(UserDB.email)) == email)
        .order_by(UserDB.id)
        .limit(MAX_ACCOUNTS_PER_EMAIL)
        .all()
    )


def issue_token(db: Session, username: str, *, now: Optional[datetime] = None) -> str:
    """New one-time token for this user; earlier unused tokens stop working. Commits."""
    now = now or datetime.utcnow()
    db.execute(
        update(PasswordResetTokenDB)
        .where(PasswordResetTokenDB.username == username, PasswordResetTokenDB.used_at.is_(None))
        .values(used_at=now)
    )
    # Housekeeping: forget links that ended more than a day ago.
    db.query(PasswordResetTokenDB).filter(PasswordResetTokenDB.expires_at < now - timedelta(days=1)).delete(
        synchronize_session=False
    )
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetTokenDB(
            username=username,
            token_hash=_hash(token),
            created_at=now,
            expires_at=now + timedelta(minutes=TOKEN_TTL_MINUTES),
        )
    )
    db.commit()
    return token


def check_token(db: Session, token: Optional[str], *, now: Optional[datetime] = None) -> Tuple[str, Optional[PasswordResetTokenDB]]:
    token = (token or "").strip()
    if not token or len(token) > 200:
        return INVALID, None
    row = db.query(PasswordResetTokenDB).filter_by(token_hash=_hash(token)).first()
    if row is None:
        return INVALID, None
    if row.used_at is not None:
        return USED, row
    if (now or datetime.utcnow()) >= row.expires_at:
        return EXPIRED, row
    return OK, row


def reset_password(db: Session, token: Optional[str], new_password: str, *, now: Optional[datetime] = None) -> str:
    """Use the token to set a new password. Returns OK, EXPIRED, USED, INVALID or "weak". Commits on OK."""
    now = now or datetime.utcnow()
    state, row = check_token(db, token, now=now)
    if state != OK:
        return state
    if password_problem(new_password):
        return "weak"
    user = db.query(UserDB).filter_by(username=row.username).first()
    if user is None:
        return INVALID
    # Claim the token atomically: a second request racing this one finds it already used.
    claimed = db.execute(
        update(PasswordResetTokenDB)
        .where(PasswordResetTokenDB.id == row.id, PasswordResetTokenDB.used_at.is_(None))
        .values(used_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        return USED
    user.hashed_password = hash_password(new_password)
    revoke_all_sessions(db, user.username)
    db.commit()
    return OK


def reset_link(token: str) -> str:
    return f"{emailer.app_base_url()}/reset-password#token={token}"


def reset_email(username: str, link: str) -> Tuple[str, str, str]:
    """(subject, plain text, HTML) in simple words."""
    subject = "Reset your Smart Warranty Hub password"
    text = (
        f"Hi {username},\n\n"
        f"We got a request to reset the password for your Smart Warranty Hub account \"{username}\".\n\n"
        "To choose a new password, open this link:\n"
        f"{link}\n\n"
        f"The link works for {TOKEN_TTL_MINUTES} minutes and only once. "
        "If it has stopped working, ask for a new one on the sign-in page.\n\n"
        "If this wasn't you, ignore this email. Your password will not change.\n\n"
        "Team Smart Warranty Hub\n"
        "Questions? Just reply to this email.\n"
    )
    name = escape(username)
    url = escape(link, quote=True)
    html = (
        "<!DOCTYPE html><html><body style=\"font-family:Arial,Helvetica,sans-serif;color:#0f172a;line-height:1.5\">"
        f"<p>Hi {name},</p>"
        f"<p>We got a request to reset the password for your Smart Warranty Hub account &quot;{name}&quot;.</p>"
        f"<p><a href=\"{url}\" style=\"display:inline-block;background:#1d4ed8;color:#ffffff;padding:10px 18px;"
        "border-radius:8px;text-decoration:none;font-weight:bold\">Choose a new password</a></p>"
        f"<p>Or copy this link into your browser:<br><span style=\"word-break:break-all\">{url}</span></p>"
        f"<p>The link works for {TOKEN_TTL_MINUTES} minutes and only once. If it has stopped working, ask for a "
        "new one on the sign-in page.</p>"
        "<p>If this wasn't you, ignore this email. Your password will not change.</p>"
        "<p>Team Smart Warranty Hub<br>Questions? Just reply to this email.</p>"
        "</body></html>"
    )
    return subject, text, html


def send_reset_email(*, to_email: str, username: str, token: str) -> bool:
    subject, text, html = reset_email(username, reset_link(token))
    return emailer.send_email(
        to_email=to_email, subject=subject, body_text=text, body_html=html, message_type="password_reset"
    )
