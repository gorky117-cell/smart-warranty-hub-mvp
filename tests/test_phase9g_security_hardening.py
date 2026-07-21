from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import create_access_token, hash_password
from app.main import _ensure_users_table_and_admin, app


def _user(username: str, role: str = "user") -> UserDB:
    return UserDB(
        username=username,
        role=role,
        hashed_password=hash_password("pw"),
        email=None,
        consent_analytics=1,
    )


def _seed_user_warranty(username: str) -> str:
    warranty_id = f"wr_{uuid4().hex[:10]}"
    with SessionLocal() as db:
        db.merge(_user(username))
        db.merge(
            WarrantyDB(
                id=warranty_id,
                product_name="Phone",
                brand="Acme",
                model_code="P1",
            )
        )
        db.merge(WarrantyOwnerDB(user_id=username, warranty_id=warranty_id))
        db.commit()
    return warranty_id


def _headers(username: str, role: str = "user") -> dict[str, str]:
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=username).first():
            db.add(_user(username, role))
            db.commit()
    return {"Authorization": f"Bearer {create_access_token(username, role)}"}


LEGACY_POST_ROUTES = [
    ("/behaviour-events", {"event_type": "nudge_dismissed", "details": {}}),
    ("/risk/score", {}),
    ("/service-tickets", {"symptom": "noise", "evidence": []}),
    ("/telemetry", {"event_type": "usage", "payload": {"hours": 1}}),
    ("/predictive/score", {}),
]


@pytest.mark.parametrize(("path", "extra_payload"), LEGACY_POST_ROUTES)
def test_legacy_post_routes_reject_cross_user_payloads(path, extra_payload):
    owner = f"owner_{uuid4().hex[:8]}"
    other = f"other_{uuid4().hex[:8]}"
    warranty_id = _seed_user_warranty(owner)
    client = TestClient(app)

    resp = client.post(
        path,
        json={"user_id": other, "warranty_id": warranty_id, **extra_payload},
        headers=_headers(owner),
    )

    assert resp.status_code == 403


@pytest.mark.parametrize(("path", "extra_payload"), LEGACY_POST_ROUTES)
def test_legacy_post_routes_require_warranty_ownership(path, extra_payload):
    owner = f"owner_{uuid4().hex[:8]}"
    other = f"other_{uuid4().hex[:8]}"
    warranty_id = _seed_user_warranty(owner)
    client = TestClient(app)

    resp = client.post(
        path,
        json={"user_id": other, "warranty_id": warranty_id, **extra_payload},
        headers=_headers(other),
    )

    assert resp.status_code == 403


def test_advisories_require_warranty_ownership():
    owner = f"owner_{uuid4().hex[:8]}"
    other = f"other_{uuid4().hex[:8]}"
    warranty_id = _seed_user_warranty(owner)
    client = TestClient(app)

    resp = client.get(
        f"/advisories/{warranty_id}",
        params={"user_id": other},
        headers=_headers(other),
    )

    assert resp.status_code == 403


def test_legacy_risk_route_allows_owner_access():
    owner = f"owner_{uuid4().hex[:8]}"
    warranty_id = _seed_user_warranty(owner)
    client = TestClient(app)

    resp = client.post(
        "/risk/score",
        json={"user_id": owner, "warranty_id": warranty_id},
        headers=_headers(owner),
    )

    assert resp.status_code == 200
    assert resp.json()["user_id"] == owner


def test_partial_db_admin_fallback_does_not_seed_insecure_admin_in_production(monkeypatch):
    admin_user = f"admin_{uuid4().hex[:8]}"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOW_INSECURE_DEFAULTS", raising=False)
    monkeypatch.setenv("ADMIN_USER", admin_user)
    monkeypatch.delenv("ADMIN_PASS", raising=False)

    with SessionLocal() as db:
        _ensure_users_table_and_admin(db)
        assert db.query(UserDB).filter_by(username=admin_user).first() is None
