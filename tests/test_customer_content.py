"""Customer-facing content fixes from live test 1 (Samsung M17e). Texts are from the live export."""

from datetime import date, timedelta

from app.models import CanonicalWarranty
from app.services import customer_content as cc

LIVE_STEPS = [
    "Out of Warranty Repair Charges",
    "Digital Service Center",
    "Service Center",
    "Type of Service (Handset) - Repair service carried at Samsung authorized service center.",
    "Exchange warranty applicable at Samsung authorized service center. Warranty applicable from customer purchase date",
]


def _warranty(**kw):
    base = dict(id="w1", product_name="Samsung Galaxy M17e 5G", brand="Samsung", model_code="M17E",
                purchase_date=date.today() - timedelta(days=30), coverage_months=12, alternatives={})
    base.update(kw)
    return CanonicalWarranty(**base)


# --- item 1: claim steps -------------------------------------------------------------------------------


def test_navigation_labels_are_dropped_from_claim_steps():
    steps = cc.clean_claim_steps(LIVE_STEPS, in_warranty=True)
    assert steps == [
        "Repair service carried at Samsung authorized service center.",
        "Exchange warranty applicable at Samsung authorized service center. Warranty applicable from customer purchase date",
    ]


def test_in_warranty_product_never_starts_with_an_out_of_warranty_step():
    steps = ["Out of warranty repairs are chargeable at the service center.", "Visit a Samsung service center with the invoice."]
    assert cc.clean_claim_steps(steps, in_warranty=True)[0] == "Visit a Samsung service center with the invoice."
    assert cc.clean_claim_steps(steps, in_warranty=False)[0].startswith("Out of warranty")  # expired: order kept


def test_tidy_applies_to_loaded_warranties_and_never_leaves_steps_empty():
    w = cc.tidy(_warranty(claim_steps=LIVE_STEPS))
    assert "Service Center" not in w.claim_steps and w.claim_steps[0].startswith("Repair service")
    only_labels = cc.tidy(_warranty(claim_steps=["Service Center", "Digital Service Center"]))
    assert only_labels.claim_steps[1] == "Contact Samsung support or an authorized service center to raise a claim."


def test_store_shows_cleaned_steps_but_database_keeps_the_oem_text():
    from app.db import SessionLocal
    from app.db_models import WarrantyDB
    from app.storage import store

    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_cc_steps").delete()
        db.add(WarrantyDB(id="wty_cc_steps", brand="Samsung", product_name="Galaxy M17e", coverage_months=12,
                          claim_steps=LIVE_STEPS, alternatives={}))
        db.commit()
    store.warranties.pop("wty_cc_steps", None)
    assert "Digital Service Center" not in store.get_warranty_db("wty_cc_steps").claim_steps
    with SessionLocal() as db:
        assert "Digital Service Center" in db.query(WarrantyDB).filter_by(id="wty_cc_steps").one().claim_steps


# --- item 5: terms for phones; label ------------------------------------------------------------------------

LIVE_TERMS = [
    "Standard coverage for 12 months from purchase date.",
    "Limited International One Year Warranty",
    "Warranty does not cover normal wear and tear (including, without limitation, wear and tear of camera lenses, batteries or displays).",
    "The limited warranty period of 1 year will apply, regardless of the warranty period of the country where the product was first sold.",
    "The company's obligation under this warranty shall be limited to repair or providing replacement of part/s only.",
    "The company's obligation under this warranty shall be limited to repairing or providing replacement of part/s, which are found to be defective.",
]
LIVE_EXCLUSIONS = [
    "Warranty does not cover repair due to external factors/medium/data types.",
    "The original serial number is removed, obliterated or altered from the machine or cabinet.",
    "Defects due to cause beyond control like lightning, abnormal voltage, acts of God or while in transit to service Center or purchaser's residence.",
]


def test_phone_terms_drop_international_clause_and_near_duplicates():
    terms = cc.clean_terms(LIVE_TERMS, phone=True)
    assert not any("International" in t or "regardless of the warranty period" in t for t in terms)
    assert sum("company's obligation" in t for t in terms) == 1
    assert any(t.endswith("which are found to be defective.") for t in terms)  # the more complete one kept


def test_phone_exclusions_drop_appliance_wording_and_garbled_fragments():
    exclusions = cc.clean_terms(LIVE_EXCLUSIONS, phone=True)
    assert exclusions == [LIVE_EXCLUSIONS[2]]
    # an appliance keeps its appliance wording
    assert LIVE_EXCLUSIONS[1] in cc.clean_terms(LIVE_EXCLUSIONS, phone=False)


def test_tidy_cleans_phone_terms_on_display():
    w = cc.tidy(_warranty(terms=LIVE_TERMS, exclusions=LIVE_EXCLUSIONS))
    assert "Limited International One Year Warranty" not in w.terms
    assert not any("machine or cabinet" in e for e in w.exclusions)


MOBILE_PAGE = """<html><body><h2>Warranty Policy</h2>
<h3>Mobile Phones</h3><h4>Warranty Terms</h4>
<p>The limited warranty period for mobile phones is one year (12 months) from the date of purchase.</p>
<p>Warranty does not cover normal wear and tear (including, without limitation, wear and tear of camera lenses, batteries or displays).</p>
<h4>THIS WARRANTY IS NOT APPLICABLE IN ANY OF THE FOLLOWING CASES</h4>
<p>1.</p><p>The original serial number is removed, obliterated or altered from the product.</p>
<p>2.</p><p>Defects due to causes beyond control like lightning, abnormal voltage, acts of God.</p>
<h3>Home Appliances</h3><h4>Warranty Terms</h4>
<p>The warranty period for the compressor is 120 months (10 years) from the date of purchase.</p>
<p>The original serial number is removed, obliterated or altered from the machine or cabinet.</p>
</body></html>"""


def test_multi_product_page_is_read_in_the_phone_section_only(tmp_path):
    import os

    from app.services.warranty_parser import parse_terms_from_url, section_text

    os.environ["TERMS_NLP_ENRICH_ENABLED"] = "0"
    section = section_text(MOBILE_PAGE, "smartphone")
    assert "compressor" not in section and "12 months" in section
    assert section_text(MOBILE_PAGE, None) is None and section_text("<h3>Mobile Phones</h3><p>x</p>", "smartphone") is None
    page = tmp_path / "samsung.html"
    page.write_text(MOBILE_PAGE, encoding="utf-8")
    phone, _ = parse_terms_from_url(str(page), product_line="smartphone")
    assert phone.duration_months == 12
    assert any("abnormal voltage" in e for e in phone.exclusions) and not any("cabinet" in e for e in phone.exclusions)
    whole, _ = parse_terms_from_url(str(page))
    assert "compressor" in (whole.raw_text or "")  # without the hint the whole page is read


def test_label_names_the_brand_and_country_page():
    from app.services.source_trust import classify_terms_source

    trust = classify_terms_source(brand="Samsung", source_url="https://www.samsung.com/in/support/warranty/",
                                  source_type="approved_oem_source")
    assert trust["label"] == "From Samsung India's official warranty page"
