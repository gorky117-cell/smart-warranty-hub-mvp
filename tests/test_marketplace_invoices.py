"""Marketplace and retail-chain invoices (consolidated run step 8). All invoices are synthetic."""

from pathlib import Path

import pytest

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.models import ArtifactType
from app.services import invoice_pipeline, summary_engine, terms_lookup
from app.services.canonical import canonicalize_artifact
from app.services.ingestion import extract_product_fields, ingest_artifact
from app.services.warranty_discovery import _region_score

FIXTURES = Path(__file__).parent / "fixtures" / "marketplace"


def _fields(name):
    return extract_product_fields((FIXTURES / f"{name}.txt").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name, brand, product, model, invoice_no, purchase",
    [
        ("amazon", "boAt", "boAt Rockerz 450 Bluetooth On Ear Headphones with Mic (Luscious Black)", None, "BLR7-1234567", "2026-02-12"),
        ("flipkart", "Philips", "Philips HL7756/00 750 W Mixer Grinder (Black, 3 Jars)", "HL7756/00", "FAABCD2600012345", "2026-01-05"),
        ("croma", "Croma", "Croma 80 cm (32 inch) HD Ready LED Smart TV CREL032HOF024601", "CREL032HOF024601", "CRM-26-001234", "2026-03-18"),
        ("reliance_digital", None, "Reconnect 1.5 Ton 3 Star Inverter Split AC RAC-SPL15", "RAC-SPL15", "RD-4455667", "2026-03-22"),
    ],
)
def test_brand_comes_from_the_product_title_not_the_seller(name, brand, product, model, invoice_no, purchase):
    fields, _c, alt = _fields(name)
    assert fields.get("brand") == brand
    assert fields["product_name"] == product
    assert fields.get("model_code") == model
    assert fields["invoice_no"] == invoice_no and fields["purchase_date"] == purchase
    assert "serial_no" not in fields and "serial_suggestion" not in alt  # no serial printed: blank is fine
    for seller in ("Appario", "RetailNet", "Infiniti", "Reliance Retail"):
        assert seller.lower() not in str(fields.get("brand") or "").lower()


def test_tax_ids_are_never_offered_as_models():
    _fields_, _c, alt = _fields("amazon")
    assert "model_suggestion" not in alt  # the seller's PAN AALCA0171E used to be offered
    assert _fields_["product_category"] == "electronics"  # "Headphones" is not a phone


def test_unknown_title_brand_is_a_suggestion():
    fields, _c, alt = _fields("reliance_digital")
    assert "brand" not in fields
    assert alt["brand_suggestion"]["value"] == "Reconnect" and alt["brand_suggestion"]["status"] == "pending"


def test_unknown_brand_never_gets_a_guessed_duration(monkeypatch):
    called = []
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: called.append(kw) or [])
    with SessionLocal() as db:
        for brand in (None, "", "Reconnect", "Zqx Gadgets"):
            result = terms_lookup.lookup_terms(db, brand=brand, category="appliance", region="IN", force_refresh=True)
            assert result.duration_months is None and result.terms == [terms_lookup.NEEDS_CHECK_MESSAGE]
            assert terms_lookup.classify_terms_source_url(result.source_url) == "needs_check"
    assert called == []


def test_reliance_own_label_invoice_ends_in_please_check(monkeypatch):
    monkeypatch.setenv("OEM_AUTO_VERIFY", "false")
    text = (FIXTURES / "reliance_digital.txt").read_text(encoding="utf-8")
    artifact = ingest_artifact(ArtifactType.invoice, content=text, use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)
    with SessionLocal() as db:
        job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=None)
    invoice_pipeline.run_job(job.id)
    from app.storage import store

    store.warranties.pop(warranty.id, None)
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=warranty.id).first()
        assert row.coverage_months is None and row.expiry_date is None
        assert row.alternatives["terms_source_type"] == "needs_check"
        assert row.terms == [terms_lookup.NEEDS_CHECK_MESSAGE]
    evidence = summary_engine.build_evidence_summary(store.get_warranty_db(warranty.id))
    assert evidence["status"] == "needs_check"
    assert evidence["status_label"] == "Estimated - please check your warranty card or the seller"


def test_india_page_preferred_for_global_brands():
    india = _region_score("IN", "https://www.samsung.com/in/support/warranty/")
    global_page = _region_score("IN", "https://www.samsung.com/support/warranty-info")
    us_page = _region_score("IN", "https://www.samsung.com/us/support/warranty/")
    assert india > global_page > us_page
    assert _region_score("IN", "https://www.dell.com/support/home/en-in") > global_page
    assert _region_score("IN", "https://www.lg.com/printer/warranty") == 0  # "in" inside "printer" is not India


def test_model_codes_keep_slash_variants_but_not_spec_pairs():
    from app.services.ingestion import _model_candidate_from_line

    assert _model_candidate_from_line("Philips HL7756/00 750 W Mixer Grinder", None) == ("HL7756/00", "code")
    assert _model_candidate_from_line("Samsung Galaxy A15 SM-A155F/DS 8GB/128GB", None) == ("SM-A155F/DS", "code")
    assert extract_product_fields("Tax Invoice\nModel: HL7756/00\nDate: 01-01-2026")[0]["model_code"] == "HL7756/00"
    assert _model_candidate_from_line("1 Epson L 3250 Printer 84433240 1no", None) == ("L3250", "code")


def test_philips_india_site_is_official_and_preferred():
    from app.services import oem_source_policy

    url = "https://www.philips.co.in/c-w/support-home/warranty.html"
    for brand in ("Philips", "Philips India"):
        assert oem_source_policy.is_approved_oem_url(url, brand)
    assert _region_score("IN", url) > _region_score("IN", "https://www.philips.com/support/warranty")
