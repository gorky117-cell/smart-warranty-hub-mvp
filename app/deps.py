import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Header, HTTPException, Depends, Cookie
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from .db_models import Base, UserDB

SECRET_KEY = os.getenv("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    salt = os.getenv("JWT_SALT", "swh-salt").encode()
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def create_access_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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
    if user.role not in ("admin", "oem"):
        raise HTTPException(status_code=403, detail="OEM/admin only")
    return user


# Backward-compatible alias
def rbac_dependency(user: UserDB = Depends(require_user)):
    return user


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin_user = os.getenv("ADMIN_USER", "admin")
        admin_pass = os.getenv("ADMIN_PASS", "admin123")
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
