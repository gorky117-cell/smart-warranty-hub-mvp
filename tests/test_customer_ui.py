"""Live test 1, items 2-3: admin/debug detail hidden from customers; guided check options fit the product."""

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.main import app
from app.services import guided_diagnostics as gd


def _page(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    return client.get("/ui/neo-dashboard").text


# --- item 2 ---------------------------------------------------------------------------------------------------


def test_admin_detail_is_marked_admin_only(monkeypatch):
    html = _page(monkeypatch)
    assert "body:not(.is-admin) .admin-only" in html  # hidden unless /auth/session says role=admin
    assert 'class="field admin-only">\n        <label>Product / Warranty ID</label>' in html
    assert "IS_ADMIN ? `Loaded (variant" in html and "'Product details loaded.'" in html
    assert "if (!IS_ADMIN) { card.style.display = 'none'; return; }" in html  # AGENTIC_WORKFLOW_ENABLED text
    assert "el.innerHTML = IS_ADMIN ? labels" in html  # raw "Summary: template | Terms: ..." line
    assert "(warrantyId && IS_ADMIN)" in html  # no wty_ ids in "Saving for" labels
    assert '<span class="admin-only"> | Warranty: <span id="saveContextWarrantyId">' in html


def test_session_reports_role_used_by_the_page(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    client = TestClient(app)
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert client.get("/auth/session").json()["role"] == "admin"


# --- item 3 ---------------------------------------------------------------------------------------------------


def test_phone_options_have_no_noise_and_a_black_phone_is_not_an_ac():
    flow = gd._question_flow("Samsung Galaxy A15 5G Mobile (Black, 8GB RAM)")
    issue = flow[0]["options"]
    assert "Noise" not in issue and "Unusual noise" not in issue
    assert {"Battery drains fast", "Screen or display problem", "Charging problem"} <= set(issue)
    assert "q_temp" not in [q["id"] for q in flow] and "q_battery" in [q["id"] for q in flow]
    assert "Not cooling" in gd._question_flow("LG 1.5 Ton Split AC")[0]["options"]
    assert gd._probable_issue({"q_issue": "Charging problem"})[0] == "Charging port, cable or adapter issue"


def test_guided_check_uses_a_form_with_nothing_preselected(monkeypatch):
    html = _page(monkeypatch)
    assert "window.prompt(`${q.text}" not in html and "await askDiagQuestion(q)" in html
    assert 'type="radio" name="diagAnswer"' in html and " checked" not in html.split("function askDiagQuestion")[1].split("async function startGuidedDiagFlow")[0]
    assert "${isChoice ? 'disabled' : ''}" in html  # Next is disabled until an answer is picked


def test_guided_session_serves_phone_options(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    with SessionLocal() as db:
        db.query(WarrantyDB).filter_by(id="wty_ui_phone").delete()
        db.add(WarrantyDB(id="wty_ui_phone", brand="Samsung", product_name="Samsung Galaxy M17e 5G Mobile (Vibe Violet)", alternatives={}))
        db.commit()
        session = gd.create_session(db, user_id="admin", warranty_id="wty_ui_phone")
        question = gd.next_question(db, session_id=session.id)["question"]
    assert question["id"] == "q_issue" and "Noise" not in question["options"]
