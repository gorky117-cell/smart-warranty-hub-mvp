from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import requests

from ..models import CanonicalWarranty

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
_LLM_TTL_SEC = int(os.getenv("LLM_ENGINE_TTL_SEC", "900"))
_LLAMA_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
_OLLAMA_URL = os.getenv("OLLAMA_URL")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

_llama_instance = None
_llama_last_used = 0.0


def _now() -> float:
    return time.time()


def _should_unload(last_used: float) -> bool:
    if not last_used:
        return False
    return (_now() - last_used) > _LLM_TTL_SEC


def _template_summary(warranty: CanonicalWarranty) -> str:
    terms = warranty.terms or []
    exclusions = warranty.exclusions or []
    claim_steps = warranty.claim_steps or []
    lines = [
        f"Product: {warranty.brand or 'N/A'} {warranty.model_code or 'N/A'}",
        f"Purchase date: {warranty.purchase_date or 'N/A'}",
        f"Expiry date: {warranty.expiry_date or 'N/A'}",
        f"Coverage months: {warranty.coverage_months or 'N/A'}",
        "Coverage / Terms: " + ("; ".join(terms) if terms else "Not available yet."),
        "Exclusions: " + ("; ".join(exclusions) if exclusions else "Not available yet."),
        "Claim steps: " + ("; ".join(claim_steps) if claim_steps else "Not available yet."),
    ]
    return "\n".join(lines)


def _summarize_with_ollama(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    if not _OLLAMA_URL:
        return None, "OLLAMA_URL not set"
    try:
        resp = requests.post(
            f"{_OLLAMA_URL.rstrip('/')}/api/generate",
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Ollama call failed: {exc}"
    if resp.status_code != 200:
        return None, f"Ollama error {resp.status_code}: {resp.text}"
    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Ollama parse failed: {exc}"
    return data.get("response"), None


def _summarize_with_llamacpp(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    global _llama_instance, _llama_last_used
    if not _LLAMA_MODEL_PATH:
        return None, "LLM_MODEL_PATH not set"
    if _llama_instance is not None and _should_unload(_llama_last_used):
        _llama_instance = None
    if _llama_instance is None:
        try:
            from llama_cpp import Llama  # type: ignore
        except Exception as exc:
            return None, f"llama_cpp unavailable: {exc}"
        try:
            _llama_instance = Llama(model_path=_LLAMA_MODEL_PATH)
        except Exception as exc:
            return None, f"llama_cpp init failed: {exc}"
    _llama_last_used = _now()
    try:
        out = _llama_instance(prompt, max_tokens=200)
        text = out.get("choices", [{}])[0].get("text", "").strip()
        return text or None, None
    except Exception as exc:
        return None, f"llama_cpp generation failed: {exc}"


def summarize_warranty(warranty: CanonicalWarranty) -> Tuple[str, str]:
    """
    Returns (summary_text, source).
    """
    if _LLM_PROVIDER == "none":
        return _template_summary(warranty), "template"

    prompt = (
        "Summarize the warranty in under 120 words; list coverage, exclusions, expiry, and claim steps. "
        "Return plain text.\n\n"
        f"Brand: {warranty.brand}\nModel: {warranty.model_code}\nExpiry: {warranty.expiry_date}\n"
        f"Coverage months: {warranty.coverage_months}\nTerms: {warranty.terms}\nExclusions: {warranty.exclusions}\n"
        f"Claim steps: {warranty.claim_steps}\n"
    )
    if _LLM_PROVIDER == "ollama_remote":
        text, err = _summarize_with_ollama(prompt)
        return (text or _template_summary(warranty)), "ollama" if text else "template"
    if _LLM_PROVIDER == "llamacpp":
        text, err = _summarize_with_llamacpp(prompt)
        return (text or _template_summary(warranty)), "llamacpp" if text else "template"
    return _template_summary(warranty), "template"


def health() -> Tuple[bool, str, Optional[str]]:
    if _LLM_PROVIDER == "none":
        return False, "LLM_PROVIDER=none (disabled)", None
    if _LLM_PROVIDER == "ollama_remote":
        if not _OLLAMA_URL:
            return False, "OLLAMA_URL not set", _OLLAMA_MODEL
        try:
            resp = requests.post(f"{_OLLAMA_URL.rstrip('/')}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False, f"Ollama health error {resp.status_code}", _OLLAMA_MODEL
            return True, "Ollama reachable", _OLLAMA_MODEL
        except requests.exceptions.RequestException as exc:
            return False, f"Ollama unreachable: {exc}", _OLLAMA_MODEL
    if _LLM_PROVIDER == "llamacpp":
        if not _LLAMA_MODEL_PATH:
            return False, "LLM_MODEL_PATH not set", "llamacpp"
        return True, "llama_cpp configured", "llamacpp"
    return False, f"Unsupported LLM_PROVIDER: {_LLM_PROVIDER}", None
