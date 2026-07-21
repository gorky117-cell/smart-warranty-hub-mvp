from app.services.source_trust import classify_terms_source


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

