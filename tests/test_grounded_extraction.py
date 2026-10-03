"""Grounded AI extraction, prepared but off by default (work plan step 9). All AI responses are mocked;
the invoice below is synthetic and its personal details are fictitious."""

import json
from types import SimpleNamespace

import pytest

from app.db import SessionLocal
from app.db_models import WarrantyDB
from app.main import _placeholder_upload_warranty
from app.models import ArtifactType
from app.services import grounded_extraction as ge
from app.services import invoice_pipeline, openai_intelligence
from app.services.ingestion import ingest_artifact

INVOICE = "\n".join(
    [
        "Sharma Electronics Pvt Ltd",
        "TAX INVOICE",
        "Invoice No: SE/2026/0417",
        "Date: 14-03-2026",
        "Bill To: Ravi Kumar",
        "12, MG Road, Indiranagar, Bengaluru 560038",
        "Phone: 98450 12345",
        "Email: ravi.k@example.com",
        "1 Samsung Galaxy M17e 5G Mobile 1 12,999.00",
        "Model: SM-M175E",
        "IMEI: 356938035643809",
        "HSN: 85171300",
        "Warranty 12 months",
    ]
)
NO_SERIAL_INVOICE = "\n".join(line for line in INVOICE.splitlines() if not line.startswith("IMEI"))


def _item(value, line, conf=0.9):
    return {"value": value, "source_line": line, "confidence": conf}


GOOD = {
    "model_code": _item("SM-M175E", "Model: SM-M175E"),
    "serial_no": _item("356938035643809", "IMEI: 356938035643809"),
    "invoice_no": _item("SE/2026/0417", "Invoice No: SE/2026/0417"),
}


def test_flag_defaults_off_and_provider_is_not_called(monkeypatch):
    monkeypatch.delenv("GROUNDED_AI_EXTRACTION", raising=False)
    calls = []
    out = ge.apply_grounded_extraction(INVOICE, {"brand": "Samsung"}, {}, {}, provider=lambda t: calls.append(t))
    assert ge.enabled() is False
    assert calls == []
    assert out == ({"brand": "Samsung"}, {}, {})


def test_redaction_removes_customer_details_and_keeps_identifiers():
    redacted, counts = ge.redact_invoice_text(INVOICE)
    for secret in ("Ravi Kumar", "MG Road", "560038", "98450 12345", "ravi.k@example.com"):
        assert secret not in redacted, secret
    for kept in ("SE/2026/0417", "SM-M175E", "356938035643809", "85171300", "Samsung Galaxy M17e"):
        assert kept in redacted, kept
    assert counts["party_lines"] + counts["address_lines"] >= 2
    assert counts["phones"] == 1 and counts["emails"] == 1


def test_provider_only_ever_sees_redacted_text():
    seen = []
    ge.apply_grounded_extraction(INVOICE, {}, {}, {}, provider=lambda text: seen.append(text) or GOOD, force=True)
    assert len(seen) == 1
    assert "Ravi Kumar" not in seen[0] and "98450" not in seen[0] and "ravi.k@" not in seen[0]


def test_grounded_values_are_accepted():
    fields, confidence, alternatives = ge.apply_grounded_extraction(
        INVOICE, {"brand": "Samsung"}, {"brand": 0.85}, {}, provider=lambda _t: GOOD, force=True
    )
    assert fields["model_code"] == "SM-M175E"
    assert fields["serial_no"] == "356938035643809"
    assert fields["invoice_no"] == "SE/2026/0417"
    assert confidence["serial_no"] == 0.9
    assert alternatives["grounded_ai"]["accepted"] == ["invoice_no", "model_code", "serial_no"]


@pytest.mark.parametrize(
    "hallucinated",
    [
        _item("R58N12ABCDE", "Serial No: R58N12ABCDE"),  # source line invented
        _item("R58N12ABCDE", "1 Samsung Galaxy M17e 5G Mobile 1 12,999.00"),  # real line, value not in it
    ],
)
def test_hallucinated_serial_is_blank_when_invoice_has_none(hallucinated):
    payload = {"serial_no": hallucinated, "model_code": _item("", ""), "invoice_no": _item("", "")}
    fields, _conf, alternatives = ge.apply_grounded_extraction(
        NO_SERIAL_INVOICE, {}, {}, {}, provider=lambda _t: payload, force=True
    )
    assert "serial_no" not in fields
    assert alternatives["grounded_ai"]["rejected"]["serial_no"] in {"source_line_not_in_text", "value_not_in_source_line"}


def test_absent_field_reported_by_ai_stays_blank():
    payload = {"serial_no": _item("", ""), "model_code": _item("", ""), "invoice_no": _item("", "")}
    fields, _conf, alternatives = ge.apply_grounded_extraction(NO_SERIAL_INVOICE, {}, {}, {}, provider=lambda _t: payload, force=True)
    assert fields == {}
    assert alternatives["grounded_ai"]["rejected"] == {}


@pytest.mark.parametrize(
    "field,value,line,reason",
    [
        ("invoice_no", "14-03-2026", "Date: 14-03-2026", "looks_like_date"),
        ("invoice_no", "85171300", "HSN: 85171300", "hsn_or_sac_code"),
        ("model_code", "85171300", "HSN: 85171300", "hsn_or_sac_code"),
        ("serial_no", "356938035643808", "IMEI: 356938035643808", "imei_checksum"),
        ("serial_no", "TAXINVOICE1", "Serial: TAXINVOICE1", "serial_implausible"),
        ("invoice_no", "SE/2026/0417", "Invoice No: SE/2026/0417", "low_confidence"),
    ],
)
def test_rule_validation_discards_implausible_values(field, value, line, reason):
    text = INVOICE + "\nIMEI: 356938035643808\nSerial: TAXINVOICE1"
    conf = 0.2 if reason == "low_confidence" else 0.9
    fields, _conf, rejected = ge.validate_ai_fields(text, text, {field: _item(value, line, conf)})
    assert field not in fields
    assert rejected[field] == reason


def test_gstin_is_not_an_invoice_number():
    text = "GSTIN: 29ABCDE1234F1Z5\nInvoice No: A-17"
    fields, _c, rejected = ge.validate_ai_fields(text, text, {"invoice_no": _item("29ABCDE1234F1Z5", "GSTIN: 29ABCDE1234F1Z5")})
    assert rejected["invoice_no"] == "gstin"


def test_pipeline_uses_grounded_values_only_when_flag_on(monkeypatch, tmp_path):
    monkeypatch.setattr(invoice_pipeline, "lookup_terms", lambda *a, **k: None)
    monkeypatch.setattr(invoice_pipeline, "verify_or_suggest", lambda **k: {"verified": True})
    calls = []
    monkeypatch.setattr(ge, "_openai_provider", lambda text: calls.append(text) or GOOD)

    def run():
        path = tmp_path / "invoice.txt"
        path.write_text(INVOICE, encoding="utf-8")
        artifact = ingest_artifact(ArtifactType.invoice, file_path=str(path))
        warranty = _placeholder_upload_warranty(artifact)
        with SessionLocal() as db:
            job = invoice_pipeline.create_job(db, warranty_id=warranty.id, artifact_id=artifact.id, source_path=str(path))
        invoice_pipeline.run_job(job.id)
        with SessionLocal() as db:
            return db.query(WarrantyDB).filter_by(id=warranty.id).first()

    monkeypatch.delenv("GROUNDED_AI_EXTRACTION", raising=False)
    off = run()
    assert calls == []
    assert "grounded_ai" not in (off.alternatives or {})

    monkeypatch.setenv("GROUNDED_AI_EXTRACTION", "1")
    on = run()
    assert len(calls) == 1 and "Ravi Kumar" not in calls[0]
    assert on.serial_no == "356938035643809"
    assert on.model_code == "SM-M175E"
    assert on.alternatives["grounded_ai"]["accepted"] == ["invoice_no", "model_code", "serial_no"]


def test_existing_openai_enrichment_prompt_is_redacted(monkeypatch):
    sent = {}

    class FakeResponses:
        def create(self, **kwargs):
            sent.update(kwargs)
            payload = {"fields": {}, "confidence": {}, "reasoning": "", "missing_fields": []}
            return SimpleNamespace(output_text=json.dumps(payload))

    monkeypatch.setattr(openai_intelligence, "invoice_enrichment_enabled", lambda: True)
    monkeypatch.setattr(openai_intelligence, "_get_client", lambda: (SimpleNamespace(responses=FakeResponses()), None))
    openai_intelligence.enrich_invoice_fields(INVOICE, {}, {})
    assert "Ravi Kumar" not in sent["input"] and "98450 12345" not in sent["input"]
    assert "SE/2026/0417" in sent["input"]
