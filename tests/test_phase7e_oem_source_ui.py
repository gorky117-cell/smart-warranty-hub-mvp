from pathlib import Path


def test_oem_dashboard_shows_controlled_source_verification_card():
    html = Path("templates/oem_dashboard.html").read_text(encoding="utf-8")

    assert 'id="source-verification-card"' in html
    assert "Controlled source verification" in html
    assert "/oem/source-policy" in html
    assert "/oem/adapters" in html
    assert "Broad search" in html
    assert "Controlled adapters" in html
