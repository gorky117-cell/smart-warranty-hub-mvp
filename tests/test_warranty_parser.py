from pathlib import Path

from app.db import SessionLocal
from app.services.warranty_parser import parse_terms_from_text, parse_terms_from_url
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
