"""Per-user password salt (backlog #20): new hashes carry their own salt; old shared-salt hashes still verify
and are upgraded on the next successful sign-in."""
from fastapi.testclient import TestClient

from app import deps
from app.db import SessionLocal
from app.db_models import UserDB
from app.main import app


def test_new_hashes_have_a_salt_per_password():
    a, b = deps.hash_password("same-pass"), deps.hash_password("same-pass")
    assert a != b  # different salts
    for h in (a, b):
        scheme, iterations, salt, digest = h.split("$")
        assert scheme == "pbkdf2_sha256" and int(iterations) == deps.PASSWORD_ITERATIONS
        assert len(bytes.fromhex(salt)) == 16 and len(digest) == 64
        assert deps.verify_password("same-pass", h)
        assert not deps.verify_password("other-pass", h)
        assert not deps.needs_rehash(h)


def test_old_shared_salt_hashes_still_verify():
    old = deps._legacy_hash("legacy-pass")
    assert "$" not in old and len(old) == 64
    assert deps.verify_password("legacy-pass", old)
    assert not deps.verify_password("wrong", old)
    assert deps.needs_rehash(old)


def test_broken_or_empty_hashes_never_verify():
    for bad in ("", None, "pbkdf2_sha256$x$zz$00", "pbkdf2_sha256$1000", "pbkdf2_sha256$1000$nothex$00"):
        assert deps.verify_password("anything", bad) is False
    assert deps.needs_rehash("pbkdf2_sha256$1000$00$00")  # fewer iterations than today


def _put_user(username, hashed):
    with SessionLocal() as db:
        db.query(UserDB).filter_by(username=username).delete()
        db.add(UserDB(username=username, role="user", hashed_password=hashed, email=f"{username}@example.com"))
        db.commit()


def _stored(username):
    with SessionLocal() as db:
        return db.query(UserDB).filter_by(username=username).first().hashed_password


def test_old_hash_is_upgraded_on_next_sign_in(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _put_user("legacy_hash_user", deps._legacy_hash("legacy-pass"))
    client = TestClient(app, follow_redirects=False)
    # A wrong password changes nothing.
    assert client.post("/auth/login", data={"username": "legacy_hash_user", "password": "nope"}).headers["location"].startswith("/login?error=invalid")
    assert "$" not in _stored("legacy_hash_user")
    # The right one signs in and upgrades the hash.
    assert client.post("/auth/login", data={"username": "legacy_hash_user", "password": "legacy-pass"}).status_code == 303
    upgraded = _stored("legacy_hash_user")
    assert upgraded.startswith("pbkdf2_sha256$") and deps.verify_password("legacy-pass", upgraded)
    # Signing in again works and keeps the new hash.
    resp = client.post("/auth/login", data={"username": "legacy_hash_user", "password": "legacy-pass"}, headers={"accept": "application/json"})
    assert resp.status_code == 200 and _stored("legacy_hash_user") == upgraded
