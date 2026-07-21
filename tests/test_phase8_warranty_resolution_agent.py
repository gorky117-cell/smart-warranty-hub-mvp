from datetime import date, datetime, timedelta
import json

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


def test_warranty_resolution_agent_records_trace_for_disabled_run(tmp_path, monkeypatch):
    trace_path = tmp_path / "agentic_traces.jsonl"
    monkeypatch.setattr(warranty_resolution_agent, "TRACE_PATH", trace_path)
    monkeypatch.delenv("AGENTIC_WORKFLOW_ENABLED", raising=False)

    with SessionLocal() as db:
        out = warranty_resolution_agent.resolve_warranty(
            db,
            user_id="trace_user",
            warranty_id="trace_warranty",
            question="Help",
        )

    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert out["trace_id"] == rows[0]["id"]
    assert rows[0]["status"] == "disabled"
    assert rows[0]["question_present"] is True
    assert "submit_claims" in rows[0]["not_allowed"]
    assert rows[0]["tool_calls"] == []


def test_warranty_resolution_agent_records_tool_trace_for_draft_run(tmp_path, monkeypatch):
    warranty_id = "w_phase8_agent_trace"
    _seed_warranty(warranty_id)
    trace_path = tmp_path / "agentic_traces.jsonl"
    monkeypatch.setattr(warranty_resolution_agent, "TRACE_PATH", trace_path)
    monkeypatch.setenv("AGENTIC_WORKFLOW_ENABLED", "1")

    with SessionLocal() as db:
        out = warranty_resolution_agent.resolve_warranty(
            db,
            user_id="trace_user_enabled",
            warranty_id=warranty_id,
            question=None,
        )

    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert out["trace_id"] == rows[0]["id"]
    assert rows[0]["status"] == "draft"
    assert rows[0]["question_present"] is False
    assert [call["tool"] for call in rows[0]["tool_calls"]] == [
        "get_warranty_record",
        "get_invoice_evidence",
        "retrieve_terms_source",
        "get_risk_care_context",
        "create_draft_claim_checklist",
    ]


def test_warranty_resolution_agent_lists_traces_with_filters(tmp_path, monkeypatch):
    trace_path = tmp_path / "agentic_traces.jsonl"
    monkeypatch.setattr(warranty_resolution_agent, "TRACE_PATH", trace_path)
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "agt_old", "user_id": "u1", "warranty_id": "w1", "status": "disabled"}),
                json.dumps({"id": "agt_mid", "user_id": "u2", "warranty_id": "w2", "status": "draft"}),
                json.dumps({"id": "agt_new", "user_id": "u1", "warranty_id": "w1", "status": "draft"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    latest = warranty_resolution_agent.list_traces(limit=2)
    assert [row["id"] for row in latest] == ["agt_new", "agt_mid"]

    filtered = warranty_resolution_agent.list_traces(user_id="u1", warranty_id="w1", status="draft")
    assert [row["id"] for row in filtered] == ["agt_new"]
