"""Real 2017 Amazon (Cloudtail) Voltas window-AC invoice, OCR text with buyer details replaced (batch 3), and the
general rules behind each fix, checked on other products and brands too (GLOBAL RULE)."""
from pathlib import Path

import pytest

from app.services import brand_registry, product_naming
from app.services.ingestion import bracket_spec_model, extract_product_fields
from app.services.terms_cache import product_line

FIXTURE = (Path(__file__).parent / "fixtures" / "invoices" / "amazon_2017_voltas_window_ac.txt").read_text(encoding="utf-8")


def test_fixture_fields():
    fields, _c, alt = extract_product_fields(FIXTURE)
    assert fields["brand"] == "Voltas"
    assert product_line(fields.get("model_code"), fields.get("product_name")) == "air_conditioner"
    assert fields["purchase_date"] == "2017-04-22"
    assert fields["invoice_no"] == "HR-SDEG-1004-0000" and alt["order_id"] == ["402-0000000-0000000"]
    assert alt["seller"] == ["Cloudtail India Private Limited"]
    assert fields["product_name"] == "Voltas 1.5 Ton 3 Star Window AC"
    assert "model_code" not in fields
    assert alt["model_suggestion"]["value"] == "183 CYa" and alt["model_suggestion"]["status"] == "pending"
    assert "B00NBM4LJ0" not in str(fields) and "B00NBM4LJ0" not in str(alt.get("model_suggestion"))


# --- seller -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,seller", [
    ("Sold By\nCloudtail India Private Limited\nInvoice No: X1", "Cloudtail India Private Limited"),
    ("Sold By: Appario Retail Private Ltd\n1 Samsung Galaxy M17e", "Appario Retail Private Ltd"),
    ("Page 1 of 2\nSeller Name: Darshita Etel Pvt Ltd\n1 Redmi 13C", "Darshita Etel Pvt Ltd"),
    ("SHARMA ELECTRONICS\nMG Road\nBill No: SH/1 Date: 01/01/2025\n1 LG TV 43UR7500PSC", "Sharma Electronics"),
    ("The Print Mall\n1 Epson L3250 Printer", "The Print Mall"),
])
def test_seller_comes_from_sold_by_or_a_shop_name(text, seller):
    _f, _c, alt = extract_product_fields(text)
    assert alt.get("seller") == [seller]


@pytest.mark.parametrize("text", [
    "Page 1 of 1, I-1/1\nInvoice for ABC Apr 22, 2017\n1 Bosch Washing Machine WAJ2416WIN",
    "Tax Invoice\nOriginal for Recipient\n1 Havells Geyser GHWAMECWH015",
    "I-1/1\nThis is a computer generated invoice\n1 Canon Printer G3010",
])
def test_unsure_means_no_seller(text):
    _f, _c, alt = extract_product_fields(text)
    assert "seller" not in alt


@pytest.mark.parametrize("value,ok", [
    ("Page 1 Of 1, I-1/1", False), ("I-1/1", False), ("Invoice For Dmvvzzmtnn", False), ("12345 67890", False),
    ("Croma", True), ("Cloudtail India Private Limited", True),
])
def test_plausible_seller_name(value, ok):
    assert brand_registry.plausible_seller_name(value) is ok


def test_product_list_label_never_shows_header_noise():
    assert product_naming.seller_from({"seller": ["Page 1 Of 1, I-1/1"]}) is None
    assert product_naming.subtitle("2017-04-22", product_naming.seller_from({"seller": ["Page 1 Of 1, I-1/1"]})) == "Bought 22 Apr 2017"
    assert product_naming.seller_from({"seller": ["CLOUDTAIL INDIA PRIVATE LIMITED"]}) == "Cloudtail India Private Limited"


# --- model in bracketed spec lists --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Voltas 1.5 Ton 3 Star Window AC (Copper, 183 CYa, White)", "183 CYa"),           # AC
    ("Samsung Galaxy M17e 5G (Blitz Blue, 6GB RAM, 128GB Storage)", None),             # phone: specs only
    ("LG 242 L Refrigerator (GL-T292RPZY, Dazzle Steel)", "GL-T292RPZY"),              # fridge
    ("IFB 7 Kg Front Load Washing Machine (Senator WXS, Silver)", None),                # series name, no digits
    ("Sony Bravia 55 inch TV (Black)", None),                                            # single item
    ("Echo Dot (B0CMTVYVRS, Charcoal)", None),                                          # ASIN
    ("Daikin 1.5 Ton Inverter Split AC (Copper, FTKL50U, White)", "FTKL50U"),
    ("Philips Mixer Grinder (750 W, 3 Jars, Black)", None),
    ("HP Laptop (16GB RAM, 512GB SSD, Silver)", None),
])
def test_bracket_spec_model(text, expected):
    found = bracket_spec_model(text)
    assert (found[0] if found else None) == expected


def test_listing_codes_are_never_models():
    text = "Sold By: Shop Pvt Ltd\n1 Bajaj Mixer Grinder 750W Rs. 2,999.00\n(White, X001ABCDEF, 3 Jars)\nX001ABCDEF\nB00NBM4LJ0"
    fields, _c, alt = extract_product_fields(text)
    for code in ("X001ABCDEF", "B00NBM4LJ0"):
        assert code not in str(fields.get("model_code"))
        assert code not in str((alt.get("model_suggestion") or {}).get("value"))


def test_a_spaced_model_can_be_confirmed_but_not_a_spaced_serial():
    from fastapi import HTTPException

    from app.main import _clean_identity_value

    assert _clean_identity_value("model_code", "183 CYa") == "183 CYA"
    assert _clean_identity_value("model_code", "GX 3701") == "GX 3701"
    assert _clean_identity_value("model_code", " 183  CYa ") == "183 CYA"  # extra spaces collapsed
    with pytest.raises(HTTPException):
        _clean_identity_value("model_code", "-183")
    with pytest.raises(HTTPException):
        _clean_identity_value("serial_no", "AB 1234")
