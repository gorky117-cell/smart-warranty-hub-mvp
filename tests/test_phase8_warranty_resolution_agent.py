from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.db_models import ParsedFieldDB
from app.models import CanonicalWarranty
from app.services import warranty_resolution_agent
from app.storage import store


def _seed_warranty(warranty_id: str) -> None:
    warranty = CanonicalWarranty(
        id=warranty_id,
        product_name="Smart TV",
        brand="Samsung",
        model_code="QLED-55",
        serial_no=None,
        purchase_date=date.today(),
        coverage_months=12,
        expiry_date=date.today() + timedelta(days=300),
        terms=["Manufacturing defects covered under normal usage."],
        exclusions=["Liquid damage is excluded."],
        claim_steps=["Contact Samsung support with invoice and product details."],
        alternatives={
            "terms_source_type": "approved_oem_source",
            "terms_source_url": "https://www.samsung.com/in/support/warranty/",
        },
    )
    store.add_warranty(warranty)
    with SessionLocal() as db:
        db.add(
            ParsedFieldDB(
                warranty_id=warranty_id,
                brand="Samsung",
                model_code="QLED-55",
                product_name="Smart TV",
                product_category="tv",
                serial_no=None,
                invoice_no="INV-AGENT-1",
                purchase_date=datetime.utcnow(),
                confidence={"brand": 0.9, "model_code": 0.8},
                raw_text="Invoice Samsung QLED-55",
            )
        )
        db.commit()


def test_warranty_resolution_agent_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AGENTIC_WORKFLOW_ENABLED", raising=False)

    with SessionLocal() as db:
        out = warranty_resolution_agent.resolve_warranty(db, user_id="u1", warranty_id="missing")

    assert out["status"] == "disabled"
    assert "submit_claims" in out["not_allowed"]
    assert "create_draft_claim_checklist" in out["allowed_tools"]


def test_warranty_resolution_agent_returns_draft_only_when_enabled(monkeypatch):
    warranty_id = "w_phase8_agent_1"
    _seed_warranty(warranty_id)
    monkeypatch.setenv("AGENTIC_WORKFLOW_ENABLED", "1")

    with SessionLocal() as db:
        out = warranty_resolution_agent.resolve_warranty(
            db,
            user_id="phase8_user",
            warranty_id=warranty_id,
            question="Can I claim this?",
        )

    assert out["status"] == "draft"
    assert out["agent"] == "warranty_resolution_agent"
    assert out["question"] == "Can I claim this?"
    assert out["product"]["serial_no_present"] is False
    assert "serial number" in out["missing_or_uncertain"]
    assert any("Do not submit a claim automatically" in item for item in out["draft_claim_checklist"])
    assert "submit_claims" in out["not_allowed"]
    assert all(call["tool"] in warranty_resolution_agent.ALLOWED_TOOLS for call in out["tool_calls"])
    assert "cannot change warranty status" in out["safety_note"]
