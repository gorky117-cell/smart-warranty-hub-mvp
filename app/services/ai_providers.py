"""Pick the AI provider for a task (OpenAI or Mistral) and fall back to the other one when it fails or
times out.

- AI_PROVIDER (openai | mistral) chooses the first provider for invoice enrichment and warranty-terms
  extraction; LLM_PROVIDER keeps choosing it for summaries. When unset, each task keeps its historic first
  choice (invoice enrichment: OpenAI; terms extraction: Mistral).
- AI_PROVIDER_FALLBACK (default on) lets the other provider try when the first one fails, times out or
  returns nothing. A provider without a configured key is skipped.
- The text is redacted with ``privacy.ai_safe`` here, before any provider sees it, and every provider
  function redacts again on its own.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .privacy import ai_safe

PROVIDERS = ("openai", "mistral")
Handler = Callable[[str], Tuple[Any, Optional[str]]]


def _truthy(name: str, default: str) -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


def fallback_enabled() -> bool:
    return _truthy("AI_PROVIDER_FALLBACK", "1")


def available(provider: str) -> bool:
    if provider == "openai":
        from .openai_intelligence import openai_available

        return openai_available()
    if provider == "mistral":
        from .mistral_intelligence import mistral_available

        return mistral_available()
    return False


def provider_order(default_first: str, chosen: Optional[str] = None) -> List[str]:
    """Providers to try, in order. Fallback candidates (and an unchosen default) need a configured key."""
    first = (chosen or os.getenv("AI_PROVIDER") or default_first or "").strip().lower()
    if chosen and first in PROVIDERS:
        # An explicitly chosen provider is always tried (it reports its own missing-key error).
        order = [first]
    else:
        order = [first] if first in PROVIDERS and available(first) else []
    if fallback_enabled() or not order:
        order += [p for p in PROVIDERS if p not in order and available(p)]
    return order


def run_with_fallback(
    task: str,
    text: str,
    handlers: Dict[str, Handler],
    *,
    default_first: str,
    chosen: Optional[str] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Try each provider in order until one returns a result. Returns (result or None, meta)."""
    safe_text = ai_safe(text)
    attempts: List[Dict[str, Any]] = []
    for provider in provider_order(default_first, chosen):
        handler = handlers.get(provider)
        if handler is None:
            continue
        started = time.perf_counter()
        try:
            result, err = handler(safe_text)
        except Exception as exc:  # timeouts and client errors count as a failure of this provider
            result, err = None, f"{exc.__class__.__name__}"
        ok = result is not None and not err
        attempts.append(
            {
                "provider": provider,
                "ok": ok,
                "error": None if ok else (str(err or "no result")[:160]),
                "ms": int((time.perf_counter() - started) * 1000),
            }
        )
        if ok:
            return result, {"task": task, "provider": provider, "fallback_used": len(attempts) > 1, "attempts": attempts}
    return None, {"task": task, "provider": None, "fallback_used": len(attempts) > 1, "attempts": attempts}


def invoice_enrichment_enabled() -> bool:
    from .openai_intelligence import invoice_enrichment_enabled as openai_flag

    return _truthy("AI_INVOICE_ENRICHMENT", "0") or openai_flag()


def enrich_invoice(
    raw_text: str,
    current_fields: Dict[str, Any],
    current_confidence: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """AI invoice enrichment with provider fallback; (enrichment or None, meta)."""
    if not invoice_enrichment_enabled():
        return None, {}
    from . import mistral_intelligence, openai_intelligence

    handlers: Dict[str, Handler] = {
        "openai": lambda text: openai_intelligence.request_invoice_enrichment(text, current_fields, current_confidence),
        "mistral": lambda text: mistral_intelligence.request_invoice_enrichment(text, current_fields, current_confidence),
    }
    result, meta = run_with_fallback("invoice_enrichment", raw_text, handlers, default_first="openai")
    return result, meta
