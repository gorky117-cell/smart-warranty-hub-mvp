from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB
from app.deps import hash_password
from app.main import app
from app.services import oem_consent


def _ensure_user(db, username: str, role: str = "user") -> None:
    row = db.query(UserDB).filter_by(username=username).first()
    if row:
        row.role = role
        db.add(row)
        db.commit()
        return
    db.add(
        UserDB(
            username=username,
            role=role,
            hashed_password=hash_password("pass123"),
            email=f"{username}@example.com",
            consent_analytics=1,
        )
    )
    db.commit()


def _login(client: TestClient, username: str = "phase9f_user") -> str:
    resp = client.post(
        "/auth/login",
        data={"username": username, "password": "pass123"},
        headers={"accept": "application/json"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_oem_direct_consent_defaults_off(monkeypatch, tmp_path):
    monkeypatch.setenv("OEM_DIRECT_CONSENT_FILE", str(tmp_path / "oem_consent.json"))

    assert oem_consent.get_oem_direct_consent("new_user")["oem_direct_sharing"] is False
    assert oem_consent.has_oem_direct_consent("new_user") is False


def test_consent_endpoint_updates_direct_oem_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("OEM_DIRECT_CONSENT_FILE", str(tmp_path / "oem_consent.json"))
    with SessionLocal() as db:
        _ensure_user(db, "phase9f_user")
    client = TestClient(app)
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    update = client.post(
        "/consent",
        json={"user_id": "phase9f_user", "consent_oem_direct_sharing": True},
        headers=headers,
    )
    current = client.get("/consent", headers=headers)

    assert update.status_code == 200
    assert update.json()["consent_oem_direct_sharing"] is True
    assert current.status_code == 200
    assert current.json()["consent_oem_direct_sharing"] is True


def test_user_cannot_update_another_users_oem_direct_consent(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("OEM_DIRECT_CONSENT_FILE", str(tmp_path / "oem_consent.json"))
    with SessionLocal() as db:
        _ensure_user(db, "phase9f_user")
        _ensure_user(db, "phase9f_other")
    client = TestClient(app)
    token = _login(client)

    resp = client.post(
        "/consent",
        json={"user_id": "phase9f_other", "consent_oem_direct_sharing": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403
