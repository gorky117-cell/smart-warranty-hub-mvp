"""Fix run B6 regressions: MG Road, device -> EV, 120 months, response decoding, kia.com/in."""

from types import SimpleNamespace

import pytest

from app.services import brand_registry, product_recommendations
from app.services import terms_lookup as tl
from app.services.ingestion import extract_product_fields
from app.services.oem_domains import load_oem_domains, normalize_domain
from app.services.warranty_parser import _best_duration_months, parse_terms_from_html, response_text


def test_mg_road_is_an_address_not_the_brand_mg():
    assert brand_registry.find_brands("12, MG Road, Bengaluru 560001") == []
    assert brand_registry.find_brands("Shop 4, Hero Honda Chowk, Gurugram") == []
    assert brand_registry.find_brands("1 MG Hector Plus EV") == ["MG"]
    assert brand_registry.find_brands("1 Bajaj Tower Fan") == ["Bajaj"]
    fields, _c, _a = extract_product_fields(
        "Sri Ram Traders\n45, MG Road, Bengaluru 560001\nTAX INVOICE\n1 Prestige Induction Cooktop PIC 20 1 2,499.00"
    )
    assert fields.get("brand") != "MG"


@pytest.mark.parametrize(
    "category,expected",
    [
        ("electronic device", "electronics"),
        ("device", "electronics"),
        ("Smart devices", "electronics"),
        ("EV", "ev"),
        ("electric vehicle", "ev"),
        ("battery", "ev"),
        ("washing machine", "appliance"),
        ("dishwasher", "appliance"),
        ("mobile", "mobile"),
        ("Mobile Phone", "mobile"),
        ("printer", "general"),
        ("Level meter", "general"),
    ],
)
def test_category_normalisation_uses_whole_words(category, expected):
    assert tl._normalize_category(category) == expected


def test_device_no_longer_gets_36_month_ev_default():
    assert tl.DEFAULT_RULES[tl._normalize_category("electronic device")] == 12


def test_product_category_does_not_read_ev_inside_words():
    assert product_recommendations.infer_product_category({"product_name": "Clever Device Hub"}) != "ev"
    assert product_recommendations.infer_product_category({"product_name": "Ather 450X EV"}) == "ev"


def test_three_digit_months_are_read_in_full():
    assert _best_duration_months("Panel warranty: 120 months.") == 120
    assert _best_duration_months("Warranty is 18 months from purchase.") == 18
    assert _best_duration_months("Model 2018month code") is None  # not a duration


def test_leading_quantity_is_not_stripped_as_a_bullet():
    parsed = parse_terms_from_html("<p>1. Warranty coverage is up to 12 months, whichever comes first.</p>")
    assert parsed.duration_months == 12
    text = "60 months (only part warranty)\nWarranty coverage of up to 1 year or 30,000 prints, whichever comes first."
    assert _best_duration_months(text) == 12  # part-only row is a component, not the base


def test_html_entities_and_undeclared_charset_decode_cleanly():
    parsed = parse_terms_from_html("<p>Epson&rsquo;s warranty includes coverage of printhead for printers.</p>")
    term = " ".join(parsed.terms)
    assert "\u2019" in term and "\ufffd" not in term
    utf8_body = "Epson\u2019s warranty".encode("utf-8")
    no_charset = SimpleNamespace(headers={"content-type": "text/html"}, content=utf8_body, text=utf8_body.decode("latin-1"))
    assert response_text(no_charset) == "Epson\u2019s warranty"
    declared = SimpleNamespace(headers={"content-type": "text/html; charset=UTF-8"}, content=utf8_body, text="Epson\u2019s warranty")
    assert response_text(declared) == "Epson\u2019s warranty"


def test_registry_domains_are_bare_hosts():
    assert normalize_domain("kia.com/in") == "kia.com"
    assert normalize_domain("https://www.Samsung.com/in/") == "samsung.com"
    registry = load_oem_domains()
    assert registry["Kia"] == ["kia.com", "kia.co.in"]
    assert all("/" not in d and ":" not in d for domains in registry.values() for d in domains)
