from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Optional, Tuple


_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
_OPENAI_TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT_SEC", "20"))
_OPENAI_MAX_INPUT_CHARS = int(os.getenv("OPENAI_MAX_INPUT_CHARS", "6000"))
_OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "0").strip().lower() in ("1", "true", "yes")
_OPENAI_INVOICE_ENRICHMENT = os.getenv("OPENAI_INVOICE_ENRICHMENT", "0").strip().lower() in ("1", "true", "yes")

_VALID_INVOICE_FIELDS = {
    "brand",
    "product_name",
    "model_code",
    "serial_no",
    "invoice_no",
    "purchase_date",
    "product_category",
}

_client = None


def _api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _openai_configured() -> bool:
    return bool(_OPENAI_ENABLED and _api_key())


def _get_client() -> Tuple[Optional[Any], Optional[str]]:
    global _client
    if not _OPENAI_ENABLED:
        return None, "OPENAI_ENABLED is not set"
    if not _api_key():
        return None, "OPENAI_API_KEY is not set"
    if _client is not None:
        return _client, None
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        return None, f"openai package unavailable: {exc}"
    try:
        _client = OpenAI(api_key=_api_key(), timeout=_OPENAI_TIMEOUT_SEC)
    except Exception as exc:
        return None, f"OpenAI client init failed: {exc}"
    return _client, None


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()
    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks).strip()


def summarize_warranty(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    client, err = _get_client()
    if err or client is None:
        return None, err
    try:
        response = client.responses.create(
            model=_OPENAI_MODEL,
            instructions=(
                "You summarize warranty information for consumers. "
                "Stay grounded in the supplied facts. If a fact is missing, say it is not available."
            ),
            input=prompt,
            temperature=0.2,
            max_output_tokens=350,
        )
    except Exception as exc:
        return None, f"OpenAI summary call failed: {exc}"
    text = _response_text(response)
    return (text or None), None


def invoice_enrichment_enabled() -> bool:
    return bool(_OPENAI_ENABLED and _OPENAI_INVOICE_ENRICHMENT and _api_key())


def _clean_string(value: Any, max_len: int = 120) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_len]


def _normalize_enrichment(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_fields = payload.get("fields") or {}
    raw_confidence = payload.get("confidence") or {}
    fields: Dict[str, str] = {}
    confidence: Dict[str, float] = {}
    for key in _VALID_INVOICE_FIELDS:
        value = _clean_string(raw_fields.get(key))
        if value:
            fields[key] = value
            try:
                score = float(raw_confidence.get(key, 0.5))
            except (TypeError, ValueError):
                score = 0.5
            confidence[key] = max(0.0, min(score, 0.85))
    return {
        "fields": fields,
        "confidence": confidence,
        "reasoning": _clean_string(payload.get("reasoning"), 300),
        "missing_fields": [
            _clean_string(item, 80)
            for item in (payload.get("missing_fields") or [])
            if _clean_string(item, 80)
        ][:10],
        "model": _OPENAI_MODEL,
    }


def enrich_invoice_fields(
    raw_text: str,
    current_fields: Dict[str, Any],
    current_confidence: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not invoice_enrichment_enabled():
        return None
    client, err = _get_client()
    if err or client is None:
        return None
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fields": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "string"} for key in sorted(_VALID_INVOICE_FIELDS)},
                "required": sorted(_VALID_INVOICE_FIELDS),
            },
            "confidence": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "number"} for key in sorted(_VALID_INVOICE_FIELDS)},
                "required": sorted(_VALID_INVOICE_FIELDS),
            },
            "reasoning": {"type": "string"},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["fields", "confidence", "reasoning", "missing_fields"],
    }
    prompt = (
        "Extract only invoice/product facts that are visible in the text. "
        "Do not infer warranty coverage or legal terms. Empty string means not found.\n\n"
        f"Current deterministic fields: {json.dumps(current_fields, default=str)}\n"
        f"Current confidence: {json.dumps(current_confidence, default=str)}\n\n"
        f"Invoice text:\n{raw_text[:_OPENAI_MAX_INPUT_CHARS]}"
    )
    try:
        response = client.responses.create(
            model=_OPENAI_MODEL,
            instructions="Return strict JSON only. Never invent missing invoice facts.",
            input=prompt,
            temperature=0,
            max_output_tokens=500,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "invoice_enrichment",
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        payload = json.loads(_response_text(response))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _normalize_enrichment(payload)


def merge_invoice_enrichment(
    fields: Dict[str, Any],
    confidence: Dict[str, Any],
    enrichment: Optional[Dict[str, Any]],
    *,
    replace_below: float = 0.65,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    if not enrichment:
        return fields, confidence, {}
    merged_fields = dict(fields)
    merged_confidence = dict(confidence)
    changed: list[str] = []
    source_fields = enrichment.get("fields") or {}
    source_confidence = enrichment.get("confidence") or {}
    for key, value in source_fields.items():
        if key not in _VALID_INVOICE_FIELDS or not value:
            continue
        try:
            existing_score = float(merged_confidence.get(key, 0.0))
        except (TypeError, ValueError):
            existing_score = 0.0
        if not merged_fields.get(key) or existing_score < replace_below:
            merged_fields[key] = value
            try:
                proposed_score = float(source_confidence.get(key, 0.5))
            except (TypeError, ValueError):
                proposed_score = 0.5
            merged_confidence[key] = max(existing_score, min(proposed_score, 0.85))
            changed.append(key)
    meta = {
        "used": bool(changed),
        "model": enrichment.get("model") or _OPENAI_MODEL,
        "fields": changed,
        "reasoning": enrichment.get("reasoning") or "",
        "missing_fields": enrichment.get("missing_fields") or [],
    }
    return merged_fields, merged_confidence, meta


def health() -> Tuple[bool, str, Optional[str]]:
    if not _OPENAI_ENABLED:
        return False, "OPENAI_ENABLED is not set", _OPENAI_MODEL
    if not _api_key():
        return False, "OPENAI_API_KEY is not set", _OPENAI_MODEL
    try:
        from openai import OpenAI  # noqa: F401
    except Exception as exc:
        return False, f"openai package unavailable: {exc}", _OPENAI_MODEL
    return True, "OpenAI configured", _OPENAI_MODEL
