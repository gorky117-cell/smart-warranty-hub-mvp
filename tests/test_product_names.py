"""Run 3 item 8: products shown by short names (and nicknames), told apart, without internal IDs."""

import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import ProductNicknameDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import customer_content, product_naming
from app.services.product_recommendations import infer_product_category

# (brand, marketplace/shop title, model) -> expected short name. Mix of types and brands.
NAMES = [
    ("Samsung", "Samsung Galaxy M17e 5G (Blitz Blue, 6GB RAM, 128GB Storage) | 50MP Camera", "SM-M175F", "Samsung Galaxy M17e 5G"),
    ("HP", "HP Laptop 15s, 12th Gen Intel Core i5-1235U, 15.6-inch (39.6 cm), FHD, 16GB DDR4", "15s-fq5111TU", "HP Laptop 15s"),
    ("Sony", "Sony Bravia 139 cm (55 inches) 4K Ultra HD Smart LED Google TV KD-55X74L (Black)", "KD-55X74L", "Sony Bravia KD-55X74L"),
    ("LG", "LG 242 L 3 Star Frost-Free Smart Inverter Double Door Refrigerator (GL-T292RPZY, Dazzle Steel)", "GL-T292RPZY", "LG GL-T292RPZY Refrigerator"),
    ("Voltas", "Voltas 1.5 Ton 3 Star Inverter Split AC (Copper, 183V Vectra Elite, White)", "183V", "Voltas Inverter Split AC"),
    ("IFB", "IFB 7 Kg 5 Star Front Load Washing Machine", "Senator WXS", "IFB Front Load Washing Machine"),
    ("Racold", "Racold Eterno Pro 25L Vertical Storage Water Heater (Geyser)", "ETERNO PRO 25", "Racold ETERNO PRO 25 Geyser"),
    ("Bajaj", "Mixer Grinder", "GX 3701", "Bajaj Mixer Grinder"),
    ("Epson", "EcoTank L3250 A4 Wi-Fi All-in-One Ink Tank Printer", "L3250", "Epson L3250 Printer"),
    ("Apple", "iPhone 15 (128 GB) - Black", "MTP03HN/A", "Apple iPhone 15"),
    ("Xiaomi", "Redmi 13C (Starry Black, 4GB RAM, 128GB Storage)", "13C", "Xiaomi Redmi 13C"),
    ("Acmeco", None, "ZX-100", "Acmeco ZX-100"),  # shop invoice with no title
    (None, "Product", None, "Your product"),        # nothing known: never an ID
]


@pytest.mark.parametrize("brand,title,model,expected", NAMES)
def test_short_names_for_a_mix_of_products(brand, title, model, expected):
    name = product_naming.short_name(brand, title, model)
    assert name == expected
    assert not re.search(r"wty_|\(|\||\bGB\b|\bRAM\b", name)


@pytest.mark.parametrize("name,line", [
    ("LG 242 L Frost-Free Smart Inverter Double Door Refrigerator", "fridge"),
    ("Voltas 1.5 Ton Inverter Split AC", "air_conditioner"),
    ("Bosch Inverter Washing Machine", "washing_machine"),
    ("Luminous Zelio+ 1100 Inverter", "inverter"),
    ("APC Back-UPS 600VA", "inverter"),
    ("Measuring Cups Set", "general"),
])
def test_inverter_is_a_product_only_when_no_appliance_is_named(name, line):
    assert infer_product_category({"product_name": name}) == line


def test_second_line_icon_and_ref():
    d = product_naming.describe(warranty_id="wty_ab12cd34", brand="Samsung", product_name="Galaxy M17e", model_code="SM-M175F",
                                purchase_date=datetime(2026, 5, 3), alternatives={"seller": ["APPARIO RETAIL PRIVATE LTD"]})
    assert d["subtitle"] == "Bought 3 May 2026 from Appario Retail Private Ltd"
    assert d["icon"] == "📱" and re.fullmatch(r"[0-9A-F]{6}", d["support_ref"])
    assert product_naming.describe(warranty_id="x", brand=None, product_name="Ceiling fan", model_code=None,
                                   purchase_date=None)["subtitle"] == "Purchase date not known yet"


USER, OTHER = "names_owner_user", "names_other_user"


def _reset():
    with SessionLocal() as db:
        db.query(ProductNicknameDB).filter(ProductNicknameDB.user_id.in_([USER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([USER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter(WarrantyDB.id.like("wty_nm_%")).delete(synchronize_session=False)
        for name in (USER, OTHER):
            if not db.query(UserDB).filter_by(username=name).first():
                db.add(UserDB(username=name, role="user", hashed_password=hash_password("secret123")))
        rows = [  # two identical phones bought the same day from the same shop, one bought later, a fridge
            ("wty_nm_1", "Samsung", "Samsung Galaxy M17e 5G (Blue, 6GB RAM)", "SM-M175F", datetime(2026, 5, 3), datetime(2026, 5, 4)),
            ("wty_nm_2", "Samsung", "Samsung Galaxy M17e 5G (Blue, 6GB RAM)", "SM-M175F", datetime(2026, 5, 3), datetime(2026, 5, 5)),
            ("wty_nm_3", "Samsung", "Samsung Galaxy M17e 5G (Blue, 6GB RAM)", "SM-M175F", datetime(2026, 7, 1), datetime(2026, 7, 2)),
            ("wty_nm_4", "LG", "LG 242 L Frost-Free Double Door Refrigerator", "GL-T292RPZY", datetime(2025, 1, 9), datetime(2026, 1, 1)),
        ]
        for wid, brand, title, model, bought, created in rows:
            db.add(WarrantyDB(id=wid, brand=brand, product_name=title, model_code=model, purchase_date=bought,
                              created_at=created, alternatives={"seller": ["Croma"]}))
            db.add(WarrantyOwnerDB(user_id=USER, warranty_id=wid))
        db.commit()


def _client(user):
    client = TestClient(app)
    password = "admin123" if user == "admin" else "secret123"
    token = client.post("/auth/login", data={"username": user, "password": password}, headers={"accept": "application/json"}).json()["access_token"]
    client.post("/auth/login", data={"username": user, "password": password})  # cookie for the UI pages
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    _reset()


def _list(client, auth):
    return {w["id"]: w for w in client.get("/warranties/list", headers=auth).json()["warranties"]}


def test_list_names_tell_identical_products_apart_and_show_no_ids():
    client, auth = _client(USER)
    items = _list(client, auth)
    labels = [items[w]["display_label"] for w in ("wty_nm_1", "wty_nm_2", "wty_nm_3", "wty_nm_4")]
    assert labels[0] == "📱 Samsung Galaxy M17e 5G - Bought 3 May 2026 from Croma"
    assert labels[1] == "📱 Samsung Galaxy M17e 5G - Bought 3 May 2026 from Croma (2)"
    assert labels[2] == "📱 Samsung Galaxy M17e 5G - Bought 1 Jul 2026 from Croma"
    assert labels[3].startswith("🧊 LG ")
    assert len(set(labels)) == 4
    for item in items.values():
        for key in ("display_label", "display_name", "subtitle"):
            assert "wty_" not in item[key] and not re.search(r"\bRef [0-9A-F]{6}", item[key])
        assert "support_ref" not in item  # the short reference is for the PDF and admin only


def test_nickname_saves_shows_first_and_is_owner_only():
    client, auth = _client(USER)
    assert client.put("/warranties/wty_nm_2/nickname", json={"nickname": "  Mom's   phone "}, headers=auth).json() == {"nickname": "Mom's phone"}
    item = _list(client, auth)["wty_nm_2"]
    assert item["display_name"] == "Mom's phone" and item["display_label"].startswith("📱 Mom's phone - Bought 3 May 2026")
    assert item["product_name_short"] == "Samsung Galaxy M17e 5G"
    other, other_auth = _client(OTHER)
    assert other.put("/warranties/wty_nm_2/nickname", json={"nickname": "mine"}, headers=other_auth).status_code == 404
    client.put("/warranties/wty_nm_2/nickname", json={"nickname": ""}, headers=auth)  # clearing it
    assert _list(client, auth)["wty_nm_2"]["display_name"] == "Samsung Galaxy M17e 5G"


def test_admin_sees_ref_and_id():
    with SessionLocal() as db:
        db.merge(WarrantyOwnerDB(user_id="admin", warranty_id="wty_nm_1"))
        db.commit()
    admin, auth = _client("admin")
    item = _list(admin, auth)["wty_nm_1"]
    assert item["support_ref"] == product_naming.support_ref("wty_nm_1")
    assert f"Ref {item['support_ref']}" in item["display_label"]


def test_customer_page_has_no_id_field_and_admin_page_keeps_it():
    customer, _ = _client(USER)
    html = customer.get("/ui/neo-dashboard").text
    assert "Product / Warranty ID" not in html and 'placeholder="wty_xxx"' not in html
    assert '<input type="hidden" id="warrantyId">' in html and "Or enter ID manually" not in html
    assert 'id="nicknameInput"' in html and "Pick a product from your list" in html
    admin, _ = _client("admin")
    admin_html = admin.get("/ui/neo-dashboard").text
    assert "Product / Warranty ID" in admin_html and '<input type="hidden" id="warrantyId">' not in admin_html


def test_pdf_export_carries_the_short_name_and_ref():
    from app.storage import store

    w = store.get_warranty_db("wty_nm_1")
    text = customer_content.export_text(w, {})
    assert "Product: Samsung Galaxy M17e 5G" in text
    assert f"Support reference: Ref {product_naming.support_ref('wty_nm_1')}" in text and "wty_nm_1" not in text
