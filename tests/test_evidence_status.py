from app.models import CanonicalWarranty
from app.services import summary_engine


def _warranty(source_type=None, source_url=None):
    alternatives = {}
    if source_type:
        alternatives["terms_source_type"] = source_type
    if source_url:
        alternatives["terms_source_url"] = source_url
    return CanonicalWarranty(
        id="w_evidence",
        brand="Acmeco",
        model_code="ZX-100",
        coverage_months=12,
        terms=["Base parts covered."],
        exclusions=["Liquid damage excluded."],
        claim_steps=["Keep invoice ready."],
        alternatives=alternatives,
    )


def test_default_rules_are_estimated_not_confirmed():
    evidence = summary_engine.build_evidence_summary(_warranty("default_rules"))

    assert evidence["status"] == "estimated"
    assert evidence["requires_oem_verification"] is True
    layman = summary_engine.build_layman_summary(_warranty("default_rules"))
    assert "not confirmed" in layman["overview"].lower()


def test_official_scraped_source_is_confirmed_with_source_metadata():
    evidence = summary_engine.build_evidence_summary(
        CanonicalWarranty(
            id="w_hp",
            brand="HP",
            model_code="PROBOOK",
            coverage_months=12,
            terms=["Base parts covered."],
            alternatives={
                "terms_source_type": "scraped",
                "terms_source_url": "https://support.hp.com/warranty",
            },
        )
    )

    assert evidence["status"] == "confirmed"
    assert evidence["sources"][0]["official"] is True
    assert evidence["sources"][0]["url"] == "https://support.hp.com/warranty"


def test_unverified_scraped_source_is_not_confirmed():
    evidence = summary_engine.build_evidence_summary(
        _warranty("scraped", "https://example.com/warranty")
    )

    assert evidence["status"] == "not_confirmed"
    assert evidence["requires_oem_verification"] is True
    assert evidence["sources"][0]["official"] is False


def test_template_summary_includes_evidence_note(monkeypatch):
    monkeypatch.setattr(summary_engine, "_LLM_PROVIDER", "none")

    text, source = summary_engine.summarize_warranty(_warranty("invoice_only"))

    assert source == "template"
    assert "Evidence:" in text
    assert "not confirmed" in text.lower()
