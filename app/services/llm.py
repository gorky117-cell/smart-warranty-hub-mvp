from typing import Optional, Tuple
import os

import requests

from .connection_registry import registry
from .audit import log_redacted

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
_MISTRAL_API = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1")
_MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")


def generate_with_ollama(prompt: str, model: str, endpoint: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        resp = requests.post(
            f"{endpoint.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Ollama call failed: {exc}"
    if resp.status_code != 200:
        return None, f"Ollama error {resp.status_code}: {resp.text}"
    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Ollama response parse failed: {exc}"
    log_redacted("llm_call", f"engine=ollama model={model} prompt={prompt}", keep=64)
    return data.get("response"), None


def _friendly_prompt(prompt: str) -> str:
    # Keep user-facing answers easy to read for non-technical users.
    style = (
        "Answer in simple, non-technical language. "
        "Use short markdown sections and bullets. "
        "Always include: Key Points, What It Means, Next Steps."
    )
    return f"{style}\n\nUser request:\n{prompt}"


def generate_with_mistral(prompt: str, model: str) -> Tuple[Optional[str], Optional[str]]:
    if not _MISTRAL_KEY:
        return None, "MISTRAL_API_KEY not set"
    try:
        resp = requests.post(
            f"{_MISTRAL_API.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {_MISTRAL_KEY}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a clear, practical assistant."},
                    {"role": "user", "content": _friendly_prompt(prompt)},
                ],
                "temperature": 0.2,
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Mistral call failed: {exc}"
    if resp.status_code != 200:
        return None, f"Mistral error {resp.status_code}: {resp.text}"
    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Mistral response parse failed: {exc}"
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    log_redacted("llm_call", f"engine=mistral model={model} prompt={prompt}", keep=64)
    return text, None


def generate_text(prompt: str, model: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Route LLM generation via registered connectors. Prefers kind=llm, name 'llm-ollama'.
    """
    if _LLM_PROVIDER == "mistral":
        return generate_with_mistral(prompt, model or _MISTRAL_MODEL)

    connector = registry.get("llm-ollama") or next(
        (c for c in registry.list("llm").values()), None
    )
    if not connector:
        return None, "No LLM connector registered."
    engine = connector.metadata.get("engine", "ollama")
    chosen_model = model or connector.metadata.get("model", "llama3.2:8b")
    if engine == "ollama":
        return generate_with_ollama(prompt, chosen_model, connector.endpoint)
    return None, f"Unsupported LLM engine: {engine}"


def health() -> Tuple[bool, str, Optional[str]]:
    if _LLM_PROVIDER == "mistral":
        if not _MISTRAL_KEY:
            return False, "MISTRAL_API_KEY not set", _MISTRAL_MODEL
        try:
            resp = requests.get(
                f"{_MISTRAL_API.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {_MISTRAL_KEY}"},
                timeout=5,
            )
            if resp.status_code != 200:
                return False, f"Mistral health error {resp.status_code}", _MISTRAL_MODEL
            return True, "Mistral reachable", _MISTRAL_MODEL
        except requests.exceptions.RequestException as exc:
            return False, f"Mistral unreachable: {exc}", _MISTRAL_MODEL

    connector = registry.get("llm-ollama") or next(
        (c for c in registry.list("llm").values()), None
    )
    if not connector:
        return False, "No LLM connector registered.", None
    model = connector.metadata.get("model", "unknown")
    try:
        resp = requests.post(
            f"{connector.endpoint.rstrip('/')}/api/tags",
            timeout=5,
        )
        if resp.status_code != 200:
            return False, f"Ollama health error {resp.status_code}", model
        return True, "Ollama reachable", model
    except requests.exceptions.RequestException as exc:
        return False, f"Ollama unreachable: {exc}", model
