"""Run 3 item 9: care guides from the brand's own manual/FAQ - sourced, grounded, saved once per model."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import CareGuideDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import care_guides

OWNER, OTHER = "care_owner_user", "care_other_user"

GUIDES = [  # a mix of product types and brands, model and product-line scope
    {"company": "Samsung", "model_code": "SM-M175F", "source_kind": "manual",
     "source_url": "https://www.samsung.com/in/support/model/SM-M175FZBGINS/", "tips": [
         {"text": "Do not expose the device to water.", "quote": "Do not expose the device to water or other liquids.", "page": "12"}]},
    {"company": "LG", "product_line": "fridge", "source_kind": "faq",
     "source_url": "https://www.lg.com/in/support/help-library/refrigerator-cleaning", "tips": [
         {"text": "Clean the door gasket regularly.", "quote": "Clean the door gasket regularly with mild soapy water."}]},
    {"company": "Epson", "model_code": "L3250", "source_kind": "manual",
     "source_url": "https://www.epson.co.in/Support/Printers/L3250/s/SPT_C11CJ67511", "tips": [
         {"text": "Print a page at least once a month.", "quote": "Print a page at least once a month to keep the print head in good condition."}]},
]


def _client(user):
    client = TestClient(app)
    password = "admin123" if user == "admin" else "secret123"
    token = client.post("/auth/login", data={"username": user, "password": password}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        db.query(CareGuideDB).filter(CareGuideDB.company.in_(["Samsung", "LG", "Epson"])).delete(synchronize_session=False)
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([OWNER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_care_%")).delete(synchronize_session=False)
        for user in (OWNER, OTHER):
            if not db.query(UserDB).filter_by(username=user).first():
                db.add(UserDB(username=user, role="user", hashed_password=hash_password("secret123")))
        for wid, brand, name, model in (("wty_care_phone", "Samsung", "Galaxy M17e", "SM-M175F"),
                                        ("wty_care_fridge", "LG", "LG Double Door Refrigerator", "GL-T292RPZY"),
                                        ("wty_care_printer", "Epson", "EcoTank L3250 Printer", "L3250"),
                                        ("wty_care_tv", "Sony", "Bravia TV", "KD-55X74L")):
            db.add(WarrantyDB(id=wid, brand=brand, product_name=name, model_code=model, purchase_date=datetime(2026, 1, 1),
                              coverage_months=12, alternatives={}, terms=[], exclusions=[], claim_steps=[]))
            db.add(WarrantyOwnerDB(user_id=OWNER, warranty_id=wid))
        db.commit()


@pytest.mark.parametrize("text,quote,ok", [
    ("Do not expose the device to water.", "Do not expose the device to water or other liquids.", True),
    ("Avoid water and drops.", "Do not expose the device to water or other liquids.", False),  # "drops" invented
    ("Clean the filter every two weeks.", "Clean the air filter every two weeks.", True),
    ("Clean the filter every week.", "Clean the air filter every two weeks.", False),  # changes the interval
])
def test_tip_may_shorten_but_not_add_to_its_quote(text, quote, ok):
    assert care_guides.grounded_tip(text, quote) is ok


def test_admin_saves_guides_and_customers_see_sourced_tips():
    admin, auth = _client("admin")
    for guide in GUIDES:
        resp = admin.post("/admin/care-guides", json=guide, headers=auth)
        assert resp.status_code == 200, resp.text
    again = admin.post("/admin/care-guides", json=GUIDES[0], headers=auth)  # researched once: replaced, not added
    assert again.json()["id"] == admin.get("/admin/care-guides", headers=auth).json()["guides"][
        [g["company"] for g in admin.get("/admin/care-guides", headers=auth).json()["guides"]].index("Samsung")]["id"]
    owner, owner_auth = _client(OWNER)
    expected = {
        "wty_care_phone": ("Do not expose the device to water.", "From Samsung's user manual, page 12"),
        "wty_care_fridge": ("Clean the door gasket regularly.", "From LG's FAQ"),            # product-line guide
        "wty_care_printer": ("Print a page at least once a month.", "From Epson's user manual"),
    }
    for wid, (title, label) in expected.items():
        recs = owner.get(f"/recommendations?warranty_id={wid}", headers=owner_auth).json()["product_recommendations"]
        tip = next(r for r in recs if r["product_id"].startswith("care_guide_"))
        assert tip["title"] == title and tip["source_label"] == label and tip["source_url"].startswith("https://")
        assert tip["action"] == "oem_derived_care" and tip["why"].startswith("“")
    recs = owner.get("/recommendations?warranty_id=wty_care_tv", headers=owner_auth).json()["product_recommendations"]
    assert not any(r["product_id"].startswith("care_guide_") for r in recs)  # no guide for this model: nothing invented


@pytest.mark.parametrize("change,detail", [
    ({"source_url": "https://some-blog.example.com/samsung-tips"}, "verified official website"),
    ({"company": "Nonexistent Brand"}, "OEM registry"),
    ({"model_code": None}, "model_code or product_line"),
    ({"tips": [{"text": "Never charge overnight.", "quote": "Do not expose the device to water."}]}, "says more than its quote"),
    ({"tips": [{"text": "Keep it dry."}]}, "exact quote"),
    ({"source_kind": "blog"}, "manual or faq"),
])
def test_bad_guides_are_refused(change, detail):
    admin, auth = _client("admin")
    payload = {**GUIDES[0], **change}
    resp = admin.post("/admin/care-guides", json=payload, headers=auth)
    assert resp.status_code == 422 and detail in resp.json()["detail"]


def test_customers_cannot_save_guides_or_read_others_recommendations():
    owner, auth = _client(OWNER)
    assert owner.post("/admin/care-guides", json=GUIDES[0], headers=auth).status_code in (401, 403)
    other, other_auth = _client(OTHER)
    assert other.get("/recommendations?warranty_id=wty_care_phone", headers=other_auth).status_code == 403
    assert other.get(f"/recommendations?user_id={OWNER}", headers=other_auth).status_code == 403


def test_terms_based_care_tips_reach_the_page_with_their_action():
    """The API used to replace each tip's action with the product category, so the page (which shows
    action == "oem_derived_care") hid every terms-based tip."""
    with SessionLocal() as db:
        w = db.query(WarrantyDB).filter_by(id="wty_care_tv").one()
        w.exclusions = ["Damage caused by lightning or abnormal voltage is not covered."]
        db.commit()
    owner, auth = _client(OWNER)
    recs = owner.get("/recommendations?warranty_id=wty_care_tv", headers=auth).json()["product_recommendations"]
    care = [r for r in recs if r["action"] == "oem_derived_care"]
    assert care and care[0]["source_label"] == "From the warranty exclusions" and care[0]["why"]
