"""Run 3 item 11: the synthetic global set (scripts/global_check.py) as tests, plus the general fixes it found."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import global_check as gc  # noqa: E402

from app.services import customer_content as cc  # noqa: E402
from app.services.ingestion import _model_candidate_from_line  # noqa: E402
from app.services.product_recommendations import infer_product_category  # noqa: E402
from app.services.summary_engine import limits_from_text  # noqa: E402


def test_the_set_covers_the_global_rule():
    assert set(c for c, *_ in gc.PRODUCTS) == set(gc.CATEGORIES)  # 9 categories
    for category in gc.CATEGORIES:
        assert len({b for c, b, *_ in gc.PRODUCTS if c == category}) >= 3  # >= 3 brands each
    assert set(gc.FORMATS) == {"text PDF", "scanned PDF", "phone photo"}


@pytest.mark.parametrize("index", range(len(gc.PRODUCTS)), ids=[f"{p[0]}-{p[1]}" for p in gc.PRODUCTS])
def test_text_pdf_invoices_marketplace_and_shop(index, tmp_path):
    from app.services.ocr import extract_text_with_meta

    product = gc.PRODUCTS[index]
    for style, (text, invoice_no, bought) in gc.invoices_for(index, product).items():
        path = tmp_path / f"{style}.pdf"
        path.write_bytes(gc.text_pdf(text))
        read, _err, meta = extract_text_with_meta(str(path))
        check = gc.check_document(product, style, read or "", invoice_no, bought, ocr_meta=meta)
        failed = [name for name, ok in check["results"].items() if not ok]
        assert failed == [], (style, failed, check["fields"])


@pytest.mark.parametrize("case", gc.WARRANTY_TYPES, ids=[t[0] for t in gc.WARRANTY_TYPES])
def test_warranty_types(case):
    rows = {r["type"]: r for r in gc.run_warranty_types()}
    assert rows[case[0]]["ok"], rows[case[0]]["card"]


def test_unknown_brand_is_never_guessed():
    rows = {r["type"]: r for r in gc.run_warranty_types()}
    assert rows["unknown brand on the invoice is not guessed"]["ok"]


# --- general fixes found by the set -------------------------------------------------------------------------

@pytest.mark.parametrize("line,brand,bad", [
    ("1 HP Laptop 15s, 12th Gen Intel Core i5-1235U, 16GB DDR4", "HP", "I5-1235U"),
    ("1 Dell Inspiron 3520 Laptop, Intel Core i3-1215U, 8GB", "Dell", "I3-1215U"),
    ("1 Havells Monza EC 15L Storage Water Heater", "Havells", "EC15L"),
])
def test_processor_and_capacity_are_not_models(line, brand, bad):
    model, _kind = _model_candidate_from_line(line, brand)
    assert model != bad


@pytest.mark.parametrize("name,line", [
    ("Redmi 13C (Starry Black, 4GB RAM, 128GB Storage)", "smartphone"),
    ("OnePlus Nord CE4 (8GB RAM, 256GB Storage)", "smartphone"),
    ("HP Laptop 15s (16GB RAM, 512GB SSD Storage)", "laptop"),
    ("Samsung Galaxy Tab A9 (4GB RAM, 64GB Storage)", "general"),  # a tablet is not a phone
])
def test_phone_recognised_from_specs(name, line):
    assert infer_product_category({"product_name": name}) == line


TERMS = [
    "The original serial number is removed, obliterated or altered from the machine or cabinet.",
    "Compressor failure due to gas leakage is covered for 10 years.",
    "Damage to the print head from non-genuine ink is not covered.",
    "The limited warranty period of 1 year will apply, regardless of the warranty period of the country where the product was first sold.",
    "Defects due to lightning or abnormal voltage are not covered.",
]


@pytest.mark.parametrize("line,kept", [
    ("smartphone", [4]),            # no cabinet, compressor or print head on a phone
    ("laptop", [4]),
    ("fridge", [0, 1, 4]),          # an appliance keeps cabinet and compressor wording
    ("air_conditioner", [0, 1, 4]),
    ("washing_machine", [0, 4]),    # no compressor
    ("printer", [2, 4]),            # keeps the print head
    (None, [0, 1, 2, 4]),           # unknown product: nothing dropped except the bought-abroad clause
])
def test_terms_about_other_products_dropped_for_any_line(line, kept):
    assert cc.clean_terms(TERMS, line=line) == [TERMS[i] for i in kept]


def test_wear_and_tear_names_parts_of_any_product():
    assert limits_from_text("Normal wear and tear of filters, lamps and rubber parts is not covered.") == [
        "Normal wear and tear of filters, lamps and bulbs or rubber parts is not covered."]


def test_ac_size_in_tons_means_an_air_conditioner():
    assert infer_product_category({"product_name": "Daikin 1.5 Ton Inverter Split AG FTKL50U"}) == "air_conditioner"


@pytest.mark.parametrize("line,brand", [
    ("1 IFB Front Load Washing Machine Senator WXS7kg", "IFB"),
    ("1 Bajaj Room Heater RX15L", "Bajaj"),
])
def test_series_glued_to_a_size_is_not_a_model(line, brand):
    model, _kind = _model_candidate_from_line(line, brand)
    assert model not in ("WXS7KG", "RX15L")
