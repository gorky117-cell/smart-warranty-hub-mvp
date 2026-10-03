"""Registry-based brand resolution (work plan step 7). Invoice texts below are synthetic."""

import pytest

from app.services import brand_registry
from app.services.ingestion import extract_product_fields

# Brands outside the old 27-brand tuple, each sold by a retailer whose name heads the invoice.
OUTSIDE_TUPLE_INVOICES = [
    ("Havells", "Vijay Sales Retail Pvt Ltd\nTAX INVOICE\nInvoice No: VS/2026/1182\nDate: 12-03-2026\n"
     "1 Havells Stealth Air BLDC Ceiling Fan 1200mm 1 4,590.00\nWarranty 5 years"),
    ("IFB", "Sri Lakshmi Electronics Pvt Ltd\nTax Invoice\nInvoice No: SLE-4471\nDate: 02-02-2026\n"
     "1 IFB Senator WXS 8kg Front Load Washing Machine 1 38,990.00\nWarranty: 4 years"),
    ("boAt", "Poorvika Mobiles Pvt Ltd\nTAX INVOICE\nInvoice No: PM/88213\nDate: 05-01-2026\n"
     "1 boAt Airdopes 141 Bluetooth Headphone 1 1,299.00\n1 year warranty"),
    ("Ather", "Ather Space Koramangala\nTAX INVOICE\nInvoice No: ATH-2231\nDate: 15-01-2026\n"
     "1 Ather 450X Electric Scooter Gen 3 1 1,45,000.00\nBattery warranty 5 years"),
    ("Crompton", "Croma - Infiniti Retail Ltd\nTAX INVOICE\nInvoice No: CRM/26/5512\nDate: 20-01-2026\n"
     "1 Crompton Arno Neo 15L Geyser 1 6,499.00\nWarranty 2 years"),
    ("Dyson", "Reliance Digital Retail Ltd\nTAX INVOICE\nInvoice No: RD-77120\nDate: 03-03-2026\n"
     "1 Dyson V12 Detect Slim Vacuum Cleaner 1 52,900.00\nWarranty 2 years"),
    ("Canon", "The Print Mall\nTAX INVOICE\nInvoice No: TPM/4410/25-26\nDate: 11-02-2026\n"
     "1 Canon PIXMA G3010 Printer 1 12,499.00\nWarranty 1 year"),
    ("Nothing", "Sangeetha Mobiles Pvt Ltd\nTAX INVOICE\nInvoice No: SM-90012\nDate: 07-03-2026\n"
     "1 Nothing Phone (2a) 5G Mobile 1 23,999.00\nWarranty 12 months"),
]


@pytest.mark.parametrize("expected,text", OUTSIDE_TUPLE_INVOICES, ids=[b for b, _ in OUTSIDE_TUPLE_INVOICES])
def test_brand_outside_old_tuple_resolves_to_manufacturer_not_seller(expected, text):
    fields, confidence, alternatives = extract_product_fields(text)
    assert fields.get("brand") == expected
    assert confidence["brand"] == 0.85


def test_registry_covers_200_brands_with_india_duplicates_collapsed():
    # 200 registry keys; " India" duplicates and case variants collapse, aliases add Mi/One Plus/i Phone.
    assert 150 <= brand_registry.brand_count() <= 200
    assert brand_registry.find_brands("Samsung India Galaxy M17e") == ["Samsung"]
    assert brand_registry.find_brands("USHA mixer") == ["Usha"]


def test_longest_registry_name_wins():
    assert brand_registry.find_brands("Bajaj Electricals Room Heater") == ["Bajaj Electricals"]
    assert brand_registry.find_brands("Bajaj Majesty Mixer") == ["Bajaj"]


@pytest.mark.parametrize(
    "text",
    ["Carrier: Blue Dart Express", "returns: nothing to declare", "a sharp knife", "hero of the day"],
)
def test_ambiguous_words_need_name_form(text):
    assert brand_registry.find_brands(text) == []


def test_ambiguous_brand_matches_when_written_as_name():
    assert brand_registry.find_brands("1 Carrier 1.5 Ton 5 Star Split AC") == ["Carrier"]
    assert brand_registry.find_brands("1 LG 55 inch OLED TV") == ["LG"]


def test_retailer_never_wins_over_product_brand_or_from_seller_line():
    assert brand_registry.resolve_brand("Croma Crompton Geyser 15L") == "Crompton"
    assert brand_registry.resolve_brand(None, ["Croma - Infiniti Retail Ltd"]) is None
    assert brand_registry.resolve_brand("Croma 80 cm HD Ready LED TV") == "Croma"


def test_brand_from_authorised_store_header_when_product_line_has_none():
    text = "LG Authorized Store\nTAX INVOICE\nProduct OLED55C3\nWarranty: 12 months manufacturer warranty"
    fields, confidence, _ = extract_product_fields(text)
    assert fields["brand"] == "LG"
    assert confidence["brand"] == 0.7


def test_registry_brand_beats_garbled_brand_label_but_label_wins_when_in_registry():
    garbled = "Whirlpool Authorized Store\nTAX INVOICE\nProduct WM-8KG-PRO\nBrand: Whitlpet\nWarranty 12 months"
    assert extract_product_fields(garbled)[0]["brand"] == "Whirlpool"
    labelled = "Sharma Traders\nTAX INVOICE\nProduct WM-8KG-PRO\nBrand: Whirlpool\nWarranty 12 months"
    assert extract_product_fields(labelled)[0]["brand"] == "Whirlpool"


def test_seller_line_is_not_used_as_brand():
    text = "Kumar Enterprises\nTAX INVOICE\nInvoice No: KE-11\nDate: 01-01-2026\nWarranty 1 year"
    assert extract_product_fields(text)[0].get("brand") != "Kumar Enterprises"


def test_brands_formerly_in_tuple_still_resolve():
    for brand in ("Acer", "Apple", "Asus", "Bosch", "Brother", "Canon", "Dell", "Dyson", "Epson", "Godrej", "Haier",
                  "HP", "Lenovo", "LG", "Microsoft", "OnePlus", "Oppo", "Panasonic", "Philips", "Samsung", "Sony",
                  "Vivo", "Voltas", "Whirlpool", "Xiaomi"):
        assert brand_registry.find_brands(f"1 {brand} Product 100") == [brand], brand
    assert brand_registry.find_brands("1 Mi Smart Band 8") == ["Xiaomi"]
    assert brand_registry.find_brands("1 Bajaj Majesty Mixer") == ["Bajaj"]
