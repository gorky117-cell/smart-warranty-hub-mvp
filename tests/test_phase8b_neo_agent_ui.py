from pathlib import Path


def test_neo_dashboard_has_draft_resolution_checklist_panel():
    html = Path("templates/neo_dashboard.html").read_text(encoding="utf-8")

    assert 'id="agentCard"' in html
    assert "Resolution checklist" in html
    assert "(draft only)" in html
    assert "/agent/warranty-resolution" in html
    assert "fetchResolutionChecklist()" in html
    assert "Draft guidance only" in html
