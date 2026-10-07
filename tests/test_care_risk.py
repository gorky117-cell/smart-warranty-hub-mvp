"""Risk wording without question packs on this branch (owner review of PR #3): "Not enough information yet - answer
3 quick questions" only when an APPROVED pack has questions for the product, otherwise "We can't rate this yet.",
and never "Low risk" without answers. The packs module (services/care_packs.py) comes from the packs branch; here
it is faked through its public functions."""
import sys
import types
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import care_risk

USER = "care_risk_user"


@pytest.fixture
def fake_packs(monkeypatch):
    """Install a stand-in app.services.care_packs: one approved AC pack; answers held in memory."""
    state = {"approved": True, "answers": {}, "insights": {}}
    mod = types.ModuleType("app.services.care_packs")

    def customer_pack(db, warranty):
        if "AC" not in (warranty.product_name or "") or not state["approved"]:
            return None
        return {"product_type": "air_conditioner", "status": "approved", "questions": [{"id": "q1"}]}

    mod.customer_pack = customer_pack
    mod.answers_for = lambda db, user, wid: dict(state["answers"])
    mod.insights = lambda db, user, w: dict(state["insights"])
    monkeypatch.setitem(sys.modules, "app.services.care_packs", mod)
    import app.services as services_pkg

    monkeypatch.setattr(services_pkg, "care_packs", mod, raising=False)
    return state


def _w(product, bought=datetime(2017, 4, 22)):
    return types.SimpleNamespace(id="w1", product_name=product, purchase_date=bought)


def test_without_any_packs_module_we_cannot_rate():
    with SessionLocal() as db:
        result = care_risk.summary(db, USER, _w("Voltas Window AC"), today=date(2026, 10, 7))
    assert result["status"] == "cannot_rate" and result["text"] == "We can't rate this yet."
    assert result["label"] is None and result["age_note"] == "Bought 22 Apr 2017 - about 9 years old."


def test_approved_pack_without_answers_asks_for_three_answers(fake_packs):
    with SessionLocal() as db:
        result = care_risk.summary(db, USER, _w("Voltas Window AC"))
    assert result["status"] == "needs_answers"
    assert result["text"] == "Not enough information yet - answer 3 quick questions"


def test_draft_pack_or_other_product_cannot_be_rated(fake_packs):
    fake_packs["approved"] = False
    with SessionLocal() as db:
        assert care_risk.summary(db, USER, _w("Voltas Window AC"))["text"] == "We can't rate this yet."
    fake_packs["approved"] = True
    with SessionLocal() as db:
        assert care_risk.summary(db, USER, _w("HP Laptop"))["text"] == "We can't rate this yet."


def test_only_skips_still_need_answers(fake_packs):
    fake_packs["answers"] = {"q1": "skip"}
    with SessionLocal() as db:
        assert care_risk.summary(db, USER, _w("Voltas Window AC"))["status"] == "needs_answers"


# The packs module's insights(): "label" is the product type's name; risk_reasons are {"effect", "reason"}.
@pytest.mark.parametrize("risks,label,text", [
    ([], "LOW", "Looking after it well"),
    ([{"effect": "lower", "reason": "Serviced every year."}], "LOW", "Looking after it well"),
    ([{"effect": "raise", "reason": "Long daily running wears parts faster."}], "MEDIUM", "Some things to watch"),
    ([{"effect": "raise", "reason": "a"}, {"effect": "raise", "reason": "b"}, {"effect": "raise", "reason": "c"}], "HIGH", "Needs attention"),
])
def test_answers_give_a_label_from_the_packs_risk_factors(fake_packs, risks, label, text):
    fake_packs["answers"] = {"q1": "over_8h"}
    fake_packs["insights"] = {"product_type": "air_conditioner", "label": "Air conditioner (split or window)", "risk_reasons": risks}
    with SessionLocal() as db:
        result = care_risk.summary(db, USER, _w("Voltas Window AC"))
    assert result["status"] == "assessed" and result["label"] == label and result["text"] == text
    assert "Air conditioner" not in result["text"]  # the product name is never taken as a rating
    if risks and risks[0]["effect"] == "raise":
        assert result["reasons"][0] == risks[0]["reason"]


@pytest.mark.parametrize("bought,note", [
    (datetime(2026, 9, 20), "Bought 20 Sep 2026 - less than a month old."),
    (datetime(2026, 1, 10), "Bought 10 Jan 2026 - less than a year old."),
    (datetime(2024, 10, 7), "Bought 7 Oct 2024 - about 2 years old."),
    (None, None),
])
def test_age_note(bought, note):
    assert care_risk.age_note(bought, today=date(2026, 10, 7)) == note


def test_endpoint_is_owner_only(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        for name in (USER, "care_risk_other"):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123"), email=f"{name}@example.com"))
        db.query(WarrantyOwnerDB).filter_by(warranty_id="cr_w1").delete()
        db.query(WarrantyDB).filter_by(id="cr_w1").delete()
        db.add(WarrantyDB(id="cr_w1", product_name="Voltas Window AC", purchase_date=datetime(2017, 4, 22), alternatives={}))
        db.add(WarrantyOwnerDB(user_id=USER, warranty_id="cr_w1"))
        db.commit()

    def client(user):
        c = TestClient(app)
        token = c.post("/auth/login", data={"username": user, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
        return c, {"Authorization": f"Bearer {token}"}

    owner, auth = client(USER)
    assert owner.get("/warranties/cr_w1/care-risk", headers=auth).json()["text"] == "We can't rate this yet."
    other, other_auth = client("care_risk_other")
    assert other.get("/warranties/cr_w1/care-risk", headers=other_auth).status_code == 403


def test_dashboard_has_no_pack_block_and_never_says_low_risk_without_answers():
    html = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")
    for gone in ('id="packCard"', "loadQuestionPack", "/questions/answer", "/account/share-answers"):
        assert gone not in html
    status_fn = html[html.index("function careRiskStatus"): html.index("function renderCareRisk")]
    assert "We can't rate this yet" in status_fn and "Low risk" not in status_fn
    assert "const predStatus = careRiskStatus(careRisk);" in html
