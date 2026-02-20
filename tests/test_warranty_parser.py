from pathlib import Path

from app.db import SessionLocal
from app.services.warranty_parser import ParsedTerms, parse_terms_from_text, parse_terms_from_url
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


def test_parse_terms_low_confidence_uses_nlp_enrichment(tmp_path: Path, monkeypatch):
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
