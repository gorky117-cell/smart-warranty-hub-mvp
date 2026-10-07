"""Question and care packs: every pack loads with all parts and follows the content rules; drafts are never shown
to customers, approved packs are; answers feed tips, reminders, risk reasons and anonymous group counts."""

import json
import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import CarePackAnswerDB, CarePackDB, NotificationDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import care_packs
from app.services.reminders import refresh_care_reminders

PACK_TYPES = care_packs.product_types()
USER, OTHER = "pack_owner_user", "pack_other_user"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    care_packs.reset_cache()
    with SessionLocal() as db:
        db.query(CarePackDB).delete()
        db.query(CarePackAnswerDB).delete()
        db.query(NotificationDB).filter(NotificationDB.user_id.in_([USER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([USER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_pk_%")).delete(synchronize_session=False)
        for name in (USER, OTHER):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123")))
        db.add(WarrantyDB(id="wty_pk_ac", brand="Voltas", product_name="Voltas 1.5 Ton Inverter Split AC", model_code="183V",
                          purchase_date=datetime.utcnow() - timedelta(days=90), coverage_months=12, alternatives={}))
        db.add(WarrantyOwnerDB(user_id=USER, warranty_id="wty_pk_ac"))
        db.commit()
    yield
    care_packs.reset_cache()


# --- every pack file ----------------------------------------------------------------------------------------

def test_packs_exist():
    assert "air_conditioner" in PACK_TYPES


@pytest.mark.parametrize("ptype", PACK_TYPES)
def test_pack_loads_with_all_parts_and_follows_the_rules(ptype):
    pack = care_packs.file_pack(ptype)
    assert pack["status"] == "draft"  # every pack ships as a draft
    assert care_packs.validate(pack) == []


@pytest.mark.parametrize("ptype", PACK_TYPES)
def test_no_warranty_numbers_brand_names_or_repair_steps(ptype):
    pack = care_packs.file_pack(ptype)
    for part in pack["warranty_structure"]:
        assert not re.search(r"\d", part["part"] + part["note"]) and "warranty card" in part["note"].lower()
    for item in pack["exclusions_to_look_for"]:
        assert not re.search(r"\d", item)
    assert care_packs.content_rule_problems(pack) == []


@pytest.mark.parametrize("ptype", PACK_TYPES)
def test_hazardous_products_put_safety_first(ptype):
    pack = care_packs.file_pack(ptype)
    if not pack["hazards"]:
        return
    tips = pack["care_tips"]
    assert tips[0]["safety"]
    safety = " ".join(t["text"].lower() for t in tips if t.get("safety"))
    if "electric" in pack["hazards"]:
        assert "switch off" in safety or "unplug" in safety
    if "gas" in pack["hazards"]:
        assert "smell gas" in safety and "ventilat" in safety and "service number" in safety
    if "battery" in pack["hazards"]:
        assert "swell" in safety or "battery" in safety


@pytest.mark.parametrize("bad,problem", [
    ({"warranty_structure": [{"part": "Compressor", "note": "Usually 10 years - check your warranty card."}]}, "no numbers"),
    ({"exclusions_to_look_for": ["Damage after 2 years"]}, "no numbers"),
    ({"care_tips_extra": {"id": "x", "priority": "LOW", "text": "Unscrew the panel to clean it.", "why": "x", "trigger": {"always": True}}}, "repair instruction"),
    ({"care_tips_extra": {"id": "y", "priority": "LOW", "text": "Samsung recommends a soft cloth.", "why": "x", "trigger": {"always": True}}}, "brand name"),
    ({"care_tips_extra": {"id": "z", "priority": "LOW", "text": "The warranty lasts 5 years.", "why": "x", "trigger": {"always": True}}}, "warranty period"),
])
def test_rule_checks_catch_bad_content(bad, problem):
    pack = care_packs.file_pack("air_conditioner")
    extra = bad.pop("care_tips_extra", None)
    pack.update(bad)
    if extra:
        pack["care_tips"] = pack["care_tips"][:-1] + [extra]
    assert any(problem in p for p in care_packs.validate(pack))


def test_matching_by_name_then_product_line():
    assert care_packs.match_type("Voltas 1.5 Ton Inverter Split AC", "183V") == "air_conditioner"
    assert care_packs.match_type("Daikin 1.5 Ton 3 Star Split AC", "FTKL50U") == "air_conditioner"
    assert care_packs.match_type("Some unknown thing", None) is None


# --- customers see approved packs only ----------------------------------------------------------------------

def _client(user=USER):
    client = TestClient(app)
    password = "admin123" if user == "admin" else "secret123"
    token = client.post("/auth/login", data={"username": user, "password": password}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_draft_pack_is_never_shown_to_customers():
    client, auth = _client()
    assert client.get("/warranties/wty_pk_ac/care-questions", headers=auth).json()["questions"] == []
    assert client.get("/warranties/wty_pk_ac/care-insights", headers=auth).json() == {"product_type": None}
    resp = client.post("/warranties/wty_pk_ac/care-answers", json={"question_id": "hours_per_day", "answer": "over_8h"}, headers=auth)
    assert resp.status_code == 422
    recs = client.get("/recommendations?warranty_id=wty_pk_ac", headers=auth).json()["product_recommendations"]
    assert not any(r.get("action") == "care_pack" for r in recs)
    assert any(r.get("action") == "general_care" for r in recs)  # the existing general tips stay


def test_approved_pack_asks_three_at_a_time_and_answers_shape_tips_and_risks():
    admin, admin_auth = _client("admin")
    assert admin.post("/admin/care-packs/air_conditioner/approve", headers=admin_auth).status_code == 200
    client, auth = _client()
    first = client.get("/warranties/wty_pk_ac/care-questions", headers=auth).json()
    assert len(first["questions"]) == 3 and all(q["why"] and q["can_skip"] for q in first["questions"])
    for qid, answer in (("hours_per_day", "over_8h"), ("filter_cleaning", "rarely"), ("voltage_issues", "skip")):
        assert client.post("/warranties/wty_pk_ac/care-answers", json={"question_id": qid, "answer": answer}, headers=auth).status_code == 200
    second = client.get("/warranties/wty_pk_ac/care-questions", headers=auth).json()
    assert [q["id"] for q in second["questions"]] == ["stabilizer", "outdoor_unit", "last_service"]  # skipped is not asked again
    view = client.get("/warranties/wty_pk_ac/care-insights", headers=auth).json()
    tips = [t["id"] for t in view["care_tips"]]
    assert tips[:2] == ["power_off_cleaning", "no_opening"] and "clean_filters" in tips and "stable_power" not in tips
    assert {r["reason"] for r in view["risk_reasons"]} == {"Long daily running wears parts faster.", "Dirty filters make the AC work harder."}
    assert view["warranty_structure"] and view["exclusions_to_look_for"]
    recs = client.get("/recommendations?warranty_id=wty_pk_ac", headers=auth).json()["product_recommendations"]
    pack_recs = [r for r in recs if r.get("action") == "care_pack"]
    assert pack_recs and pack_recs[0]["safety"] and not any(r.get("action") == "general_care" for r in recs)
    bad = client.post("/warranties/wty_pk_ac/care-answers", json={"question_id": "hours_per_day", "answer": "forever"}, headers=auth)
    assert bad.status_code == 422


def test_other_users_cannot_use_someone_elses_product():
    admin, admin_auth = _client("admin")
    admin.post("/admin/care-packs/air_conditioner/approve", headers=admin_auth)
    other, auth = _client(OTHER)
    assert other.get("/warranties/wty_pk_ac/care-questions", headers=auth).status_code == 403


def test_pack_reminders_once_per_interval_for_approved_packs_only():
    with SessionLocal() as db:
        refresh_care_reminders(db)
        assert db.query(NotificationDB).filter_by(user_id=USER).count() == 0  # draft: nothing
        care_packs.set_status(db, "air_conditioner", "approved", admin="admin")
        refresh_care_reminders(db)
        refresh_care_reminders(db)
        types = sorted(n.type for n in db.query(NotificationDB).filter_by(user_id=USER).all())
        msg = db.query(NotificationDB).filter_by(user_id=USER, type="care_pack_air_conditioner_filter_clean").one().message
    assert types == ["care_pack_air_conditioner_filter_clean", "care_pack_air_conditioner_service_visit"]
    assert "About every 2 weeks" in msg and "manual" in msg


# --- admin review, edit, approve, audit ---------------------------------------------------------------------

def test_admin_edit_returns_to_draft_and_everything_is_audited():
    admin, auth = _client("admin")
    admin.post("/admin/care-packs/air_conditioner/approve", headers=auth)
    pack = admin.get("/admin/care-packs/air_conditioner", headers=auth).json()["pack"]
    pack["care_tips"][-1]["text"] = "Pick a moderate temperature instead of the coldest setting."
    for key in ("approved_by", "approved_at"):
        pack.pop(key, None)
    edited = admin.put("/admin/care-packs/air_conditioner", json=pack, headers=auth)
    assert edited.status_code == 200 and edited.json()["status"] == "draft"
    bad = dict(pack, warranty_structure=[{"part": "Compressor", "note": "10 years - check your warranty card"}])
    assert admin.put("/admin/care-packs/air_conditioner", json=bad, headers=auth).status_code == 422
    detail = admin.get("/admin/care-packs/air_conditioner", headers=auth).json()
    assert detail["pack"]["care_tips"][-1]["text"].startswith("Pick a moderate")
    actions = [a["action"] for a in detail["audit"]]
    assert "care_pack_edit" in actions and "care_pack_approve" in actions
    listing = admin.get("/admin/care-packs", headers=auth).json()["packs"]
    assert any(p["product_type"] == "air_conditioner" and p["status"] == "draft" for p in listing)


def test_admin_only():
    client, auth = _client()
    assert client.get("/admin/care-packs", headers=auth).status_code in (401, 403)
    assert client.post("/admin/care-packs/air_conditioner/approve", headers=auth).status_code in (401, 403)
    assert client.get("/oem/care-packs/air_conditioner/groups", headers=auth).status_code in (401, 403)


# --- anonymous group counts ---------------------------------------------------------------------------------

def test_group_counts_need_ten_consenting_people():
    with SessionLocal() as db:
        care_packs.set_status(db, "air_conditioner", "approved", admin="admin")
        names = [f"pack_group_{i}" for i in range(12)]
        for i, name in enumerate(names):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password="x", consent_analytics=0 if i < 3 else 1))
        db.commit()
        for i, name in enumerate(names):  # 12 answer; 3 of them do not allow analytics -> 9 counted
            db.add(CarePackAnswerDB(user_id=name, warranty_id=f"w{i}", product_type="air_conditioner",
                                    question_id="hours_per_day", answer="over_8h" if i % 2 else "4_8h"))
        db.commit()
        assert care_packs.group_counts(db, "air_conditioner")["questions"] == {}  # 9 < 10: hidden
        db.query(UserDB).filter(UserDB.username == names[0]).update({"consent_analytics": 1})
        db.commit()
        counts = care_packs.group_counts(db, "air_conditioner")["questions"]
    assert counts == {"hours_per_day": {"over_8h": 5, "4_8h": 5}}


def test_review_worksheet_lists_every_pack():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import care_packs_review

    text = care_packs_review.build()
    for ptype in PACK_TYPES:
        assert f"## {care_packs.file_pack(ptype)['label']}" in text
    assert "| Approve |" in text


@pytest.mark.parametrize("name,expected", [
    ("Voltas 1.5 Ton Inverter Split AC", "air_conditioner"), ("LG 242 L Frost Free Smart Inverter Refrigerator", "refrigerator"),
    ("IFB Front Load Washing Machine", "washing_machine"), ("Racold Eterno Pro Geyser", "water_heater"),
    ("Sony Bravia 55 inch LED TV", "television"), ("Redmi 13C (4GB RAM, 128GB Storage)", "smartphone"),
    ("HP Laptop 15s", "laptop"), ("Samsung Galaxy Tab A9", "tablet"), ("Epson EcoTank L3250 Printer", "printer"),
    ("Havells Ceiling Fan", "ceiling_fan"), ("Symphony Air Cooler", "air_cooler"), ("Bajaj Room Heater", "room_heater"),
    ("Philips Mixer Grinder HL7756", "mixer_grinder"), ("Philips Air Fryer", "air_fryer"), ("Kent RO Water Purifier", "water_purifier"),
    ("Pigeon Induction Cooktop", "induction_cooktop"), ("Prestige Gas Stove 3 Burner", "gas_stove"),
    ("Faber Kitchen Chimney", "kitchen_chimney"), ("Luminous Inverter Battery", "inverter_battery"),
    ("V-Guard Voltage Stabilizer", "voltage_stabilizer"), ("TP-Link Wi-Fi Router", "wifi_router"),
    ("Noise Smartwatch", "smartwatch"), ("boAt Airdopes TWS Earbuds", "earphones_headphones"),
    ("Ambrane Power Bank 20000mAh", "power_bank_charger"), ("JBL Bluetooth Speaker", "speaker_soundbar"),
    ("Morphy Richards Steam Iron", "iron_steamer"), ("Eureka Robot Vacuum", "vacuum_cleaner"),
    ("Bajaj Electric Kettle", "kettle_toaster"), ("LG Microwave Oven", "microwave_otg"), ("Dyson Air Purifier", "air_purifier"),
    ("Daikin Inverter AC FTKL50U", "air_conditioner"), ("Bosch Inverter Washing Machine", "washing_machine"),
])
def test_every_product_type_finds_its_pack(name, expected):
    assert care_packs.match_type(name, None) == expected


def test_there_are_thirty_packs():
    assert len(PACK_TYPES) == 30
