"""Mistral counterparts of the OpenAI invoice and warranty-terms extraction calls.

Every function redacts its input with ``privacy.ai_safe`` before anything is sent. Keys and settings are
read at call time, so a process can switch provider without re-importing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import requests

from .privacy import ai_safe


def _api_url() -> str:
    return os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1").rstrip("/")


def _model() -> str:
    return os.getenv("MISTRAL_MODEL", "mistral-small-latest")


def _timeout() -> float:
    try:
        return float(os.getenv("MISTRAL_TIMEOUT_SEC", "20"))
    except ValueError:
        return 20.0


def mistral_available() -> bool:
    return bool((os.getenv("MISTRAL_API_KEY") or "").strip())


def chat_json(system: str, prompt: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One JSON-mode chat call; (object, error). The prompt is redacted here, whatever the caller did."""
    key = (os.getenv("MISTRAL_API_KEY") or "").strip()
    if not key:
        return None, "MISTRAL_API_KEY not set"
    try:
        resp = requests.post(
            f"{_api_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": _model(),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": ai_safe(prompt)}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=_timeout(),
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Mistral call failed: {exc.__class__.__name__}"
    if resp.status_code != 200:
        return None, f"Mistral error {resp.status_code}"
    try:
        content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content") or ""
        payload = json.loads(content)
    except Exception as exc:
        return None, f"Mistral JSON parse failed: {exc.__class__.__name__}"
    return (payload, None) if isinstance(payload, dict) else (None, "Mistral returned no JSON object")


def request_invoice_enrichment(
    raw_text: str,
    current_fields: Dict[str, Any],
    current_confidence: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    from .openai_intelligence import _OPENAI_MAX_INPUT_CHARS, _VALID_INVOICE_FIELDS, _normalize_enrichment

    keys = ", ".join(sorted(_VALID_INVOICE_FIELDS))
    prompt = (
        "Extract only invoice/product facts that are visible in the text. Do not infer warranty coverage or "
        "legal terms. Empty string means not found. Return a JSON object with keys: "
        f'"fields" (object with string keys {keys}), "confidence" (object with a number 0-1 for each of those '
        'keys), "reasoning" (string), "missing_fields" (array of strings).\n\n'
        f"Current deterministic fields: {json.dumps(current_fields, default=str)}\n"
        f"Current confidence: {json.dumps(current_confidence, default=str)}\n\n"
        f"Invoice text:\n{ai_safe(raw_text)[:_OPENAI_MAX_INPUT_CHARS]}"
    )
    payload, err = chat_json("Return strict JSON only. Never invent missing invoice facts.", prompt)
    if err or payload is None:
        return None, err
    result = _normalize_enrichment(payload)
    result["model"] = _model()
    return result, None
