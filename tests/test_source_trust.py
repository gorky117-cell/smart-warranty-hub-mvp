from app.services.source_trust import classify_terms_source
from app.services.terms_lookup import classify_terms_source_url


def test_known_oem_domain_is_official():
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


def test_approved_oem_source_has_distinct_trust_label():
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
