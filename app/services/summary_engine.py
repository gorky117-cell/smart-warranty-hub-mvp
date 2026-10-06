from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
import re
from typing import Optional, Tuple, Dict, Any

import requests

from ..models import CanonicalWarranty
from .privacy import ai_safe
from .source_trust import brand_page_url, classify_terms_source
from .warranty_parser import sanitize_base_terms

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
    terms = sanitize_base_terms(warranty.terms or [])
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


TERMS_FRESH_DAYS = 30


def _checked_on(checked_at: Optional[str], flagged: Optional[bool]) -> Tuple[Optional[str], bool]:
    """(YYYY-MM-DD, needs refresh) for when the terms source was last checked."""
    if not checked_at:
        return None, bool(flagged)
    try:
        when = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None, bool(flagged)
    return when.date().isoformat(), bool(flagged) or (datetime.utcnow() - when) > timedelta(days=TERMS_FRESH_DAYS)


def build_evidence_summary(warranty: CanonicalWarranty) -> Dict[str, object]:
    """
    Additive trust layer for warranty terms.
    It labels whether the terms are confirmed, cached, estimated, or not confirmed
    without changing the underlying warranty/scoring logic.
    """
    alt = getattr(warranty, "alternatives", None) or {}
    source_type = (alt.get("terms_source_type") or "unknown").strip() or "unknown"
    source_url = alt.get("terms_source_url")
    source_urls = alt.get("terms_source_urls") or ([source_url] if source_url else [])
    refreshed_at = alt.get("terms_last_refreshed_at")

    oem_entity = alt.get("oem_entity") or {}
    source_trust = classify_terms_source(
        brand=oem_entity.get("company") or getattr(warranty, "brand", None),
        source_url=source_url,
        source_type=source_type,
    )

    unreadable = alt.get("unreadable_invoice")
    if unreadable or source_type == "unreadable":
        status = "unreadable"
        label = "We couldn't read this invoice"
        note = (unreadable or {}).get("message") or "We couldn't read this invoice - retake the photo or enter the details."
        confidence = 0.0
    elif source_type == "needs_check":
        status = "needs_check"
        label = "Estimated - please check your warranty card or the seller"
        note = "No official warranty terms were confirmed for this product, so no warranty period is shown."
        confidence = 0.2
    elif source_type == "knowledge_base" and source_url:
        # Hand-checked entry (knowledge base v1): customers see when it was checked.
        checked, _stale = _checked_on(refreshed_at, False)
        brand_name = oem_entity.get("company") or getattr(warranty, "brand", None) or "the brand"
        status = "confirmed"
        label = f"Checked on {checked}" if checked else "Checked by Smart Warranty Hub"
        note = f"Terms hand-checked against the official {brand_name} website."
        confidence = 0.95
    elif source_type == "approved_oem_source" and source_url:
        status = "confirmed"
        label = source_trust["label"]
        note = source_trust["note"]
        confidence = source_trust["confidence"]
    elif source_type == "scraped" and source_url:
        if source_trust.get("verified") or source_trust.get("official"):
            status = "confirmed"
        else:
            status = "not_confirmed"
        label = source_trust["label"]
        note = source_trust["note"]
        confidence = source_trust["confidence"]
    elif source_type == "internal_warranty_db":
        # Legacy rows (before cache fix 2) copied another record's terms, estimates included: not confirmed.
        status = "not_confirmed"
        label = "Copied from another saved product - not confirmed"
        note = "These terms came from another product saved here and may be an estimate. Please check them with the brand."
        confidence = 0.4
    elif source_type == "internal_terms_cache":
        status = "cached"
        label = "Saved copy of the terms"
        note = "These terms come from a copy we saved earlier. Please check the brand's website before making a claim."
        confidence = 0.7
    elif source_type == "default_rules":
        status = "estimated"
        label = "Estimated, please check"
        note = "We could not find this brand's own warranty terms, so these are typical terms for this kind of product. Please check your warranty card."
        confidence = 0.45
    elif source_type == "invoice_only":
        status = "not_confirmed"
        label = "Not confirmed yet"
        note = "We read your invoice but have not found the brand's warranty terms yet."
        confidence = 0.35
    elif source_type == "synthetic_approved":
        status = "not_confirmed"
        label = "Test data - not real terms"
        note = "These terms are test data, not the brand's real terms."
        confidence = 0.6
    else:
        status = "not_confirmed"
        label = "Not confirmed yet"
        note = "We don't know where these terms came from yet, so please don't rely on them for a claim."
        confidence = 0.3

    sources = []
    for idx, url in enumerate(source_urls):
        if not url:
            continue
        sources.append(
            {
                "title": "Warranty terms source" if idx == 0 else f"Warranty terms source {idx + 1}",
                "url": url,
                "source_type": source_type,
                "trust_status": source_trust.get("status"),
                "official": source_trust.get("official", False),
                "verified": source_trust.get("verified", False),
                "host": source_trust.get("host"),
                "fetched_at": refreshed_at,
                "confidence": confidence,
            }
        )
    checked_on, needs_refresh = _checked_on(refreshed_at, alt.get("terms_needs_refresh"))
    if source_type == "knowledge_base":
        needs_refresh = False  # hand-checked; re-checks are an admin action, not an age rule
    if checked_on and status == "confirmed" and source_type != "knowledge_base":
        # Cache fix 5: say when the official page was checked; older than 30 days needs a refresh.
        label = f"{label} - checked on {checked_on}" + (", needs refresh" if needs_refresh else "")
        if needs_refresh:
            note = f"{note} Last checked on {checked_on}. The terms may have changed since; please check the brand's website."
    return {
        "checked_on": checked_on,
        "needs_refresh": needs_refresh,
        "status": status,
        "status_label": label,
        "source_type": source_type,
        "source_url": source_url,
        "last_refreshed_at": refreshed_at,
        "confidence": confidence,
        "requires_oem_verification": status != "unreadable"
        and (bool(source_trust.get("requires_oem_verification")) or needs_refresh
             or status in {"estimated", "not_confirmed", "cached"}),
        "note": note,
        "sources": sources,
        "source_trust": source_trust,
        # Where the customer can check for themselves when nothing is confirmed (source order, last step).
        "brand_page_url": None if status == "confirmed" else brand_page_url(
            oem_entity.get("company") or getattr(warranty, "brand", None)),
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
    prompt = ai_safe(prompt)  # callers redact too; never rely on that alone
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
    unreadable = (getattr(warranty, "alternatives", None) or {}).get("unreadable_invoice")
    if unreadable:
        return unreadable.get("message") or "We couldn't read this invoice - retake the photo or enter the details.", "unreadable"
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
        f"Coverage months: {warranty.coverage_months}\nTerms: {sanitize_base_terms(warranty.terms or [])}\nExclusions: {warranty.exclusions}\n"
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
    prompt = ai_safe(prompt)  # buyer details never reach a provider (fix run B1)
    if _LLM_PROVIDER in ("openai", "mistral"):
        # The chosen provider first, then the other one if it fails or times out (redacted for both).
        from .ai_providers import run_with_fallback

        text, meta = run_with_fallback(
            "summary",
            prompt,
            {"openai": lambda p: _summarize_with_openai(p), "mistral": lambda p: _summarize_with_mistral(p)},
            default_first=_LLM_PROVIDER,
            chosen=_LLM_PROVIDER,
        )
        if text:
            return text, meta["provider"]
        if _LLM_PROVIDER == "openai":
            return _fallback_summary(prompt, warranty)
        return _template_summary(warranty), "template"
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
    terms = sanitize_base_terms(warranty.terms or [])
    if terms:
        points.extend([f"Term: {t}" for t in terms[:5]])
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


def _dedupe_plain(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        clean = " ".join(str(item).split()).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _useful_customer_bullets(items: List[str], *, kind: str, coverage: str) -> List[str]:
    bullets: List[str] = []
    for item in items:
        low = item.lower()
        if kind == "term":
            if any(k in low for k in ("coverage", "warranty", "month", "year")):
                bullets.append(f"Standard warranty coverage shown: {coverage}.")
            if "printhead" in low:
                bullets.append("Printhead coverage or limits are mentioned in the OEM terms.")
            elif any(k in low for k in ("repair", "replacement", "defective", "manufacturing")):
                bullets.append("Manufacturing defects may be repaired or replaced under OEM terms.")
            # Cautions (international limits, wear, exclusions) belong under Limits, never Pros.
        elif kind == "exclusion":
            if any(k in low for k in ("liquid", "water", "moisture")):
                bullets.append("Liquid or moisture damage may not be covered.")
            elif any(k in low for k in ("wear", "tear", "consumable", "filter", "lamp", "bulb")):
                bullets.append("Normal wear, consumables or replaceable parts may not be covered.")
            elif "unauthor" in low:  # grounded: only when the text itself speaks of unauthorized repair
                bullets.append("Repairs by unauthorized people are mentioned as not covered.")
            elif any(k in low for k in ("authorised", "authorized")):
                bullets.append("Repairs are done at authorized service centres.")
            elif any(k in low for k in ("screen", "accidental", "physical")):
                bullets.append("Screen, accidental or physical damage may have limits or exclusions.")
        elif kind == "claim":
            if any(k in low for k in ("warranty checker", "warranty check", "register")):
                bullets.append("Check warranty status or register the product on the OEM support page.")
            elif any(k in low for k in ("service center", "service centre", "authorized service", "authorised service")):
                bullets.append("Use an authorized service center or official OEM support route.")
            elif any(k in low for k in ("invoice", "serial", "model", "photo")):
                bullets.append("Keep invoice, model/serial details and issue photos ready before contacting support.")
            elif any(k in low for k in ("repair", "book", "troubleshoot")):
                bullets.append("Use OEM troubleshooting or book repair through the official support route.")
    return _dedupe_plain(bullets)


# Limits read from the warranty text (terms + exclusions). Each rule: (pattern, bullet).
# Limits read from the warranty text (terms + exclusions). Every line names only what the source names
# (live test 1 correction: no conclusions the terms do not state).
def _found(low: str, words) -> List[str]:
    """The words of ``words`` that appear in ``low`` (each a (pattern, display name) pair), in order."""
    return [name for pattern, name in words if re.search(pattern, low)]


def _join(names: List[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def limits_from_text(text: str, *, phone: bool = False) -> List[str]:
    """Short "not covered" lines naming only what the text names. Works for any product (`phone` is kept for
    older callers and no longer changes anything)."""
    low = (text or "").lower()
    out: List[str] = []
    if re.search(r"wear and tear|wear & tear|normal wear", low):
        parts = _found(low, ((r"camera lens", "camera lenses"), (r"batter(?:y|ies)", "batteries"), (r"display", "displays"),
                             (r"screen", "screens"), (r"filters?\b", "filters"), (r"lamps?\b|bulbs?\b", "lamps and bulbs"),
                             (r"knobs?\b", "knobs"), (r"gaskets?\b", "gaskets"), (r"rubber", "rubber parts"),
                             (r"plastic", "plastic parts"), (r"remote", "remotes"), (r"belts?\b", "belts"),
                             (r"brushes\b|brush\b", "brushes"), (r"cartridges?\b", "cartridges"),
                             (r"cables?\b|cords?\b", "cables")))
        out.append(f"Normal wear and tear{' of ' + _join(parts) if parts else ''} is not covered.")
    causes = _found(low, ((r"lightning", "lightning"), (r"abnormal voltage", "abnormal voltage"),
                          (r"power surge", "power surges"), (r"voltage fluctuation", "voltage fluctuations")))
    if causes:
        out.append(f"Damage from {_join(causes)} is not covered.")
    if re.search(r"unauthori[sz]ed", low):
        out.append("Repairs or changes by unauthorized people are not covered.")
    elif re.search(r"modification|alteration", low):
        out.append("Modifications or alterations are not covered.")
    wet = _found(low, ((r"liquid", "liquid"), (r"waterlogging", "waterlogging"), (r"\bwater\b", "water"), (r"moisture", "moisture")))
    if wet:
        out.append(f"Damage from {_join(wet)} is not covered.")
    misuse = _found(low, ((r"physical damage", "physical damage"), (r"accidental", "accidental damage"),
                          (r"improper use", "improper use"), (r"misuse", "misuse")))
    if misuse:
        text_ = _join(misuse)
        out.append(f"{text_[0].upper() + text_[1:]} {'is' if len(misuse) == 1 else 'are'} not covered.")
    if re.search(r"serial number is removed|serial number.*(?:obliterated|altered)", low):
        out.append("The warranty does not apply if the serial number is removed or altered.")
    if re.search(r"consumable", low):
        out.append("Consumables are not covered.")
    return out


def service_route_lines(claim_text: str, brand: Optional[str]) -> List[str]:
    """Grounded lines about where repairs happen ("carried at Samsung authorized service center")."""
    low = (claim_text or "").lower()
    if re.search(r"authori[sz]ed service (?:center|centre)", low):
        owner = brand.strip() if brand and brand.strip() else "the brand's"
        return [f"Repairs are done at {owner} authorized service centres."]
    return []


def build_layman_summary(warranty: CanonicalWarranty) -> Dict[str, object]:
    """
    Human-friendly warranty explanation for non-technical users.
    Additive helper: does not change core predictive/terms logic.
    """
    terms = [str(t).strip() for t in sanitize_base_terms(warranty.terms or []) if str(t).strip()]
    exclusions = [str(e).strip() for e in (warranty.exclusions or []) if str(e).strip()]
    claim_steps = [str(c).strip() for c in (warranty.claim_steps or []) if str(c).strip()]
    evidence = build_evidence_summary(warranty)

    product = " ".join([x for x in [warranty.brand, warranty.model_code] if x]) or (warranty.product_name or "product")
    coverage = f"{warranty.coverage_months} months" if warranty.coverage_months else "not clearly stated"

    facts = (getattr(warranty, "alternatives", None) or {}).get("facts")
    if facts:
        # Own words (owner decision): facts written by SWH, never the brand's sentences.
        from .warranty_facts import customer_lists

        lists = customer_lists(facts, warranty.brand)
        pros = [f["text"] + "." for f in (facts.get("covers") or []) + (facts.get("part_periods") or [])][:4]
        cons = lists["exclusions"]
        claim_friction = lists["claim_steps"][:4]
    else:
        pros = _useful_customer_bullets(terms, kind="term", coverage=coverage)[:4]
        from .customer_content import is_phone

        cons = limits_from_text(" ".join(terms + exclusions), phone=is_phone(warranty))
        claim_friction = service_route_lines(" ".join(claim_steps), warranty.brand) + [
            line for line in _useful_customer_bullets(claim_steps, kind="claim", coverage=coverage)
            if "authorized service center" not in line  # replaced by the grounded line above
        ][:4]
    # Fine print: only what is not already a limit (no generic filler; empty sections are hidden).
    fine_print = []
    low_all = " ".join(exclusions).lower()
    if not facts and "consum" in low_all and not any("consumable" in c.lower() for c in cons):
        fine_print.append("Consumables are usually not covered.")

    red_flags = []
    if not warranty.coverage_months:
        red_flags.append("The warranty period is not clear yet. Please check it with the brand.")
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
