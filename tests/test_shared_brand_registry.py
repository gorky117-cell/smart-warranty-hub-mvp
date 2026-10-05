"""Owner decision 2: a shared brand name is resolved by product category; the bare name is never a company."""

import pytest

from app.services.brand_families import is_unresolved_family, resolve_oem_entity
from app.services.source_trust import classify_terms_source
from app.services.terms_cache import verified_official


@pytest.mark.parametrize("brand,product,company", [
    ("Bajaj", "Bajaj GX 3701 Mixer Grinder", "Bajaj Electricals"),
    ("Bajaj", "Bajaj Pulsar 150 Motorcycle", "Bajaj Auto"),
    ("Bajaj Finserv", "Bajaj Mixer Grinder", "Bajaj Electricals"),  # the lender is never the maker
    ("Honda", "Honda Activa 6G Scooter", "Honda Motorcycle & Scooter India"),
    ("Honda", "Honda City Car", "Honda Cars India"),
    ("Hero", "Hero Splendor Plus Motorcycle", "Hero MotoCorp"),
    ("Hero", "Hero Sprint Bicycle", "Hero Cycles"),
    ("TVS", "TVS Jupiter Scooter", "TVS Motor"),
    ("TVS", "TVS Gold Keyboard", None),           # TVS Electronics: not TVS Motor, so no terms
    ("Godrej", "Godrej Double Door Refrigerator", "Godrej Appliances"),
    ("Hindware", "Hindware Kitchen Chimney", "Hindware Appliances"),
    ("Yamaha", "Yamaha PSR Keyboard", "Yamaha Music India"),
    ("Bajaj", "Bajaj Gift Card", None),             # cannot tell: no company's terms
])
def test_category_decides_the_company(brand, product, company):
    assert resolve_oem_entity(brand, product_name=product).company == company


@pytest.mark.parametrize("name,shared", [
    ("Bajaj", True), ("Bajaj Finserv", True), ("Honda", True), ("Hero", True), ("TVS", True), ("Tata", True),
    ("Wipro", True), ("Nokia", True), ("Crompton", False), ("Havells", False), ("Samsung", False),
    ("Bajaj Electricals", False), ("Bajaj Auto", False),
])
def test_bare_shared_names_are_not_companies(name, shared):
    assert is_unresolved_family(name) is shared


@pytest.mark.parametrize("brand,url,official", [
    ("Bajaj Electricals", "https://www.bajajelectricals.com/warranty", True),
    ("Bajaj Electricals", "https://www.bajajauto.com/warranty", False),  # a motorcycle page is not a mixer's
    ("Bajaj", "https://www.bajajauto.com/warranty", False),                # bare name: no official site
    ("Bajaj", "https://www.bajaj.com/warranty", False),
    ("Bajaj Finserv", "https://www.bajajfinserv.in/terms", False),
    ("Honda", "https://www.hondacarindia.com/warranty", False),
    ("Honda Cars India", "https://www.hondacarindia.com/warranty", True),
    ("Crompton", "https://www.crompton.co.in/warranty", True),
])
def test_official_pages_only_for_resolved_companies(brand, url, official):
    assert bool(classify_terms_source(brand=brand, source_url=url, source_type="scraped")["official"]) is official
    if not official:
        assert verified_official(url, brand) is False  # never cached or labelled as the brand's own page
