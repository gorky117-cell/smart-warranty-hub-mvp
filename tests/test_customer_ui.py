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


# --- items 8 and 10: care tips tied to the terms; "How to look after it" ---------------------------------------

import json  # noqa: E402
from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

from app.models import CanonicalWarranty  # noqa: E402
from app.services.customer_content import tidy  # noqa: E402
from app.services.product_recommendations import build_product_recommendations  # noqa: E402

_SAMSUNG = json.loads((Path(__file__).parent / "fixtures" / "oem_terms_captured_2026-10-02.json").read_text(encoding="utf-8"))["samsung"]["parsed"]


def _m17e(**kw):
    base = dict(id="w", brand="Samsung", model_code="M17E", product_name="Samsung Galaxy M17e 5G Mobile",
                purchase_date=date(2026, 5, 1), coverage_months=12, terms=_SAMSUNG["terms"],
                exclusions=_SAMSUNG["exclusions"], claim_steps=_SAMSUNG["claim_steps"],
                alternatives={"terms_source_url": "https://www.samsung.com/in/support/warranty/"})
    base.update(kw)
    return tidy(CanonicalWarranty(**base)).model_dump()


def test_care_tips_follow_the_exclusions_with_varied_priority():
    tips = build_product_recommendations("u", "w", warranty=_m17e(), predictive={"risk_label": "LOW"})
    care = [t for t in tips if t["action"] == "oem_derived_care"]
    assert care[0]["title"] == "Charge with the original charger and use surge protection"
    assert care[0]["why"].startswith("Samsung's terms exclude damage from lightning and abnormal voltage.")
    assert len({t["risk_band"] for t in care}) >= 2  # not all MEDIUM any more
    assert [t["priority"] for t in care] == sorted(t["priority"] for t in care)
    # only a statement about where repairs happen -> a grounded line, no "void" claim
    assert any(t["why"] == "Repairs are done at Samsung authorized service centres." for t in care)


def test_appliance_power_tip_and_no_tips_without_terms():
    fridge = build_product_recommendations("u", "w", warranty={
        "brand": "LG", "product_name": "LG Refrigerator 260L", "exclusions": ["Damage due to voltage fluctuation is excluded."],
        "alternatives": {"terms_source_url": "https://www.lg.com/in/support/"}}, predictive={})
    assert any(t["title"] == "Use a stabilizer or surge protector" for t in fridge)
    bare = build_product_recommendations("u", "w", warranty={"brand": "LG", "product_name": "LG Refrigerator"}, predictive={})
    assert not any(t["action"] == "oem_derived_care" for t in bare)


def test_care_section_shows_tips_or_hides(monkeypatch):
    html = _page(monkeypatch)
    assert '<details id="careSection" style="display:none;">' in html  # hidden until there are real tips
    assert "renderCareTips(allProductRecs)" in html and "if (!list.length) { section.style.display = 'none';" in html
    body = html.split("function renderAdvisories(adv) {")[1].split("}")[0]
    assert "innerHTML" not in body  # generic nudges ("Coverage Quick View") no longer fill it


# --- item 11: notes wording matches what the code does -----------------------------------------------------------


def test_notes_wording_matches_the_code(monkeypatch):
    from app.services import predictive, telemetry_intelligence

    html = _page(monkeypatch)
    assert "These notes are used only to personalize care guidance" not in html
    assert "Optional notes help improve risk insights and reminders." not in html
    expected = (f"only for groups of at least {telemetry_intelligence._MIN_OEM_COHORT} people")
    assert html.count(expected) == 2 and "__SWH_OEM_MIN_COHORT__" not in html
    # the claims in the text hold: errors/failures raise, maintenance lowers, usage hours are read as a number
    ev = lambda t, payload=None: type("E", (), {"event_type": t, "payload": payload or {}})()  # noqa: E731
    base = predictive.derive_score([])[0]
    assert predictive.derive_score([ev("error"), ev("failure")])[0] > base
    assert predictive.derive_score([ev("maintenance")])[0] < base
    assert predictive.derive_score([ev("usage", {"hours": 500})])[0] > base
    clean = telemetry_intelligence.sanitize_payload({"note": "x", "phone": "9876543210"})
    assert "phone" not in clean  # identifiers are dropped before saving
    assert "payload.hours = hours" in html and "document.getElementById('telStatus').textContent = 'Saved.';" in html
