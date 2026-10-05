import pytest

from app.services import source_trust
from app.services.source_trust import classify_terms_source
from app.services.terms_lookup import classify_terms_source_url


@pytest.fixture
def no_verified_domains(monkeypatch):
    # data/oem_verified.json is populated since fix run B8; these tests pin the unverified behaviour.
    monkeypatch.setattr(source_trust, "load_verified_domains", lambda: {})


def test_known_oem_domain_is_official(no_verified_domains):
    trust = classify_terms_source(
        brand="HP",
        source_url="https://support.hp.com/warranty",
        source_type="scraped",
    )

    assert trust["official"] is True
    assert trust["requires_oem_verification"] is True
    assert trust["status"] == "official"


def test_unverified_external_source_requires_verification():
    trust = classify_terms_source(
        brand="HP",
        source_url="https://example.com/warranty",
        source_type="scraped",
    )

    assert trust["official"] is False
    assert trust["verified"] is False
    assert trust["requires_oem_verification"] is True


def test_synthetic_approved_source_is_test_only():
    trust = classify_terms_source(
        brand="Acmeco",
        source_url="test_data/synthetic_acmeco_zx100_warranty.html",
        source_type="synthetic_approved",
    )

    assert trust["status"] == "synthetic_test_source"
    assert trust["official"] is False
    assert trust["verified"] is False
    assert trust["requires_oem_verification"] is True


def test_approved_oem_source_has_distinct_trust_label(no_verified_domains):
    source_type = classify_terms_source_url("https://www.samsung.com/in/support/warranty/", "Samsung")
    trust = classify_terms_source(
        brand="Samsung",
        source_url="https://www.samsung.com/in/support/warranty/",
        source_type=source_type,
    )

    assert source_type == "approved_oem_source"
    assert trust["status"] == "approved_oem_source"
    assert trust["official"] is True
    assert trust["requires_oem_verification"] is True


def test_unapproved_http_source_remains_scraped():
    source_type = classify_terms_source_url("https://example.com/warranty", "Samsung")

    assert source_type == "scraped"


def test_verified_domain_is_labelled_verified_official(monkeypatch):
    monkeypatch.setattr(source_trust, "load_verified_domains", lambda: {"HP": ["hp.com"]})
    trust = classify_terms_source(brand="HP", source_url="https://support.hp.com/warranty", source_type="scraped")
    assert trust["status"] == "verified_official"
    assert trust["verified"] is True and trust["official"] is True
    assert trust["label"] == "From HP's official warranty page"


def test_verified_label_uses_registry_brand_spelling(monkeypatch):
    monkeypatch.setattr(source_trust, "load_verified_domains", lambda: {"OnePlus": ["oneplus.in"]})
    trust = classify_terms_source(brand="oneplus", source_url="https://www.oneplus.in/support", source_type="scraped")
    assert trust["label"] == "From OnePlus India's official warranty page"  # oneplus.in


def test_orient_points_to_orient_electric_not_the_tiles_company():
    from app.services.oem_domains import load_oem_domains, load_verified_domains

    for registry in (load_oem_domains(), load_verified_domains()):
        assert registry["Orient"] == ["orientelectric.com"]
        assert not any("orientbell" in d for domains in registry.values() for d in domains)


def test_manually_confirmed_site_has_its_own_label(no_verified_domains):
    trust = classify_terms_source(brand="LG", source_url="https://www.lg.com/in/support/warranty", source_type="scraped")
    assert trust["status"] == "manually_confirmed_official"
    assert trust["label"] == "From LG India's official warranty page (manually confirmed)"
    assert trust["manually_confirmed"] is True and trust["official"] is True


def test_manual_list_covers_the_five_checker_blocked_brands():
    from app.services.oem_domains import load_manual_confirmed_domains, load_oem_domains

    manual = load_manual_confirmed_domains()
    registry = load_oem_domains()
    assert set(manual) == {"LG", "Sony", "Dell", "Panasonic", "Whirlpool"}
    for brand, domains in manual.items():
        assert set(domains) <= set(registry[brand]), brand
