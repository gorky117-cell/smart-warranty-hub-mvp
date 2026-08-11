from pathlib import Path

from app.db import SessionLocal
from app.models import CanonicalWarranty
from app.services.summary_engine import build_layman_summary
from app.services.warranty_parser import ParsedTerms, parse_terms_from_text, parse_terms_from_url, sanitize_support_items
from app.services.terms_lookup import lookup_terms


def test_parse_terms_from_text():
    text = (
        "Coverage: This product has 24 months warranty.\n"
        "Exclusions:\n"
        "Physical damage\n"
        "Water damage\n"
        "Claim steps:\n"
        "Contact support\n"
        "Provide invoice\n"
    )
    parsed = parse_terms_from_text(text)
    assert parsed.duration_months == 24
    assert "Physical damage" in parsed.exclusions
    assert "Contact support" in parsed.claim_steps


def test_parse_terms_extracts_usage_limits_and_covered_parts():
    text = (
        "Warranty coverage of up to 1 year or 30,000 prints, whichever comes first. "
        "Warranty includes coverage of printhead for high volume printing. "
        "For service support call the OEM helpdesk. "
        "Check repair status from the support page."
    )

    parsed = parse_terms_from_text(text)

    assert parsed.duration_months == 12
    joined_terms = " ".join(parsed.terms).lower()
    assert "30,000 prints" in joined_terms
    assert "whichever comes first" in joined_terms
    assert "printhead" in joined_terms
    joined_claims = " ".join(parsed.claim_steps).lower()
    assert "service support" in joined_claims
    assert "repair status" in joined_claims


def test_parse_terms_does_not_use_extended_plan_as_base_duration():
    text = (
        "Warranty coverage of up to 1 year or 30,000 prints, whichever comes first. "
        "Epson warranty includes coverage of printhead for high volume printing. "
        "Epson CoverPlus extends the standard warranty on our products for up to 5 years, "
        "from the date the product was purchased."
    )

    parsed = parse_terms_from_text(text)

    assert parsed.duration_months == 12
    joined_terms = " ".join(parsed.terms).lower()
    assert "30,000 prints" in joined_terms
    assert "printhead" in joined_terms
    assert "optional extended plan" not in joined_terms
    assert "5 years" not in joined_terms


def test_parse_terms_does_not_invent_base_duration_from_extended_plan_only():
    text = "Optional extended warranty plan available for up to 5 years after product purchase."

    parsed = parse_terms_from_text(text)

    assert parsed.duration_months is None
    assert parsed.terms == []


def test_parse_terms_filters_noisy_extended_plan_navigation():
    text = (
        "Coverage: 12 months warranty from purchase date. "
        "Service Plans. Extended Warranty. Activate Your Service Plan. "
        "Your Warranty and Service Plan details are as follows. "
        "Verify your Epson limited warranty and Service Plans below. "
        "Epson CoverPlus extends the standard warranty on our products for up to 5 years, "
        "from the date the product was purchased. "
        "With CoverPlus."
    )

    parsed = parse_terms_from_text(text)

    assert parsed.duration_months == 12
    extended = [term for term in parsed.terms if term.lower().startswith("optional extended plan")]
    assert extended == []
    joined_terms = " ".join(parsed.terms).lower()
    assert "activate your service plan" not in joined_terms
    assert "with coverplus" not in joined_terms
    assert "coverplus" not in joined_terms


def test_layman_summary_filters_stale_optional_extended_plan_terms():
    warranty = CanonicalWarranty(
        id="wty_test",
        brand="Epson",
        model_code="L3250",
        coverage_months=12,
        terms=[
            "Standard coverage for 12 months from purchase date.",
            "Optional extended plan: Epson CoverPlus extends the standard warranty on our products for up to 5 years.",
            "Warranty includes coverage of printhead for high volume printing.",
        ],
        alternatives={
            "terms_source_type": "approved_oem_source",
            "terms_source_url": "https://www.epson.co.in/product",
        },
    )

    summary = build_layman_summary(warranty)
    joined = " ".join(summary["pros"]).lower()

    assert "12 months" in joined
    assert "printhead" in joined
    assert "coverplus" not in joined
    assert "extended plan" not in joined


def test_layman_summary_turns_oem_text_into_customer_guidance():
    warranty = CanonicalWarranty(
        id="wty_customer_summary",
        brand="Samsung",
        model_code="M17E",
        coverage_months=12,
        terms=[
            "The company's obligation under this warranty shall be limited to repairing or providing replacement of part/s, which are found to be defective.",
            "Standard coverage for 12 months from purchase date.",
        ],
        exclusions=[
            "C-1. Unless stated otherwise, this Warranty does not extend to loss caused by normal wear and tear, fire, water (liquid spillage or ingression).",
        ],
        claim_steps=[
            "and we’ll guide you through the process. We recommend",
            "with us, so that we can help you as quickly and efficiently as possible.",
            "Warranty Checker",
            "Detailed cost & estimated repair time can be confirmed at a Samsung Authorized Service Center.",
        ],
        alternatives={
            "terms_source_type": "approved_oem_source",
            "terms_source_url": "https://www.samsung.com/in/support/warranty/",
        },
    )

    summary = build_layman_summary(warranty)
    joined = " ".join(summary["pros"] + summary["cons"] + summary["claim_friction"]).lower()

    assert "standard warranty coverage shown: 12 months" in joined
    assert "liquid or moisture damage may not be covered" in joined
    assert "check warranty status" in joined
    assert "authorized service center" in joined
    assert "and we’ll guide" not in joined
    assert "with us, so that" not in joined


def test_parse_terms_filters_oem_navigation_marketing_labels():
    text = (
        "Warranty coverage of up to 1 year or 30,000 prints, whichever comes first.\n"
        "Epson warranty includes coverage of printhead for high volume printing.\n"
        "Warranty\n"
        "About Epson\n"
        "Our Purpose\n"
        "Exceptional People\n"
        "Engineered Precision\n"
        "Environmental Pursuit\n"
        "Enduring Partnerships\n"
    )

    parsed = parse_terms_from_text(text)
    joined = " ".join(parsed.terms).lower()

    assert "30,000 prints" in joined
    assert "printhead" in joined
    assert "about epson" not in joined
    assert "our purpose" not in joined
    assert "exceptional people" not in joined
    assert "engineered precision" not in joined
    assert "environmental pursuit" not in joined
    assert "enduring partnerships" not in joined


def test_sanitize_support_items_filters_samsung_menu_noise():
    items = [
        "Please refer to your user manual or warranty card to determine if your model is covered by additional parts warranty.",
        "Show More",
        "Key links",
        "See our latest products",
        "Samsung Care+",
        "Screen Replacement Price",
        "Mobile, Tablet & Laptop",
        "Home Appliance, TV & Audio",
        "How can I find the model number for my product?",
        "Warranty Checker",
        "Detailed cost & estimated repair time can be confirmed at a Samsung Authorized Service Center.",
        "Chat with us to register your product",
    ]

    clean = sanitize_support_items(items)
    joined = " ".join(clean).lower()

    assert "additional parts warranty" in joined
    assert "warranty checker" in joined
    assert "authorized service center" in joined
    assert "chat with us" in joined
    assert "show more" not in joined
    assert "key links" not in joined
    assert "latest products" not in joined
    assert "samsung care" not in joined
    assert "screen replacement price" not in joined
    assert "mobile, tablet" not in joined
    assert "home appliance" not in joined
    assert "model number" not in joined


def test_parse_terms_extracts_non_printer_component_limits():
    text = (
        "Coverage: 24 months warranty from purchase date. "
        "The motor is covered for 10 years when operated under normal use. "
        "Service request must be raised through the official support portal."
    )

    parsed = parse_terms_from_text(text)

    assert parsed.duration_months == 24
    assert any("motor" in term.lower() for term in parsed.terms)
    assert any("service request" in step.lower() for step in parsed.claim_steps)


def test_parse_terms_from_url_html(tmp_path: Path):
    html = (
        "<html><body>"
        "<h1>Warranty</h1>"
        "<p>Coverage: 12 months warranty from purchase date.</p>"
        "<h2>Exclusions</h2><ul><li>Liquid damage</li></ul>"
        "<h2>Claim steps</h2><ol><li>Contact support</li></ol>"
        "</body></html>"
    )
    path = tmp_path / "warranty.html"
    path.write_text(html, encoding="utf-8")
    parsed, err = parse_terms_from_url(str(path))
    assert err is None
    assert parsed is not None
    assert parsed.duration_months == 12


def test_lookup_terms_with_url_override(tmp_path: Path):
    html = (
        "<html><body>"
        "<p>Warranty coverage is 18 months.</p>"
        "<p>Exclusions: misuse, liquid damage.</p>"
        "<p>Claim steps: Contact support.</p>"
        "</body></html>"
    )
    path = tmp_path / "terms.html"
    path.write_text(html, encoding="utf-8")
    with SessionLocal() as db:
        result = lookup_terms(
            db,
            brand="Acmeco",
            category="appliance",
            region=None,
            model_code="ZX-100",
            product_name="Washer",
            url_override=str(path),
            force_refresh=True,
        )
    assert result.duration_months == 18


def test_lookup_terms_blocks_unapproved_manual_url_in_production(tmp_path: Path, monkeypatch):
    html = "<html><body><p>Warranty coverage is 36 months.</p></body></html>"
    path = tmp_path / "unapproved_terms.html"
    path.write_text(html, encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("TERMS_ALLOW_PRODUCTION_MANUAL_URL", raising=False)

    with SessionLocal() as db:
        result = lookup_terms(
            db,
            brand="Acmeco",
            category="appliance",
            region=None,
            model_code="ZX-100",
            product_name="Washer",
            url_override=str(path),
            force_refresh=True,
        )

    assert result.duration_months == 24
    assert result.source_url == "internal://manual_url_blocked_by_oem_policy"


def test_parse_terms_low_confidence_rejects_ungrounded_nlp_enrichment(tmp_path: Path, monkeypatch):
    html = "<html><body><p>Warranty details available from support team.</p></body></html>"
    path = tmp_path / "low_conf.html"
    path.write_text(html, encoding="utf-8")

    monkeypatch.setenv("TERMS_NLP_ENRICH_ENABLED", "1")
    monkeypatch.setenv("TERMS_NLP_MIN_CONFIDENCE", "0.9")

    def _fake_enrich(raw_text: str):
        return (
            ParsedTerms(
                duration_months=24,
                terms=["Covers manufacturing defects."],
                exclusions=["Accidental damage is excluded."],
                claim_steps=["Contact support with invoice."],
                raw_text=None,
                confidence=0.8,
            ),
            None,
        )

    monkeypatch.setattr("app.services.warranty_parser._mistral_enrich_terms", _fake_enrich)
    parsed, err = parse_terms_from_url(str(path))
    assert err is None
    assert parsed is not None
    assert parsed.duration_months is None
    assert "Covers manufacturing defects." not in parsed.terms
    assert "Accidental damage is excluded." not in parsed.exclusions
    assert "Contact support with invoice." not in parsed.claim_steps


def test_parse_terms_low_confidence_uses_grounded_nlp_enrichment(tmp_path: Path, monkeypatch):
    html = (
        "<html><body><p>Warranty coverage is 24 months from purchase date. "
        "Covers manufacturing defects. Accidental damage is excluded. "
        "Contact support with invoice.</p></body></html>"
    )
    path = tmp_path / "grounded_low_conf.html"
    path.write_text(html, encoding="utf-8")

    monkeypatch.setenv("TERMS_NLP_ENRICH_ENABLED", "1")
    monkeypatch.setenv("TERMS_NLP_MIN_CONFIDENCE", "0.9")

    def _fake_enrich(raw_text: str):
        return (
            ParsedTerms(
                duration_months=24,
                terms=["Covers manufacturing defects."],
                exclusions=["Accidental damage is excluded."],
                claim_steps=["Contact support with invoice."],
                raw_text=None,
                confidence=0.8,
            ),
            None,
        )

    monkeypatch.setattr("app.services.warranty_parser._mistral_enrich_terms", _fake_enrich)
    parsed, err = parse_terms_from_url(str(path))
    assert err is None
    assert parsed is not None
    assert parsed.duration_months == 24
    assert "Covers manufacturing defects." in parsed.terms
    assert "Accidental damage is excluded." in parsed.exclusions
    assert "Contact support with invoice." in parsed.claim_steps


def test_parse_terms_keeps_deterministic_duration_when_present(tmp_path: Path, monkeypatch):
    html = "<html><body><p>Coverage: 12 months warranty from purchase date.</p></body></html>"
    path = tmp_path / "deterministic_win.html"
    path.write_text(html, encoding="utf-8")

    monkeypatch.setenv("TERMS_NLP_ENRICH_ENABLED", "1")
    monkeypatch.setenv("TERMS_NLP_MIN_CONFIDENCE", "0.99")

    def _fake_enrich(raw_text: str):
        return (
            ParsedTerms(
                duration_months=36,
                terms=["Extended support terms."],
                exclusions=[],
                claim_steps=[],
                raw_text=None,
                confidence=0.8,
            ),
            None,
        )

    monkeypatch.setattr("app.services.warranty_parser._mistral_enrich_terms", _fake_enrich)
    parsed, err = parse_terms_from_url(str(path))
    assert err is None
    assert parsed is not None
    # Deterministic parser remains primary.
    assert parsed.duration_months == 12
