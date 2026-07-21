from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import requests

from ..models import CanonicalWarranty
from .source_trust import classify_terms_source

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
_LLM_TTL_SEC = int(os.getenv("LLM_ENGINE_TTL_SEC", "900"))
_LLAMA_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
_OLLAMA_URL = os.getenv("OLLAMA_URL")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
_MISTRAL_API = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1")
_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
_MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
_OPENAI_FALLBACK_PROVIDER = os.getenv("OPENAI_FALLBACK_PROVIDER", "template").lower()
_RAG_ENABLED = os.getenv("RAG_ENABLED", "0").strip().lower() in ("1", "true", "yes")

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
    evidence = build_evidence_summary(warranty)
    lines = [
        f"Product: {warranty.brand or 'N/A'} {warranty.model_code or 'N/A'}",
        f"Purchase date: {warranty.purchase_date or 'N/A'}",
        f"Expiry date: {warranty.expiry_date or 'N/A'}",
        f"Coverage months: {warranty.coverage_months or 'N/A'}",
        f"Evidence: {evidence['status_label']} - {evidence['note']}",
        "Coverage / Terms: " + ("; ".join(terms) if terms else "Not available yet."),
        "Exclusions: " + ("; ".join(exclusions) if exclusions else "Not available yet."),
        "Claim steps: " + ("; ".join(claim_steps) if claim_steps else "Not available yet."),
    ]
    return "\n".join(lines)


def build_evidence_summary(warranty: CanonicalWarranty) -> Dict[str, object]:
    """
    Additive trust layer for warranty terms.
    It labels whether the terms are confirmed, cached, estimated, or not confirmed
    without changing the underlying warranty/scoring logic.
    """
    alt = getattr(warranty, "alternatives", None) or {}
    source_type = (alt.get("terms_source_type") or "unknown").strip() or "unknown"
    source_url = alt.get("terms_source_url")
    refreshed_at = alt.get("terms_last_refreshed_at")

    source_trust = classify_terms_source(
        brand=getattr(warranty, "brand", None),
        source_url=source_url,
        source_type=source_type,
    )

    if source_type == "scraped" and source_url:
        if source_trust.get("verified") or source_trust.get("official"):
            status = "confirmed"
        else:
            status = "not_confirmed"
        label = source_trust["label"]
        note = source_trust["note"]
        confidence = source_trust["confidence"]
    elif source_type == "internal_warranty_db":
        status = "confirmed_internal"
        label = "Confirmed from saved warranty record"
        note = "Warranty terms came from an existing saved warranty record."
        confidence = 0.8
    elif source_type == "internal_terms_cache":
        status = "cached"
        label = "Cached source"
        note = "Warranty terms came from the local terms cache. Refresh from OEM source if claim certainty is required."
        confidence = 0.7
    elif source_type == "default_rules":
        status = "estimated"
        label = "Estimated, not confirmed"
        note = "Warranty terms are estimated from category/default rules, not confirmed by an OEM source."
        confidence = 0.45
    elif source_type == "invoice_only":
        status = "not_confirmed"
        label = "Not confirmed"
        note = "Invoice data was found, but official warranty terms have not been confirmed."
        confidence = 0.35
    else:
        status = "not_confirmed"
        label = "Not confirmed"
        note = "Source evidence is missing. Do not treat these warranty terms as confirmed."
        confidence = 0.3

    sources = []
    if source_url:
        sources.append(
            {
                "title": "Warranty terms source",
                "url": source_url,
                "source_type": source_type,
                "trust_status": source_trust.get("status"),
                "official": source_trust.get("official", False),
                "verified": source_trust.get("verified", False),
                "host": source_trust.get("host"),
                "fetched_at": refreshed_at,
                "confidence": confidence,
            }
        )
    return {
        "status": status,
        "status_label": label,
        "source_type": source_type,
        "source_url": source_url,
        "last_refreshed_at": refreshed_at,
        "confidence": confidence,
        "requires_oem_verification": bool(source_trust.get("requires_oem_verification"))
        or status in {"estimated", "not_confirmed", "cached"},
        "note": note,
        "sources": sources,
        "source_trust": source_trust,
    }


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


def _summarize_with_mistral(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    if not _MISTRAL_KEY:
        return None, "MISTRAL_API_KEY not set"
    try:
        resp = requests.post(
            f"{_MISTRAL_API.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {_MISTRAL_KEY}"},
            json={
                "model": _MISTRAL_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a warranty summary assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=20,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Mistral call failed: {exc}"
    if resp.status_code != 200:
        return None, f"Mistral error {resp.status_code}: {resp.text}"
    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Mistral parse failed: {exc}"
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return (text.strip() if text else None), None


def _summarize_with_openai(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        from .openai_intelligence import summarize_warranty as openai_summarize
    except Exception as exc:
        return None, f"OpenAI helper unavailable: {exc}"
    return openai_summarize(prompt)


def _fallback_summary(prompt: str, warranty: CanonicalWarranty) -> Tuple[str, str]:
    if _OPENAI_FALLBACK_PROVIDER == "mistral":
        text, _ = _summarize_with_mistral(prompt)
        if text:
            return text, "mistral"
    if _OPENAI_FALLBACK_PROVIDER == "ollama_remote":
        text, _ = _summarize_with_ollama(prompt)
        if text:
            return text, "ollama"
    if _OPENAI_FALLBACK_PROVIDER == "llamacpp":
        text, _ = _summarize_with_llamacpp(prompt)
        if text:
            return text, "llamacpp"
    return _template_summary(warranty), "template"


def summarize_warranty(warranty: CanonicalWarranty) -> Tuple[str, str]:
    """
    Returns (summary_text, source).
    """
    if _LLM_PROVIDER == "none":
        return _template_summary(warranty), "template"

    evidence = build_evidence_summary(warranty)
    prompt = (
        "Summarize the warranty in under 120 words; list coverage, exclusions, expiry, and claim steps. "
        "Do not present estimated or invoice-only terms as confirmed. "
        "If evidence_status is not confirmed, explicitly say the terms are not confirmed and should be verified with OEM. "
        "Return plain text.\n\n"
        f"Evidence status: {evidence['status_label']}\nEvidence note: {evidence['note']}\n"
        f"Brand: {warranty.brand}\nModel: {warranty.model_code}\nExpiry: {warranty.expiry_date}\n"
        f"Coverage months: {warranty.coverage_months}\nTerms: {warranty.terms}\nExclusions: {warranty.exclusions}\n"
        f"Claim steps: {warranty.claim_steps}\n"
    )
    if _RAG_ENABLED:
        try:
            from ..db import SessionLocal
            from .rag import build_context, rag_enabled
            if rag_enabled():
                query = f"{warranty.brand} {warranty.model_code} warranty terms exclusions claim steps"
                with SessionLocal() as db:
                    ctx = build_context(db, query_text=query, limit=4)
                if ctx:
                    prompt = prompt + "\nRelevant context:\n" + ctx
        except Exception:
            pass
    if _LLM_PROVIDER == "mistral":
        text, err = _summarize_with_mistral(prompt)
        return (text or _template_summary(warranty)), "mistral" if text else "template"
    if _LLM_PROVIDER == "openai":
        text, err = _summarize_with_openai(prompt)
        if text:
            return text, "openai"
        return _fallback_summary(prompt, warranty)
    if _LLM_PROVIDER == "ollama_remote":
        text, err = _summarize_with_ollama(prompt)
        return (text or _template_summary(warranty)), "ollama" if text else "template"
    if _LLM_PROVIDER == "llamacpp":
        text, err = _summarize_with_llamacpp(prompt)
        return (text or _template_summary(warranty)), "llamacpp" if text else "template"
    return _template_summary(warranty), "template"


def build_structured_summary(warranty: CanonicalWarranty) -> Dict[str, object]:
    points = []
    tags = []
    if warranty.coverage_months:
        points.append(f"Coverage: {warranty.coverage_months} months")
        tags.append("coverage")
    if warranty.expiry_date:
        points.append(f"Expiry date: {warranty.expiry_date}")
        tags.append("expiry")
    if warranty.terms:
        points.extend([f"Term: {t}" for t in warranty.terms[:5]])
        tags.append("terms")
    if warranty.exclusions:
        points.extend([f"Exclusion: {e}" for e in warranty.exclusions[:5]])
        tags.append("exclusions")
    if warranty.claim_steps:
        points.extend([f"Claim: {c}" for c in warranty.claim_steps[:5]])
        tags.append("claims")
    if warranty.brand:
        tags.append(warranty.brand.lower())
    if warranty.model_code:
        tags.append(warranty.model_code.lower())
    return {"points": points, "tags": list(dict.fromkeys(tags))}


def build_layman_summary(warranty: CanonicalWarranty) -> Dict[str, object]:
    """
    Human-friendly warranty explanation for non-technical users.
    Additive helper: does not change core predictive/terms logic.
    """
    terms = [str(t).strip() for t in (warranty.terms or []) if str(t).strip()]
    exclusions = [str(e).strip() for e in (warranty.exclusions or []) if str(e).strip()]
    claim_steps = [str(c).strip() for c in (warranty.claim_steps or []) if str(c).strip()]
    evidence = build_evidence_summary(warranty)

    product = " ".join([x for x in [warranty.brand, warranty.model_code] if x]) or (warranty.product_name or "product")
    coverage = f"{warranty.coverage_months} months" if warranty.coverage_months else "not clearly stated"

    pros = terms[:4] if terms else ["Coverage details are partially available from current records."]
    cons = exclusions[:4] if exclusions else ["No explicit exclusions were parsed yet. Please verify on OEM page/bill."]

    claim_friction = []
    if claim_steps:
        claim_friction.extend(claim_steps[:3])
    else:
        claim_friction.append("Claim process is not fully available yet.")

    fine_print = []
    low_all = " ".join(exclusions).lower()
    checks = [
        ("physical damage", "Physical damage is usually excluded."),
        ("liquid", "Liquid damage is often excluded."),
        ("unauthor", "Unauthorized repair can void coverage."),
        ("wear", "Normal wear-and-tear may not be covered."),
        ("consum", "Consumables are usually not covered."),
    ]
    for key, note in checks:
        if key in low_all:
            fine_print.append(note)
    if not fine_print:
        fine_print.append("Read exclusions carefully before raising a claim.")

    red_flags = []
    if not warranty.coverage_months:
        red_flags.append("Coverage term is unclear. Verify with OEM source.")
    if not warranty.expiry_date and warranty.purchase_date and warranty.coverage_months:
        red_flags.append("Expiry date is derived estimate from purchase date + coverage.")
    if not terms and not exclusions and not claim_steps:
        red_flags.append("Only limited warranty text was found; confidence may be low.")

    if evidence["status"] in {"confirmed", "confirmed_internal"}:
        overview = f"For {product}, expected coverage is {coverage}. {evidence['note']}"
    else:
        overview = (
            f"For {product}, expected coverage is {coverage}, but the warranty terms are not confirmed. "
            f"{evidence['note']}"
        )

    return {
        "overview": overview,
        "pros": pros,
        "cons": cons,
        "fine_print": fine_print,
        "claim_friction": claim_friction,
        "red_flags": red_flags,
        "evidence_status": evidence,
    }


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
    if _LLM_PROVIDER == "mistral":
        if not _MISTRAL_KEY:
            return False, "MISTRAL_API_KEY not set", _MISTRAL_MODEL
        return True, "Mistral configured", _MISTRAL_MODEL
    if _LLM_PROVIDER == "openai":
        try:
            from .openai_intelligence import health as openai_health
        except Exception as exc:
            return False, f"OpenAI helper unavailable: {exc}", None
        return openai_health()
    if _LLM_PROVIDER == "llamacpp":
        if not _LLAMA_MODEL_PATH:
            return False, "LLM_MODEL_PATH not set", "llamacpp"
        return True, "llama_cpp configured", "llamacpp"
    return False, f"Unsupported LLM_PROVIDER: {_LLM_PROVIDER}", None
