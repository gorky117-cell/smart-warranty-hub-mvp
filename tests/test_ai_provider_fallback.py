"""Provider fallback (OpenAI <-> Mistral) with mocked failures; both providers only see redacted text."""

import json
from types import SimpleNamespace

import pytest
import requests

from app.models import CanonicalWarranty
from app.services import ai_providers, mistral_intelligence, openai_intelligence, summary_engine, warranty_parser

INVOICE = "\n".join([
    "Croma - Infiniti Retail Ltd",
    "TAX INVOICE",
    "Bill To: Asha Verma",
    "Flat 12B, Lake View Apartments, Powai, Mumbai 400076",
    "Mobile: 9876543210",
    "Email: asha.verma@example.com",
    "1 Samsung 55 inch QLED TV QA55Q60D 1 54,990.00",
])
BUYER = ("Asha Verma", "Lake View", "9876543210", "asha.verma@example.com")


def _clean(text):
    assert not any(b.lower() in str(text).lower() for b in BUYER), text


@pytest.fixture
def both_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.setattr(openai_intelligence, "_OPENAI_ENABLED", True)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_PROVIDER_FALLBACK", raising=False)


def test_primary_timeout_falls_back_and_both_get_redacted_text(both_keys):
    seen = {}

    def openai_handler(text):
        seen["openai"] = text
        raise requests.exceptions.Timeout()

    def mistral_handler(text):
        seen["mistral"] = text
        return "ok", None

    result, meta = ai_providers.run_with_fallback(
        "t", INVOICE, {"openai": openai_handler, "mistral": mistral_handler}, default_first="openai"
    )
    assert result == "ok" and meta["provider"] == "mistral" and meta["fallback_used"] is True
    assert meta["attempts"][0] == {**meta["attempts"][0], "provider": "openai", "ok": False, "error": "Timeout"}
    _clean(seen["openai"]), _clean(seen["mistral"])
    assert "QA55Q60D" in seen["mistral"]  # product identifiers are kept


def test_error_result_also_falls_back(both_keys):
    result, meta = ai_providers.run_with_fallback(
        "t", "x", {"mistral": lambda t: (None, "Mistral error 503"), "openai": lambda t: ("ok", None)}, default_first="mistral"
    )
    assert result == "ok" and [a["provider"] for a in meta["attempts"]] == ["mistral", "openai"]


def test_fallback_can_be_switched_off(both_keys, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_FALLBACK", "0")
    calls = []
    result, meta = ai_providers.run_with_fallback(
        "t", "x", {"openai": lambda t: calls.append("openai") or (None, "down"), "mistral": lambda t: calls.append("mistral") or ("ok", None)},
        default_first="openai",
    )
    assert result is None and calls == ["openai"]


def test_provider_without_a_key_is_never_a_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(openai_intelligence, "_OPENAI_ENABLED", True)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert ai_providers.provider_order("openai") == ["openai"]
    assert ai_providers.provider_order("mistral") == ["openai"]  # unchosen default without key: skipped
    monkeypatch.setenv("AI_PROVIDER", "mistral")
    assert ai_providers.provider_order("openai") == ["openai"]


def test_both_failing_returns_nothing(both_keys):
    result, meta = ai_providers.run_with_fallback(
        "t", "x", {"openai": lambda t: (_ for _ in ()).throw(TimeoutError()), "mistral": lambda t: (None, "Mistral error 500")},
        default_first="openai",
    )
    assert result is None and meta["provider"] is None and len(meta["attempts"]) == 2


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


def test_invoice_enrichment_falls_back_to_mistral(both_keys, monkeypatch):
    monkeypatch.setenv("AI_INVOICE_ENRICHMENT", "1")
    monkeypatch.setattr(openai_intelligence, "request_invoice_enrichment", lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    sent = []
    content = json.dumps({"fields": {"brand": "Samsung", "model_code": "QA55Q60D"}, "confidence": {"brand": 0.9, "model_code": 0.8},
                          "reasoning": "", "missing_fields": []})

    def fake_post(url, *args, **kwargs):
        sent.append(json.dumps(kwargs.get("json")))
        return _Resp({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(mistral_intelligence.requests, "post", fake_post)
    result, meta = ai_providers.enrich_invoice(INVOICE, {}, {})
    assert meta["provider"] == "mistral" and meta["fallback_used"] is True
    assert result["fields"] == {"brand": "Samsung", "model_code": "QA55Q60D"}
    assert result["confidence"]["brand"] == 0.85  # capped as for OpenAI
    _clean(sent[0])


def test_invoice_enrichment_off_by_default(monkeypatch):
    monkeypatch.delenv("AI_INVOICE_ENRICHMENT", raising=False)
    monkeypatch.setattr(openai_intelligence, "_OPENAI_INVOICE_ENRICHMENT", False)
    assert ai_providers.enrich_invoice(INVOICE, {}, {}) == (None, {})


def test_summary_falls_back_from_mistral_to_openai(both_keys, monkeypatch):
    monkeypatch.setattr(summary_engine, "_LLM_PROVIDER", "mistral")
    monkeypatch.setattr(summary_engine, "_RAG_ENABLED", False)
    prompts = {}

    def mistral_down(prompt):
        prompts["mistral"] = prompt
        raise requests.exceptions.ConnectTimeout()

    def openai_up(prompt):
        prompts["openai"] = prompt
        return "Covered for 12 months.", None

    monkeypatch.setattr(summary_engine, "_summarize_with_mistral", mistral_down)
    monkeypatch.setattr(summary_engine, "_summarize_with_openai", openai_up)
    warranty = CanonicalWarranty(id="w1", product_name="TV", brand="Samsung", terms=[INVOICE], alternatives={})
    text, source = summary_engine.summarize_warranty(warranty)
    assert (text, source) == ("Covered for 12 months.", "openai")
    _clean(prompts["mistral"]), _clean(prompts["openai"])


def test_summary_template_when_both_fail(both_keys, monkeypatch):
    monkeypatch.setattr(summary_engine, "_LLM_PROVIDER", "mistral")
    monkeypatch.setattr(summary_engine, "_RAG_ENABLED", False)
    monkeypatch.setattr(summary_engine, "_summarize_with_mistral", lambda p: (None, "Mistral error 500"))
    monkeypatch.setattr(summary_engine, "_summarize_with_openai", lambda p: (None, "OpenAI summary call failed"))
    warranty = CanonicalWarranty(id="w2", product_name="TV", brand="Samsung", alternatives={})
    assert summary_engine.summarize_warranty(warranty)[1] == "template"


def test_terms_extraction_falls_back_to_openai(both_keys, monkeypatch):
    monkeypatch.setattr(warranty_parser, "_mistral_enrich_terms", lambda t: (None, "Mistral call failed: ReadTimeout"))
    page = "Warranty: 24 months from purchase. Exclusions: liquid damage. Contact: support desk."
    seen = []

    def fake_terms(text):
        seen.append(text)
        return {"duration_months": 24, "terms": ["24 months"], "exclusions": ["liquid damage"], "claim_steps": []}, None

    monkeypatch.setattr(openai_intelligence, "request_terms_json", fake_terms)
    parsed, meta = warranty_parser._ai_enrich_terms(page + "\n" + INVOICE)
    assert meta["provider"] == "openai" and parsed.duration_months == 24 and parsed.exclusions == ["liquid damage"]
    _clean(seen[0])
