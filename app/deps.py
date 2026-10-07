import os
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Header, HTTPException, Depends, Cookie
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from .db_models import Base, UserDB, AuditLogDB, UserSessionCutoffDB
from .services.runtime_safety import insecure_defaults_allowed


def _is_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


_ALLOW_INSECURE_DEFAULTS = insecure_defaults_allowed()

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    if _ALLOW_INSECURE_DEFAULTS:
        SECRET_KEY = "change-me"
        print("WARNING: JWT_SECRET is not set; using insecure default for compatibility.")
    else:
        SECRET_KEY = secrets.token_urlsafe(48)
        print("WARNING: JWT_SECRET is not set; generated ephemeral secret for this runtime.")

_JWT_SALT = os.getenv("JWT_SALT")
if not _JWT_SALT:
    if _ALLOW_INSECURE_DEFAULTS:
        _JWT_SALT = "swh-salt"
        print("WARNING: JWT_SALT is not set; using insecure default for compatibility.")
    else:
        _JWT_SALT = hashlib.sha256(f"{SECRET_KEY}:swh".encode()).hexdigest()
        print("WARNING: JWT_SALT is not set; derived runtime salt from JWT_SECRET.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = _JWT_SALT.encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


PASSWORD_MIN_LENGTH = 6


def password_problem(password: Optional[str]) -> Optional[str]:
    """The password rule used everywhere a password is set; None when the password is acceptable."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"Use at least {PASSWORD_MIN_LENGTH} characters."
    return None


def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        # When this session started (Unix seconds); sessions older than the user's cutoff are refused.
        "sat": time.time(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def session_revoked(db: Session, username: str, payload: dict) -> bool:
    """True when the user signed out all sessions (e.g. a new password) after this session started.
    Sessions issued before this check existed carry no start time and count as started at 0."""
    try:
        row = db.get(UserSessionCutoffDB, username)
    except Exception:  # table missing on a partly upgraded database: nothing was ever revoked there
        db.rollback()
        return False
    if row is None:
        return False
    try:
        started = float(payload.get("sat") or 0)
    except (TypeError, ValueError):
        started = 0.0
    return started < float(row.not_before_ts or 0)


def revoke_all_sessions(db: Session, username: str) -> float:
    """Every session of this user started before now stops working. Caller commits."""
    now = time.time()
    row = db.get(UserSessionCutoffDB, username)
    if row is None:
        db.add(UserSessionCutoffDB(username=username, not_before_ts=now, updated_at=datetime.utcnow()))
    else:
        row.not_before_ts = now
        row.updated_at = datetime.utcnow()
    return now


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    token_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> UserDB:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    elif token_cookie:
        token = token_cookie
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(UserDB).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if session_revoked(db, username, payload):
        raise HTTPException(status_code=401, detail="Session signed out")
    return user


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    token_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> Optional[UserDB]:
    try:
        return get_current_user(authorization, token_cookie, db)
    except HTTPException:
        return None


def require_user(user: UserDB = Depends(get_current_user)):
    return user


def require_admin(user: UserDB = Depends(get_current_user)):
    if user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_oem_or_admin(user: UserDB = Depends(get_current_user)):
    if user.role not in ("admin", "oem", "tpa"):
        raise HTTPException(status_code=403, detail="OEM/TPA/admin only")
    return user


def rbac_dependency(user: UserDB = Depends(require_user)):
    return user


def init_db():
    print(f"Initializing database... Dialect: {engine.dialect.name}")
    # Install Postgres extension first so later table creation does not fail on vector type.
    if engine.dialect.name == "postgresql":
        try:
            from sqlalchemy import text

            with SessionLocal() as db:
                db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                db.commit()
            print("Postgres vector extension enabled.")
        except Exception as exc:
            print(f"Vector extension init failed: {exc}")
    else:
        print("Using SQLite (vector extension skipped).")

    from .schema_upgrade import NEW_TABLES, run_startup_upgrade

    try:
        # Existing tables as before; the knowledge-base tables are created by the guarded upgrade below.
        Base.metadata.create_all(
            bind=engine, tables=[t for t in Base.metadata.sorted_tables if t.name not in NEW_TABLES]
        )
        # Belt-and-suspenders creation for hotfix safety on partially-migrated DBs.
        UserDB.__table__.create(bind=engine, checkfirst=True)
        AuditLogDB.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:
        print(f"DB create_all failed: {exc}")
        return
    run_startup_upgrade(engine)  # never raises; logs clearly and switches the cache/knowledge base off on failure

    try:
        with SessionLocal() as db:
            admin_user = os.getenv("ADMIN_USER")
            admin_pass = os.getenv("ADMIN_PASS")
            if not admin_user or not admin_pass:
                if _ALLOW_INSECURE_DEFAULTS:
                    admin_user = "admin"
                    admin_pass = "admin123"
                    print("WARNING: ADMIN_USER/ADMIN_PASS not set; using insecure defaults for compatibility.")
                else:
                    print("Skipping admin seed: set ADMIN_USER and ADMIN_PASS for production.")
                    return
            existing = db.query(UserDB).filter_by(username=admin_user).first()
            if not existing:
                db.add(
                    UserDB(
                        username=admin_user,
                        role="admin",
                        hashed_password=hash_password(admin_pass),
                        email=None,
                    )
                )
                db.commit()
    except Exception as exc:
        print(f"DB seed failed: {exc}")
