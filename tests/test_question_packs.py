"""Batch 3 items 9 and 10: question packs per product type, care-risk wording, reminders, anonymous group counts."""
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import (NotificationDB, QuestionPackAnswerDB, QuestionPackConsentDB, UserDB, WarrantyDB,
                           WarrantyOwnerDB)
from app.deps import hash_password
from app.main import app
from app.services import question_packs as qp

USER = "pack_user"
PRODUCTS = {
    "air_conditioner": "Voltas 1.5 Ton 3 Star Window AC", "smartphone": "Samsung Galaxy M17e Mobile Phone",
    "fridge": "LG 242 L Double Door Refrigerator", "washing_machine": "Bosch 7 kg Front Load Washing Machine",
    "water_heater": "Racold 25L Storage Water Heater Geyser", "laptop": "HP Laptop 15s",
    "tv": "Sony Bravia 55 inch LED TV", "printer": "Epson L3250 Printer",
}


def _user(name):
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=name).first():
            db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123"), email=f"{name}@example.com"))
            db.commit()


def _warranty(wid, owner, product, brand="Voltas", region=None, bought=datetime(2017, 4, 22)):
    _user(owner)
    with SessionLocal() as db:
        for model in (QuestionPackAnswerDB, WarrantyOwnerDB):
            db.query(model).filter_by(warranty_id=wid).delete()
        db.query(NotificationDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        alts = {"delivery_region": {**region, "consent": None}} if region else {}
        db.add(WarrantyDB(id=wid, brand=brand, product_name=product, purchase_date=bought, alternatives=alts, confidence={}))
        db.add(WarrantyOwnerDB(user_id=owner, warranty_id=wid))
        db.commit()


def _client(user=USER):
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": user, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _user(USER)


# --- packs ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("line", list(PRODUCTS))
def test_every_product_type_has_a_pack(line):
    pack = qp.pack_for(line)
    assert pack and 4 <= len(pack["questions"]) <= 8
    for q in pack["questions"]:
        assert q["why"] and len(q["why"]) < 130 and q["text"].endswith("?")
        assert q.get("kind") == "place" or len(q["options"]) >= 2


def test_ac_pack_covers_the_owners_list():
    ids = [q["id"] for q in qp.pack_for("air_conditioner")["questions"]]
    assert ids == ["region", "ac_hours", "ac_last_service", "ac_service_by", "ac_filter", "power", "problem", "ac_installer"]


def test_three_at_a_time_with_skip_and_why():
    _warranty("pack_w1", USER, PRODUCTS["air_conditioner"], region={"city": "Faridabad", "state": "Haryana"})
    client, headers = _client()
    first = client.get("/warranties/pack_w1/questions", headers=headers).json()
    assert first["pack"] == "air_conditioner" and len(first["questions"]) == 3 and first["answered"] == 0
    region_q = first["questions"][0]
    assert region_q["options"][0] == {"value": "invoice_place", "label": "Faridabad, Haryana (from your invoice)"}
    assert all(q["why"] for q in first["questions"])
    resp = client.post("/warranties/pack_w1/questions/answer", json={"question_id": "ac_hours", "answer": "skip"}, headers=headers)
    assert resp.status_code == 200
    nxt = client.get("/warranties/pack_w1/questions", headers=headers).json()
    assert "ac_hours" not in [q["id"] for q in nxt["questions"]] and nxt["answered"] == 0  # a skip is not an answer
    bad = client.post("/warranties/pack_w1/questions/answer", json={"question_id": "ac_hours", "answer": "lots"}, headers=headers)
    assert bad.status_code == 422


def test_choosing_the_invoice_city_is_consent_to_use_it():
    _warranty("pack_w2", USER, PRODUCTS["air_conditioner"], region={"city": "Faridabad", "state": "Haryana"})
    client, headers = _client()
    client.post("/warranties/pack_w2/questions/answer", json={"question_id": "region", "answer": "invoice_place"}, headers=headers)
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id="pack_w2").first()
        assert w.alternatives["delivery_region"]["consent"] is True and w.climate_zone == "hot"


# --- care risk wording (item 10) ----------------------------------------------------------------------------

def test_no_answers_is_never_low_risk():
    _warranty("pack_w3", USER, PRODUCTS["fridge"], brand="LG")
    client, headers = _client()
    risk = client.get("/warranties/pack_w3/care-risk", headers=headers).json()
    assert risk["status"] == "needs_answers" and risk["label"] is None
    assert risk["text"] == "Not enough information yet - answer 3 quick questions"
    assert risk["age_note"].startswith("Bought 22 Apr 2017 - about")


def test_all_skipped_is_still_not_enough():
    _warranty("pack_w4", USER, PRODUCTS["tv"], brand="Sony", bought=datetime(2025, 1, 1))
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id="pack_w4").first()
        for q in qp.questions_for(w)[:3]:
            qp.record_answer(db, USER, w, q["id"], "skip")
        assert qp.care_risk(db, USER, w, today=date(2025, 6, 1))["status"] == "needs_answers"


def test_answers_give_label_reasons_tips_and_one_reminder():
    _warranty("pack_w5", USER, PRODUCTS["air_conditioner"], bought=datetime(2024, 3, 1))
    client, headers = _client()
    for qid, answer in (("ac_hours", "gt12"), ("ac_last_service", "never"), ("ac_filter", "rarely"), ("problem", "none")):
        client.post("/warranties/pack_w5/questions/answer", json={"question_id": qid, "answer": answer}, headers=headers)
    risk = client.get("/warranties/pack_w5/care-risk", headers=headers).json()
    assert risk["status"] == "assessed" and risk["label"] == "HIGH" and risk["text"] == "Needs attention"
    assert risk["reasons"][0] in ("Runs more than 12 hours a day in summer", "Never serviced")
    assert any("filter" in t for t in risk["tips"])
    client.get("/warranties/pack_w5/care-risk", headers=headers)  # asked twice: one reminder only
    with SessionLocal() as db:
        assert db.query(NotificationDB).filter_by(warranty_id="pack_w5", type="care_pack_ac_service").count() == 1


def test_a_well_kept_product_is_low_and_says_so():
    _warranty("pack_w6", USER, PRODUCTS["smartphone"], brand="Samsung", bought=datetime(2025, 1, 10))
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id="pack_w6").first()
        for qid, answer in (("phone_charger", "original"), ("phone_case", "both"), ("phone_water", "no")):
            qp.record_answer(db, USER, w, qid, answer)
        risk = qp.care_risk(db, USER, w, today=date(2025, 6, 1))
    assert risk["label"] == "LOW" and risk["text"] == "Looking after it well"
    assert risk["reasons"] == ["Nothing in your answers points to a problem."]
    assert risk["age_note"] == "Bought 10 Jan 2025 - less than a year old."


def test_age_adds_to_the_reasons():
    _warranty("pack_w7", USER, PRODUCTS["washing_machine"], brand="Bosch", bought=datetime(2016, 1, 1))
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id="pack_w7").first()
        qp.record_answer(db, USER, w, "wm_loads", "lt4")
        risk = qp.care_risk(db, USER, w, today=date(2025, 6, 1))
    assert "About 9 years old" in risk["reasons"] and risk["label"] == "MEDIUM"


def test_pack_endpoints_need_the_owner():
    _warranty("pack_w8", USER, PRODUCTS["printer"], brand="Epson")
    _user("pack_stranger")
    client, headers = _client("pack_stranger")
    assert client.get("/warranties/pack_w8/questions", headers=headers).status_code == 403
    assert client.get("/warranties/pack_w8/care-risk", headers=headers).status_code == 403


# --- anonymous group counts for brands (consent, 10+) -------------------------------------------------------

def _answer_as(n, consent, answer="gt12"):
    user = f"pack_group_{n}"
    _warranty(f"pack_g{n}", user, PRODUCTS["air_conditioner"], brand="GroupCo")
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id=f"pack_g{n}").first()
        qp.record_answer(db, user, w, "ac_hours", answer)
        if consent is not None:
            qp.set_share_consent(db, user, consent)


def test_group_counts_need_consent_and_ten_people():
    with SessionLocal() as db:
        db.query(QuestionPackConsentDB).filter(QuestionPackConsentDB.user_id.like("pack_group_%")).delete(synchronize_session=False)
        db.commit()
    for n in range(9):
        _answer_as(n, True)
    _answer_as(9, False)          # said no
    _answer_as(10, None)          # never asked
    with SessionLocal() as db:
        assert qp.group_counts(db, brand="GroupCo", pack="air_conditioner", question_id="ac_hours")["available"] is False
    _answer_as(11, True, answer="lt4")
    with SessionLocal() as db:
        result = qp.group_counts(db, brand="groupco", pack="air_conditioner", question_id="ac_hours")
        assert result["available"] and result["customers"] == 10
        assert result["counts"] == {"More than 12 hours": 9, "Less than 4 hours": 1}
        assert qp.group_counts(db, brand="GroupCo", pack="air_conditioner", question_id="region")["available"] is False


def test_brand_counts_endpoint_is_for_brand_staff_only():
    client, headers = _client()
    assert client.get("/oem/question-insights?brand=GroupCo&pack=air_conditioner&question_id=ac_hours", headers=headers).status_code == 403


def test_share_consent_endpoint():
    client, headers = _client()
    assert client.post("/account/share-answers", json={"share": "yes"}, headers=headers).status_code == 422
    assert client.post("/account/share-answers", json={"share": False}, headers=headers).json() == {"share_anonymous": False}
    _warranty("pack_w9", USER, PRODUCTS["laptop"], brand="HP")
    assert client.get("/warranties/pack_w9/questions", headers=headers).json()["share_consent"] is False


def test_dashboard_wording():
    html = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")
    assert "Not enough information yet" in html and "Why we ask: " in html and "label: 'Skip'" in html
    assert "groups of 10 or more people" in html
    assert "const predStatus = careRiskStatus(careRisk);" in html  # the badge no longer comes from the model
