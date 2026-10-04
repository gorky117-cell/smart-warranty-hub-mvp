"""Shared brand names: the product decides which company's terms are used (consolidated run step 7)."""

import pytest

from app.db import SessionLocal
from app.services import oem_source_policy, terms_lookup
from app.services.brand_families import resolve_oem_entity


@pytest.mark.parametrize(
    "brand, product, company",
    [
        ("Bajaj", "Bajaj Ceiling Fan 1200mm", "Bajaj Electricals"),
        ("Bajaj", "Bajaj Rex 500W Mixer Grinder", "Bajaj Electricals"),
        ("Bajaj Finserv", "Bajaj Mixer Grinder (EMI)", "Bajaj Electricals"),
        ("Bajaj", "Bajaj Pulsar 150 Motorcycle", "Bajaj Auto"),
        ("Bajaj", "Bajaj Chetak Electric", "Bajaj Auto"),
        ("Honda", "Honda Activa 6G", "Honda Motorcycle & Scooter India"),
        ("Honda", "Honda City VX CVT", "Honda Cars India"),
        ("Hero", "Hero Splendor Plus", "Hero MotoCorp"),
        ("Hero", "Hero Sprint 26T Bicycle", "Hero Cycles"),
        ("Yamaha", "Yamaha FZ-S V3", "Yamaha Motor India"),
        ("Yamaha", "Yamaha PSR-E373 Keyboard", "Yamaha Music India"),
        ("Hyundai", "Hyundai Creta SX", "Hyundai India"),
        ("Usha", "Usha Janome Sewing Machine", "Usha International"),
        ("Wipro", "Wipro 9W LED Bulb", "Wipro Lighting"),
        ("Nokia", "Nokia 105 Mobile Phone", "HMD"),
        ("Tata", "Tata Nexon XZ", "Tata Motors"),
        ("Havells", "Havells Stealth Ceiling Fan", "Havells"),
        ("Crompton", "Crompton Arno 15L Water Heater", "Crompton"),
    ],
)
def test_product_decides_the_company(brand, product, company):
    assert resolve_oem_entity(brand, product_name=product).company == company


@pytest.mark.parametrize(
    "brand, product",
    [
        ("Hero", "Hero Mixer Grinder"),  # no Hero appliance company: never appliance terms
        ("Hyundai", "Hyundai 32 inch LED TV"),  # licensed electronics: no official site
        ("Nokia", "Nokia 43 inch Smart TV"),
        ("Kenmore", "Kenmore Refrigerator"),  # not sold in India
        ("Bajaj", "Bajaj"),  # segment cannot be told
        ("Tata", "Tata Sky Set Top Box"),
    ],
)
def test_no_company_when_the_segment_has_none(brand, product):
    entity = resolve_oem_entity(brand, product_name=product)
    assert entity.family and entity.company is None


def test_unshared_brand_passes_through():
    entity = resolve_oem_entity("Samsung", product_name="Samsung Galaxy S24")
    assert entity.family is None and entity.company == "Samsung"


def test_bajaj_appliance_never_accepts_motorcycle_or_finance_pages():
    for url in ("https://www.bajajauto.com/warranty", "https://www.bajajfinserv.in/emi-card"):
        assert not oem_source_policy.is_approved_oem_url(url, "Bajaj Electricals")
    assert oem_source_policy.is_approved_oem_url("https://www.bajajelectricals.com/warranty", "Bajaj Electricals")


def test_hero_two_wheeler_never_accepts_appliance_pages():
    for url in ("https://www.bajajelectricals.com/warranty", "https://havells.com/warranty", "https://herocycles.com/warranty"):
        assert not oem_source_policy.is_approved_oem_url(url, "Hero MotoCorp")
    assert oem_source_policy.is_approved_oem_url("https://www.heromotocorp.com/en-in/warranty.html", "Hero MotoCorp")


def _lookup(monkeypatch, brand, product):
    seen = []
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: seen.append(kw["brand"]) or [])
    with SessionLocal() as db:
        result = terms_lookup.lookup_terms(db, brand=brand, category=None, region="IN", product_name=product, force_refresh=True)
    return result, seen


def test_lookup_uses_the_resolved_company(monkeypatch):
    _result, seen = _lookup(monkeypatch, "Bajaj", "Bajaj Ceiling Fan 1200mm")
    assert seen == ["Bajaj Electricals"]
    _result, seen = _lookup(monkeypatch, "Hero", "Hero Splendor Plus")
    assert seen == ["Hero MotoCorp"]


def test_lookup_without_a_company_asks_the_customer_to_check(monkeypatch):
    result, seen = _lookup(monkeypatch, "Hero", "Hero Mixer Grinder")
    assert seen == []  # no search at all
    assert result.duration_months is None
    assert result.terms == [terms_lookup.NEEDS_CHECK_MESSAGE]
    assert terms_lookup.classify_terms_source_url(result.source_url) == "needs_check"


def test_pipeline_records_the_company_for_a_bajaj_mixer_invoice(monkeypatch):
    from app.db_models import WarrantyDB
    from app.models import ArtifactType
    from app.services import invoice_pipeline
    from app.services.canonical import canonicalize_artifact
    from app.services.ingestion import ingest_artifact

    seen = []
    monkeypatch.setattr(terms_lookup, "discover_sources", lambda **kw: seen.append(kw["brand"]) or [])
    monkeypatch.setenv("OEM_AUTO_VERIFY", "false")
    text = "Tax Invoice\nSold by: Bajaj Finserv EMI Store\n1 Bajaj Rex 500W Mixer Grinder 1 Nos 2,499.00\nInvoice No: INV-77\nDate: 02-03-2025"
    artifact = ingest_artifact(ArtifactType.invoice, content=text, use_ocr=False)
    warranty = canonicalize_artifact(artifact, None)
    with SessionLocal() as db:
        job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=None)
    invoice_pipeline.run_job(job.id)
    with SessionLocal() as db:
        row = db.query(WarrantyDB).filter_by(id=warranty.id).first()
        assert row.brand == "Bajaj"
        assert row.alternatives["oem_entity"] == {"family": "Bajaj", "segment": "home_appliance", "company": "Bajaj Electricals"}
    assert seen == ["Bajaj Electricals"]
