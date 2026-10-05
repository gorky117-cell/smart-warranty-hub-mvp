"""Run 3 item 7: 'Your warranty in 5 lines', grounded, with 'please confirm' where unsure; warranty types."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import DocumentDB, ParsedFieldDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services.warranty_card import detect_types, five_lines

TODAY = date(2026, 10, 5)


def _w(**kw):
    base = dict(id="wty_x", brand="Samsung", product_name="Galaxy M17e", model_code="SM-M175F", serial_no="",
                purchase_date=datetime(2026, 5, 3), coverage_months=12, expiry_date=None, alternatives={},
                terms=["Samsung warrants the product against manufacturing defects; parts are repaired or replaced free of charge."],
                exclusions=["Damage caused by lightning, abnormal voltage or liquid is not covered."],
                claim_steps=["Repairs are carried out at a Samsung authorized service center."])
    base.update(kw)
    return SimpleNamespace(**base)


CONFIRMED = {"status": "confirmed"}


def _text(card):
    return [line["text"] for line in card["lines"]]


def test_five_lines_for_an_in_warranty_phone():
    card = five_lines(_w(), CONFIRMED, {"id": "doc_1", "kind_label": "Invoice / bill", "filename": "bill.pdf", "available": True}, today=TODAY)
    lines = _text(card)
    assert lines[0] == "Covered until 3 May 2027 (6 months left)."
    assert lines[1].startswith("Covered: Samsung warrants the product against manufacturing defects")
    assert lines[2] == "Not covered: Damage from lightning or abnormal voltage is not covered. Damage from liquid is not covered."
    assert lines[3] == "If it breaks: Repairs are done at Samsung authorized service centres."
    assert lines[4] == "Your original invoice / bill: bill.pdf" and card["lines"][4]["url"] == "/documents/doc_1/file"
    assert not any(line["confirm"] for line in card["lines"]) and card["please_confirm"] == [] and not card["estimated"]


def test_everything_unknown_is_please_confirm_never_a_guess():
    card = five_lines(_w(brand="", purchase_date=None, coverage_months=None, terms=[], exclusions=[], claim_steps=[]),
                      {"status": "not_confirmed"}, None, today=TODAY)
    lines = _text(card)
    assert lines[0].startswith("Please confirm your purchase date")
    assert lines[1].startswith("Please confirm what is covered") and lines[2].startswith("Please confirm what is not covered")
    assert lines[3] == "If it breaks: contact the seller with your invoice and serial number."
    assert lines[4].startswith("Your original invoice is not saved here yet")
    assert all(line["confirm"] for line in card["lines"]) and "purchase date" in card["please_confirm"]


def test_estimated_terms_and_unknown_brand_are_tagged():
    card = five_lines(_w(), {"status": "estimated"}, None, today=TODAY)
    assert card["estimated"] and card["lines"][1]["tag"] == "Estimated, please check" and card["lines"][1]["confirm"]
    card = five_lines(_w(brand=None), CONFIRMED, None, today=TODAY)
    assert card["estimated"]


def test_expired_and_pending_suggestions():
    card = five_lines(_w(purchase_date=datetime(2023, 1, 5),
                         alternatives={"serial_suggestion": {"value": "123", "status": "pending"},
                                       "vision_suggestions": {"purchase_date": {"status": "pending"}}}), CONFIRMED, None, today=TODAY)
    assert _text(card)[0] == "Expired on 5 Jan 2024."
    assert card["please_confirm"] == ["serial number", "purchase date"]


# --- warranty types (global rule), each grounded in the sentence it came from ---------------------------------

TYPE_CASES = [
    ("part_period", "fridge", "", ["The compressor is covered for 10 years from the date of purchase."], "Compressor: 10 years"),
    ("part_period", "AC", "", ["Warranty: 1 year on the product and 5 years on the compressor."], "Compressor: 5 years"),
    ("part_period", "phone", "", ["Accessories such as the charger are covered for 6 months."], "Accessories: 6 months"),
    ("part_period", "TV", "", ["The display panel carries a warranty of two years."], "Display panel: 2 years"),
    ("extended_plan", "laptop", "1 HP Laptop 15s\n2 Extended Warranty 2 Years (HP Care Pack) 3,499.00", [], None),
    ("extended_plan", "phone", "Samsung Care+ Accidental Damage Protection Plan 1 Yr", [], None),
    ("pro_rata", "inverter battery", "", ["Warranty: 36 months (18 months free replacement + 18 months pro-rata)."], None),
    ("starts_at_installation", "AC", "", ["The warranty period starts from the date of installation."], None),
    ("registration_required", "water purifier", "", ["Product registration within 30 days is mandatory to avail the warranty."], None),
    ("on_site", "washing machine", "", ["Service will be provided at your home by an authorized technician."], None),
    ("carry_in", "phone", "", ["Carry-in warranty: bring the product to the nearest service centre."], None),
    ("seller_warranty", "small appliance", "Warranty provided by the seller: 6 months shop warranty", [], None),
    ("no_warranty", "printer", "Item sold as is. No warranty.", [], None),
    ("refurbished", "phone", "Apple iPhone 12 (Renewed) 64GB", [], None),
    ("international", "camera", "", ["This product carries an international warranty."], None),
]


@pytest.mark.parametrize("kind,product,invoice,terms,text", TYPE_CASES)
def test_warranty_types_are_found_with_their_source(kind, product, invoice, terms, text):
    found = [t for t in detect_types(invoice, terms, []) if t["type"] == kind]
    assert found, (kind, product)
    assert found[0]["source_sentence"]
    if text:
        assert any(t["text"] == text for t in found)


@pytest.mark.parametrize("terms", [
    ["Warranty does not cover consumables; no warranty applies to the remote batteries."],  # a limit, not "no warranty"
    ["Damage if the product is used commercially is not covered."],                        # not "refurbished"
    ["Extended warranty is available at extra cost."],                                     # offered, not bought
])
def test_no_false_types_from_ordinary_terms(terms):
    kinds = {t["type"] for t in detect_types("", terms, [])}
    assert not kinds & {"no_warranty", "refurbished", "extended_plan"}


def test_installation_start_and_no_warranty_change_the_first_line():
    card = five_lines(_w(terms=["The warranty period starts from the date of installation."]), CONFIRMED, None, today=TODAY)
    assert "counted from installation - please confirm the installation date" in card["lines"][0]["text"] and card["lines"][0]["confirm"]
    card = five_lines(_w(coverage_months=None), CONFIRMED, None, invoice_text="Open box item sold as is. No warranty.", today=TODAY)
    assert card["lines"][0]["text"] == "Your invoice says there is no warranty for this product."
    assert {"no_warranty", "refurbished"} <= {x["type"] for x in card["extras"]}


# --- endpoint and page --------------------------------------------------------------------------------------

def test_endpoint_owner_sees_card_other_user_denied(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        for user in ("five_owner", "five_other"):
            if not db.query(UserDB).filter_by(username=user).first():
                db.add(UserDB(username=user, role="user", hashed_password=hash_password("secret123")))
        db.query(WarrantyOwnerDB).filter_by(warranty_id="wty_five_1").delete()
        db.query(ParsedFieldDB).filter_by(warranty_id="wty_five_1").delete()
        db.query(DocumentDB).filter_by(warranty_id="wty_five_1").delete()
        db.query(WarrantyDB).filter_by(id="wty_five_1").delete()
        db.add(WarrantyDB(id="wty_five_1", brand="LG", product_name="LG Refrigerator", model_code="GL-T292RPZY",
                          purchase_date=datetime(2026, 1, 9), coverage_months=12, alternatives={},
                          terms=["LG warrants this refrigerator against manufacturing defects.",
                                 "The compressor is covered for 10 years."],
                          exclusions=["Damage due to voltage fluctuation is not covered."], claim_steps=[]))
        db.add(ParsedFieldDB(warranty_id="wty_five_1", raw_text="Vijay Sales\nLG Refrigerator GL-T292RPZY\nInstallation and demo free"))
        db.add(WarrantyOwnerDB(user_id="five_owner", warranty_id="wty_five_1"))
        db.commit()

    def client(user):
        c = TestClient(app)
        token = c.post("/auth/login", data={"username": user, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
        return c, {"Authorization": f"Bearer {token}"}

    owner, auth = client("five_owner")
    card = owner.get("/warranties/wty_five_1/five-lines", headers=auth).json()
    assert len(card["lines"]) == 5 and card["lines"][0]["text"].startswith("Covered until 9 Jan 2027")
    assert any(x["text"] == "Compressor: 10 years" for x in card["extras"])
    other, other_auth = client("five_other")
    assert other.get("/warranties/wty_five_1/five-lines", headers=other_auth).status_code == 403
    owner.post("/auth/login", data={"username": "five_owner", "password": "secret123"})
    html = owner.get("/ui/neo-dashboard").text
    assert "Your warranty in 5 lines" in html and "loadFiveLines(warrantyId);" in html
