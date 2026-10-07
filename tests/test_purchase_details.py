"""Batch 3 item 4: price, capacity/size, star rating, type, and delivery city/state only (never the street),
with the customer's consent before the region is used for weather-based care tips."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import product_recommendations, purchase_details
from app.services.ingestion import extract_product_fields

FIXTURE = (Path(__file__).parent / "fixtures" / "invoices" / "amazon_2017_voltas_window_ac.txt").read_text(encoding="utf-8")
USER = "purchase_details_user"


def test_fixture_purchase_details_and_region():
    _f, _c, alt = extract_product_fields(FIXTURE)
    assert alt["purchase_details"] == {
        "price": {"amount": 22490.0, "currency": "INR", "from": "item row"},
        "capacity": "1.5 Ton", "star_rating": 3, "type": "window",
    }
    assert alt["delivery_region"] == {"city": "Faridabad", "state": "Haryana", "consent": None}
    # Nothing else of the address is kept in what we read.
    for private in ("Test Buyer", "Test Address", "121001"):
        assert private not in str(alt["delivery_region"]) and private not in str(alt["purchase_details"])


@pytest.mark.parametrize("product,expected", [
    ("LG 242 L 3 Star Frost-Free Double Door Refrigerator", {"capacity": "242 L", "star_rating": 3, "type": "double door"}),
    ("Bosch 7 kg 5 Star Inverter Front Load Washing Machine", {"capacity": "7 kg", "star_rating": 5, "type": "front load"}),
    ("Daikin 1.5 Ton 3 Star Inverter Split AC", {"capacity": "1.5 Ton", "star_rating": 3, "type": "split"}),
    ("Sony Bravia 139 cm (55 inches) 4K TV", {"capacity": "55 inch"}),
    ("Racold Eterno Pro 25L Vertical Storage Water Heater (Geyser)", {"capacity": "25 L", "type": "storage"}),
    ("Samsung Galaxy M17e 5G (6GB RAM, 128GB Storage)", {"capacity": "128 GB storage"}),
    ("Philips Mixer Grinder 750W", {"capacity": "750 W"}),
    ("Epson L3250 Printer", {}),
])
def test_specs_for_many_products(product, expected):
    assert purchase_details.product_specs(product) == expected


@pytest.mark.parametrize("text,amount", [
    ("1 Epson L 3250 Printer 84433240 1no 13,200.00 11,186.44", 13200.0),
    ("1 Samsung Galaxy M17e | B0GN1NNYXF ₹12,499.00 1 ₹12,499.00", 12499.0),
    ("Item: Redmi 13C\nGrand Total: INR 9,999.00", 9999.0),
])
def test_price(text, amount):
    item = "Epson L 3250 Printer" if "Epson" in text else ("Samsung Galaxy M17e" if "Samsung" in text else None)
    assert purchase_details.price_paid(text, item)["amount"] == amount


@pytest.mark.parametrize("text,region", [
    ("Shipping Address:\nRavi, 12 MG Road, Pune, Maharashtra 411001", {"city": "Pune", "state": "Maharashtra"}),
    ("Ship To\nA. Kumar\nFlat 3, Sector 21\nNoida, Uttar Pradesh - 201301", {"city": "Noida", "state": "Uttar Pradesh"}),
    ("Billing Address\nX, 4 Park Street, Kolkata, WEST BENGAL 700016", {"city": "Kolkata", "state": "West Bengal"}),
    ("Place of Supply: 06-HARYANA", {"city": None, "state": "Haryana"}),
    ("Deliver To: Plot 7, Sector 14, Haryana 122001", {"city": None, "state": "Haryana"}),  # street words: no city
    ("Sold by a shop in Pune", None),
])
def test_delivery_region_is_city_and_state_only(text, region):
    assert purchase_details.delivery_region(text) == region


def test_climate_tip_only_with_consent():
    region = {"city": "Faridabad", "state": "Haryana", "consent": None}
    assert purchase_details.climate_tip("air_conditioner", region) is None
    assert purchase_details.climate_tip("air_conditioner", {**region, "consent": False}) is None
    assert "filter" in purchase_details.climate_tip("air_conditioner", {**region, "consent": True})
    assert purchase_details.climate_tip("fridge", {"city": "Chennai", "state": "Tamil Nadu", "consent": True})


def _setup(wid, region):
    with SessionLocal() as db:
        if not db.query(UserDB).filter_by(username=USER).first():
            db.add(UserDB(username=USER, role="user", hashed_password=hash_password("secret123"), email="pd@example.com"))
        db.query(WarrantyOwnerDB).filter_by(warranty_id=wid).delete()
        db.query(WarrantyDB).filter_by(id=wid).delete()
        db.add(WarrantyDB(id=wid, brand="Voltas", product_name="Voltas 1.5 Ton 3 Star Window AC",
                          alternatives={"delivery_region": region}, confidence={}))
        db.add(WarrantyOwnerDB(user_id=USER, warranty_id=wid))
        db.commit()
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": USER, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_consent_endpoint_sets_and_clears_climate(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client, headers = _setup("wty_region_1", {"city": "Faridabad", "state": "Haryana", "consent": None})
    resp = client.post("/warranties/wty_region_1/region-consent", json={"use": True}, headers=headers)
    assert resp.status_code == 200 and resp.json()["climate_zone"] == "hot"
    assert resp.json()["delivery_region"]["consent"] is True
    resp = client.post("/warranties/wty_region_1/region-consent", json={"use": False}, headers=headers)
    assert resp.json()["climate_zone"] is None and resp.json()["delivery_region"]["consent"] is False
    assert client.post("/warranties/wty_region_1/region-consent", json={"use": "yes"}, headers=headers).status_code == 422


def test_consent_needs_the_owner(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _setup("wty_region_2", {"city": "Pune", "state": "Maharashtra", "consent": None})
    other = TestClient(app)
    assert other.post("/warranties/wty_region_2/region-consent", json={"use": True}).status_code == 401


def test_care_tips_use_the_region_only_after_yes():
    warranty = {"product_name": "Voltas 1.5 Ton 3 Star Window AC",
                "alternatives": {"delivery_region": {"city": "Faridabad", "state": "Haryana", "consent": None}}}
    recs = product_recommendations.build_product_recommendations("u", "w", warranty=warranty)
    assert not any(r["product_id"].startswith("climate_") for r in recs)
    warranty["alternatives"]["delivery_region"]["consent"] = True
    recs = product_recommendations.build_product_recommendations("u", "w", warranty=warranty)
    assert recs[0]["product_id"] == "climate_air_conditioner" and "Faridabad" in recs[0]["title"]


def test_dashboard_asks_before_using_the_region():
    html = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")
    assert "May we use this city and state for weather-based care tips?" in html
    assert "never your street address" in html and "/region-consent" in html
