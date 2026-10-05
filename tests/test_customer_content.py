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
