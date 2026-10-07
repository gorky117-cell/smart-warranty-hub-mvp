"""Owner review of PR #3, item 4: the consent wording for brand totals, shown at the question; opt-in, changeable."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import AnonymousTotalsConsentDB, UserDB
from app.deps import hash_password
from app.main import app
from app.services import brand_access

TEXT = ("Allow SWH to share anonymous totals (never your name or details) with the brand, only for groups of 10 or "
        "more people. You can change this anytime.")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username="totals_user").first():
            db.add(UserDB(username="totals_user", role="user", hashed_password=hash_password("secret123"), email="t@example.com"))
        db.query(AnonymousTotalsConsentDB).filter_by(user_id="totals_user").delete()
        db.commit()
    c = TestClient(app)
    token = c.post("/auth/login", data={"username": "totals_user", "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {token}"}


def test_exact_wording():
    assert brand_access.ANONYMOUS_TOTALS_CONSENT == TEXT and brand_access.MIN_GROUP == 10


def test_off_until_allowed_and_changeable_anytime(client):
    c, headers = client
    assert c.get("/account/anonymous-totals", headers=headers).json() == {"text": TEXT, "allow": False}
    assert c.post("/account/anonymous-totals", json={"allow": True}, headers=headers).json()["allow"] is True
    with SessionLocal() as db:
        assert brand_access.totals_allowed(db, "totals_user") is True
    assert c.post("/account/anonymous-totals", json={"allow": False}, headers=headers).json()["allow"] is False
    assert c.get("/account/anonymous-totals", headers=headers).json()["allow"] is False
    assert c.post("/account/anonymous-totals", json={"allow": "yes"}, headers=headers).status_code == 422


def test_needs_sign_in():
    assert TestClient(app).get("/account/anonymous-totals").status_code == 401


def test_shown_at_the_question_on_the_dashboard():
    html = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")
    card = html[html.index('id="behaviourCard"'): html.index('id="recCard"')]
    assert TEXT in card and 'id="totalsConsentBox"' in card and "checked" not in card.split('id="totalsConsentBox"')[1].split(">")[0]
    assert "loadTotalsConsent();" in html
