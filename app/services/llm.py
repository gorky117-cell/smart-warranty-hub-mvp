from typing import Optional, Tuple

import requests

from .connection_registry import registry
from .audit import log_redacted


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


def generate_text(prompt: str, model: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Route LLM generation via registered connectors. Prefers kind=llm, name 'llm-ollama'.
    """
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
