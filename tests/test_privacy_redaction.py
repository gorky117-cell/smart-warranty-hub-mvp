"""Buyer-data redaction at every AI boundary (fix run B1). Synthetic invoice, fictitious people."""

import json
from types import SimpleNamespace

import pytest

from app.models import CanonicalWarranty
from app.services import llm, openai_intelligence, rag, summary_engine, warranty_parser
from app.services.privacy import REDACTED, ai_safe, redact_text

INVOICE = "\n".join(
    [
        "Croma - Infiniti Retail Ltd",
        "Unit 5, Phoenix Mall, LBS Marg, Mumbai 400070",
        "Phone 022-61234567 care@croma.example",
        "GSTIN: 27AAACI1234A1Z5",
        "TAX INVOICE",
        "Invoice No: CRM/26/5512",
        "Bill To: Asha Verma",
        "Flat 12B, Lake View Apartments, Powai, Mumbai 400076",
        "Mobile: 9876543210",
        "Email: asha.verma@example.com",
        "GSTIN: 27ABCDE1234F1Z5",
        "1 Samsung 55 inch QLED TV QA55Q60D 1 54,990.00",
        "Serial No: 0B7X3HAW500123",
    ]
)
BUYER = ("Asha Verma", "Lake View", "Powai", "400076", "9876543210", "asha.verma@example.com", "27ABCDE1234F1Z5")
SELLER = ("Croma - Infiniti Retail Ltd", "Phoenix Mall", "022-61234567", "care@croma.example", "27AAACI1234A1Z5")
KEPT = ("CRM/26/5512", "QA55Q60D", "0B7X3HAW500123", "Samsung 55 inch QLED TV")


def test_buyer_tokens_masked_seller_and_identifiers_kept():
    redacted, counts = redact_text(INVOICE)
    for value in BUYER:
        assert value not in redacted, value
    for value in SELLER + KEPT:
        assert value in redacted, value
    assert "Bill To: [REDACTED]" in redacted and "Mobile: [REDACTED]" in redacted  # labels kept
    assert counts["buyer_values"] >= 4


def test_phone_and_email_without_any_buyer_label_are_masked_unless_seller_line():
    text = "Thanks for shopping\nContact 9876543210 or a.b@example.com\nCustomer care: 1800-123-4567"
    out = ai_safe(text)
    assert "9876543210" not in out and "a.b@example.com" not in out
    assert "1800-123-4567" in out


def test_user_ids_in_event_documents_are_masked():
    assert ai_safe("user=asha@example.com warranty=w1 type=usage") == f"user={REDACTED} warranty=w1 type=usage"


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


@pytest.fixture
def capture_post(monkeypatch):
    sent = []

    def fake_post(url, *args, **kwargs):
        sent.append(json.dumps(kwargs.get("json", {})))
        return _Resp({"choices": [{"message": {"content": "{}"}}], "data": [{"embedding": [0.1]}], "response": "ok"})

    for module in (llm, rag, warranty_parser, summary_engine):
        monkeypatch.setattr(module.requests, "post", fake_post)
    return sent


def _assert_clean(payloads):
    assert payloads
    for payload in payloads:
        for value in BUYER:
            assert value not in payload, value


def test_mistral_chat_and_ollama_prompts_redacted(monkeypatch, capture_post):
    monkeypatch.setattr(llm, "_MISTRAL_KEY", "test-key")
    llm.generate_with_mistral(INVOICE, "m")
    llm.generate_with_ollama(INVOICE, "m", "http://localhost:1")
    _assert_clean(capture_post)


def test_mistral_terms_enrichment_redacted(monkeypatch, capture_post):
    monkeypatch.setattr(warranty_parser, "_MISTRAL_KEY", "test-key")
    warranty_parser._mistral_enrich_terms(INVOICE)
    _assert_clean(capture_post)


def test_rag_embeddings_redacted(monkeypatch, capture_post):
    monkeypatch.setattr(rag, "_MISTRAL_KEY", "test-key")
    rag._embed(INVOICE + "\nuser=asha.verma@example.com")
    _assert_clean(capture_post)


def test_summary_prompt_redacted_for_every_provider(monkeypatch):
    seen = []
    for name in ("_summarize_with_mistral", "_summarize_with_openai", "_summarize_with_ollama", "_summarize_with_llamacpp"):
        monkeypatch.setattr(summary_engine, name, lambda prompt: (seen.append(prompt), (None, "x"))[1])
    warranty = CanonicalWarranty(id="w1", brand="Samsung", terms=["Contact asha.verma@example.com or 9876543210"])
    for provider in ("mistral", "openai", "ollama_remote", "llamacpp"):
        monkeypatch.setattr(summary_engine, "_LLM_PROVIDER", provider)
        summary_engine.summarize_warranty(warranty)
    assert len(seen) == 4
    _assert_clean(seen)


def test_openai_summary_and_enrichment_redacted_even_with_flags_on(monkeypatch):
    sent = []

    class FakeResponses:
        def create(self, **kwargs):
            sent.append(kwargs["input"])
            return SimpleNamespace(output_text=json.dumps({"fields": {}, "confidence": {}, "reasoning": "", "missing_fields": []}))

    monkeypatch.setenv("OPENAI_ENABLED", "1")
    monkeypatch.setenv("OPENAI_INVOICE_ENRICHMENT", "1")
    monkeypatch.setattr(openai_intelligence, "invoice_enrichment_enabled", lambda: True)
    monkeypatch.setattr(openai_intelligence, "_get_client", lambda: (SimpleNamespace(responses=FakeResponses()), None))
    openai_intelligence.summarize_warranty(INVOICE)
    openai_intelligence.enrich_invoice_fields(INVOICE, {}, {})
    assert len(sent) == 2
    _assert_clean(sent)
    assert all("CRM/26/5512" in payload for payload in sent)


def test_embed_model_reads_mode_and_model(monkeypatch):
    from app.services.rag import embed_model_from_env

    monkeypatch.delenv("MISTRAL_EMBED_MODEL", raising=False)
    monkeypatch.delenv("MISTRAL_EMBED_MODE", raising=False)
    assert embed_model_from_env() == "mistral-embed"
    monkeypatch.setenv("MISTRAL_EMBED_MODE", "mistral-embed-2312")
    assert embed_model_from_env() == "mistral-embed-2312"  # production sets the MODE name
    monkeypatch.setenv("MISTRAL_EMBED_MODE", "auto")
    assert embed_model_from_env() == "mistral-embed"  # not a model name: ignored
    monkeypatch.setenv("MISTRAL_EMBED_MODEL", "codestral-embed")
    assert embed_model_from_env() == "codestral-embed"  # MODEL wins


def test_mistral_summary_helper_redacts_on_its_own(monkeypatch, capture_post):
    monkeypatch.setattr(summary_engine, "_MISTRAL_KEY", "test-key")
    summary_engine._summarize_with_mistral(INVOICE)
    body = str(capture_post[-1])
    assert "9876543210" not in body and "asha" not in body.lower()
