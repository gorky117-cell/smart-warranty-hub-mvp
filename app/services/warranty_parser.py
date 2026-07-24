from __future__ import annotations

import re
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import requests
from bs4 import BeautifulSoup

from .ocr import extract_text_with_meta
from .oem_parsers import parse_oem_html, parse_oem_text
import json


MAX_RAW_TEXT = 4000
_HEADLESS_ENABLED = os.getenv("HEADLESS_SCRAPE", "0").strip().lower() in ("1", "true", "yes")
_OEM_DOMAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_domains.json"
_MISTRAL_API = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1")
_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
_MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")


@dataclass
class ParsedTerms:
    duration_months: Optional[int]
    terms: List[str]
    exclusions: List[str]
    claim_steps: List[str]
    raw_text: Optional[str]
    confidence: float = 0.0


_YEAR_RE = re.compile(r"(\d{1,2})\s*(?:year|years|yr|yrs)", re.IGNORECASE)
_MONTH_RE = re.compile(r"(\d{1,2})\s*(?:month|months|mo)", re.IGNORECASE)
_EXTENDED_PLAN_MARKERS = (
    "coverplus",
    "extended warranty",
    "extends warranty",
    "extend warranty",
    "extended plan",
    "service plan",
    "protection plan",
    "add-on warranty",
    "additional warranty",
)


def _env_true(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _nlp_enrich_enabled() -> bool:
    # Keep deterministic parser primary. NLP enrich is optional fallback.
    return _env_true("TERMS_NLP_ENRICH_ENABLED", "1")


def _nlp_min_confidence() -> float:
    return _env_float("TERMS_NLP_MIN_CONFIDENCE", 0.45)


def _nlp_max_chars() -> int:
    return _env_int("TERMS_NLP_MAX_CHARS", 3000)


def _best_duration_months(text: str) -> Optional[int]:
    component_words = (
        "motor",
        "compressor",
        "panel",
        "battery",
        "adapter",
        "charger",
        "drum",
        "lamp",
        "printhead",
        "print head",
    )
    general: List[int] = []
    component: List[int] = []
    for sentence in _sentences(text):
        low = sentence.lower()
        if any(marker in low for marker in _EXTENDED_PLAN_MARKERS):
            continue
        target = component if any(word in low for word in component_words) else general
        target.extend([int(m.group(1)) * 12 for m in _YEAR_RE.finditer(sentence)])
        target.extend([int(m.group(1)) for m in _MONTH_RE.finditer(sentence)])
    candidates = general or component
    if not candidates:
        return None
    return max(candidates)


def _split_lines(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l and len(l) <= 240]
    if len(lines) > 3:
        return lines
    # fallback: split into sentences
    sentences = re.split(r"[.\n]+", text)
    sentences = [s.strip() for s in sentences if 10 <= len(s.strip()) <= 240]
    return sentences


def _extract_section(lines: List[str], keywords: Tuple[str, ...]) -> List[str]:
    out: List[str] = []
    capturing = False
    for line in lines:
        low = line.lower()
        if any(k in low for k in keywords):
            capturing = True
            continue
        if capturing:
            if any(h in low for h in ("coverage", "exclusion", "claim", "procedure", "how to", "steps")):
                if out:
                    break
            if len(line) >= 6:
                out.append(line)
                if len(out) >= 6:
                    break
    return out


def _clean_item(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^[\-\*\u2022\d\.\)\(]+\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip(" :;,-")
    return s


def _dedupe_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        val = _clean_item(item)
        if len(val) < 3:
            continue
        key = val.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(val)
    return out


def _sentences(text: str) -> List[str]:
    chunks = re.split(r"(?<=[.!?])\s+|[\n\r]+", text or "")
    return _dedupe_keep_order([c for c in chunks if 12 <= len(c.strip()) <= 280])


def _extract_coverage_terms(text: str) -> List[str]:
    terms: List[str] = []
    unit_re = r"(?:prints?|pages?|cycles?|hours?|km|kilometers?|miles?)"
    for sentence in _sentences(text):
        low = sentence.lower()
        has_warranty = any(k in low for k in ("warranty", "coverage", "covered", "covers"))
        has_usage_limit = re.search(r"\b\d[\d,.\s]*\s*" + unit_re + r"\b", low)
        has_first_rule = "whichever comes first" in low
        has_limit_word = any(k in low for k in ("up to", "maximum", "limit", "valid for"))
        if has_warranty and (has_usage_limit or has_first_rule or has_limit_word):
            terms.append(sentence)
        elif has_usage_limit and has_first_rule:
            terms.append(sentence)
    return _dedupe_keep_order(terms)


def _extract_extended_plan_terms(text: str) -> List[str]:
    terms: List[str] = []
    for sentence in _sentences(text):
        low = sentence.lower()
        if any(marker in low for marker in _EXTENDED_PLAN_MARKERS):
            terms.append(f"Optional extended plan: {sentence}")
    return _dedupe_keep_order(terms)


def _extract_covered_parts(text: str) -> List[str]:
    terms: List[str] = []
    for sentence in _sentences(text):
        low = sentence.lower()
        if any(k in low for k in ("covered", "coverage", "includes", "warranty includes")) and any(
            part in low
            for part in (
                "printhead",
                "print head",
                "compressor",
                "motor",
                "panel",
                "battery",
                "adapter",
                "charger",
                "drum",
                "lamp",
            )
        ):
            terms.append(sentence)
    return _dedupe_keep_order(terms)


def _extract_claim_service_steps(lines: List[str]) -> List[str]:
    out: List[str] = []
    reject = (
        "brighter futures",
        "dedicated customer service team",
        "just a phone call",
        "home",
        "about us",
        "where to buy",
        "newsletter",
        "promotion",
        "offers",
    )
    for line in lines:
        low = line.lower()
        if any(bad in low for bad in reject):
            continue
        if any(
            key in low
            for key in (
                "service support",
                "contact support",
                "customer service",
                "warranty check",
                "verify warranty",
                "service request",
                "repair status",
                "service center",
                "service centre",
                "register your product",
                "product registration",
            )
        ):
            out.append(line)
        if len(out) >= 5:
            break
    return _dedupe_keep_order(out)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        chunk = raw[start : end + 1]
        try:
            obj = json.loads(chunk)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _to_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return _dedupe_keep_order([str(x) for x in value if str(x).strip()])
    if isinstance(value, str) and value.strip():
        # If model returns a newline/bullet string, split to list.
        if "\n" in value:
            return _dedupe_keep_order([x for x in value.splitlines() if x.strip()])
        return _dedupe_keep_order([value.strip()])
    return []


def _parse_mistral_terms_json(content: str) -> Optional[ParsedTerms]:
    obj = _extract_json_object(content)
    if not obj:
        return None
    duration_raw = obj.get("duration_months")
    duration: Optional[int] = None
    if duration_raw is not None and str(duration_raw).strip():
        try:
            duration = int(float(str(duration_raw)))
        except Exception:
            duration = None
    terms = _to_str_list(obj.get("terms"))
    exclusions = _to_str_list(obj.get("exclusions"))
    claim_steps = _to_str_list(obj.get("claim_steps"))
    confidence = 0.0
    if duration:
        confidence += 0.4
    if exclusions:
        confidence += 0.2
    if claim_steps:
        confidence += 0.2
    if terms:
        confidence += 0.2
    confidence = min(confidence, 1.0)
    return ParsedTerms(
        duration_months=duration,
        terms=terms,
        exclusions=exclusions,
        claim_steps=claim_steps,
        raw_text=None,
        confidence=confidence,
    )


def _mistral_enrich_terms(raw_text: str) -> Tuple[Optional[ParsedTerms], Optional[str]]:
    if not _MISTRAL_KEY:
        return None, "MISTRAL_API_KEY not set"
    text = (raw_text or "").strip()
    if not text:
        return None, "No text to enrich"
    clipped = text[: max(200, _nlp_max_chars())]
    prompt = (
        "Extract warranty details from text. Return JSON only with keys: "
        "duration_months (number or null), terms (array), exclusions (array), claim_steps (array). "
        "Do not include markdown.\n\n"
        f"Text:\n{clipped}"
    )
    try:
        resp = requests.post(
            f"{_MISTRAL_API.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {_MISTRAL_KEY}"},
            json={
                "model": _MISTRAL_MODEL,
                "messages": [
                    {"role": "system", "content": "You extract structured warranty information."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
            },
            timeout=20,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Mistral call failed: {exc}"
    if resp.status_code != 200:
        return None, f"Mistral error {resp.status_code}"
    try:
        data = resp.json()
    except Exception as exc:
        return None, f"Mistral parse failed: {exc}"
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    parsed = _parse_mistral_terms_json(content)
    if not parsed:
        return None, "Mistral returned non-JSON terms payload"
    return parsed, None


def _needs_enrichment(parsed: ParsedTerms) -> bool:
    if parsed.confidence < _nlp_min_confidence():
        return True
    if not parsed.duration_months and (not parsed.terms or not parsed.exclusions or not parsed.claim_steps):
        return True
    return False


def _merge_parsed(base: ParsedTerms, enrich: ParsedTerms) -> ParsedTerms:
    duration = base.duration_months if base.duration_months else enrich.duration_months
    terms = _dedupe_keep_order((base.terms or []) + (enrich.terms or []))
    exclusions = _dedupe_keep_order((base.exclusions or []) + (enrich.exclusions or []))
    claim_steps = _dedupe_keep_order((base.claim_steps or []) + (enrich.claim_steps or []))
    conf = max(base.confidence, enrich.confidence)
    # Small confidence lift only when enrichment adds new signals.
    if len(terms) > len(base.terms or []) or len(exclusions) > len(base.exclusions or []) or len(claim_steps) > len(base.claim_steps or []):
        conf = min(1.0, conf + 0.1)
    return ParsedTerms(
        duration_months=duration,
        terms=terms,
        exclusions=exclusions,
        claim_steps=claim_steps,
        raw_text=base.raw_text or enrich.raw_text,
        confidence=min(conf, 1.0),
    )


def _finalize_parsed(parsed: ParsedTerms, raw_text_for_enrich: Optional[str] = None) -> ParsedTerms:
    # Always normalize deterministic parser output.
    normalized = ParsedTerms(
        duration_months=parsed.duration_months,
        terms=_dedupe_keep_order(parsed.terms or []),
        exclusions=_dedupe_keep_order(parsed.exclusions or []),
        claim_steps=_dedupe_keep_order(parsed.claim_steps or []),
        raw_text=parsed.raw_text,
        confidence=parsed.confidence,
    )
    if not _nlp_enrich_enabled():
        return normalized
    if not _needs_enrichment(normalized):
        return normalized
    enrich_text = (raw_text_for_enrich or normalized.raw_text or "").strip()
    enrich, _err = _mistral_enrich_terms(enrich_text)
    if not enrich:
        return normalized
    return _merge_parsed(normalized, enrich)


def parse_terms_from_text(text: str) -> ParsedTerms:
    text = (text or "").strip()
    lines = _split_lines(text)

    duration_months = _best_duration_months(text)
    exclusions = _dedupe_keep_order(_extract_section(lines, ("exclusion", "not covered", "limitations")))
    claim_steps = _dedupe_keep_order(
        _extract_section(lines, ("claim", "how to claim", "procedure", "steps"))
        + _extract_claim_service_steps(lines)
    )

    terms: List[str] = []
    if duration_months:
        terms.append(f"Standard coverage for {duration_months} months from purchase date.")
    terms = _dedupe_keep_order(
        terms
        + _extract_coverage_terms(text)
        + _extract_covered_parts(text)
        + _extract_extended_plan_terms(text)
    )
    if not terms:
        terms = _dedupe_keep_order(_extract_section(lines, ("coverage", "warranty", "includes")))

    confidence = 0.0
    if duration_months:
        confidence += 0.4
    if exclusions:
        confidence += 0.2
    if claim_steps:
        confidence += 0.2
    if terms:
        confidence += 0.2
    confidence = min(confidence, 1.0)

    raw_text = text[:MAX_RAW_TEXT] if text else None
    return ParsedTerms(
        duration_months=duration_months,
        terms=terms or [],
        exclusions=exclusions or [],
        claim_steps=claim_steps or [],
        raw_text=raw_text,
        confidence=confidence,
    )


def parse_terms_from_html(html: str) -> ParsedTerms:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return parse_terms_from_text(text)


def _load_oem_domains() -> Dict[str, List[str]]:
    if not _OEM_DOMAIN_PATH.exists():
        return {}
    try:
        return json.loads(_OEM_DOMAIN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _brand_from_url(url: str) -> Optional[str]:
    try:
        host = (requests.utils.urlparse(url).hostname or "").lower()
    except Exception:
        return None
    domains = _load_oem_domains()
    for brand, doms in domains.items():
        for d in doms:
            if host.endswith(d.lower()):
                return brand
    return None


def _fetch_headless(url: str, timeout_ms: int = 15000) -> Optional[str]:
    """
    Optional headless fetch for JS-heavy pages.
    Requires playwright installed and browser dependencies.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            content = page.content()
            browser.close()
            return content
    except Exception:
        return None


def _read_local_path(path: Path) -> Tuple[Optional[str], Optional[str], bool]:
    if not path.exists():
        return None, f"File not found: {path}", False
    if path.suffix.lower() == ".pdf":
        text, err, _meta = extract_text_with_meta(str(path))
        return text, err, True
    try:
        return path.read_text(encoding="utf-8", errors="ignore"), None, False
    except Exception as exc:
        return None, f"File read failed: {exc}", False


def parse_terms_from_url(url: str, timeout: int = 10) -> Tuple[Optional[ParsedTerms], Optional[str]]:
    url = (url or "").strip()
    if not url:
        return None, "Empty URL"

    if url.startswith("file://"):
        local_path = Path(url.replace("file://", ""))
        text, err, is_pdf = _read_local_path(local_path)
        if err:
            return None, err
        if is_pdf:
            parsed = parse_terms_from_text(text or "")
            return _finalize_parsed(parsed, raw_text_for_enrich=text), None
        if local_path.suffix.lower() in (".html", ".htm"):
            parsed = parse_terms_from_html(text or "")
            return _finalize_parsed(parsed, raw_text_for_enrich=text), None
        parsed = parse_terms_from_text(text or "")
        return _finalize_parsed(parsed, raw_text_for_enrich=text), None

    if Path(url).exists():
        local_path = Path(url)
        text, err, is_pdf = _read_local_path(local_path)
        if err:
            return None, err
        if is_pdf:
            parsed = parse_terms_from_text(text or "")
            return _finalize_parsed(parsed, raw_text_for_enrich=text), None
        if local_path.suffix.lower() in (".html", ".htm"):
            parsed = parse_terms_from_html(text or "")
            return _finalize_parsed(parsed, raw_text_for_enrich=text), None
        parsed = parse_terms_from_text(text or "")
        return _finalize_parsed(parsed, raw_text_for_enrich=text), None

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "SmartWarrantyHub/1.0"})
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"

    content_type = (resp.headers.get("content-type") or "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp.flush()
            tmp_path = Path(tmp.name)
        try:
            text, err, _meta = extract_text_with_meta(str(tmp_path))
            if err:
                return None, err
            parsed = parse_terms_from_text(text or "")
            return _finalize_parsed(parsed, raw_text_for_enrich=text), None
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass

    try:
        html = resp.text
    except Exception:
        html = resp.content.decode("utf-8", errors="ignore")
    parsed = parse_terms_from_html(html)
    # OEM-specific rules (brand-specific selectors/regex)
    try:
        brand_hint = _brand_from_url(url)
        oem_blocks = parse_oem_html(html, brand_hint)
        if oem_blocks.get("coverage_block"):
            oem_parsed = parse_terms_from_text(oem_blocks["coverage_block"])
            if oem_parsed.duration_months and (not parsed.duration_months or oem_parsed.duration_months > parsed.duration_months):
                parsed.duration_months = oem_parsed.duration_months
            if oem_parsed.terms:
                parsed.terms = oem_parsed.terms + parsed.terms
            if oem_parsed.exclusions:
                parsed.exclusions = oem_parsed.exclusions + parsed.exclusions
            if oem_parsed.claim_steps:
                parsed.claim_steps = oem_parsed.claim_steps + parsed.claim_steps
        oem_text = parse_oem_text(parsed.raw_text or html, brand_hint)
        ext = oem_text.get("extended_parts", {})
        if isinstance(ext, dict) and ext:
            for k, v in ext.items():
                parsed.terms.append(f"{k.title()} extended warranty: {v}")
    except Exception:
        pass
    if _HEADLESS_ENABLED and (parsed.confidence < 0.2 or len(parsed.raw_text or "") < 200):
        headless_html = _fetch_headless(url)
        if headless_html:
            parsed = parse_terms_from_html(headless_html)
    return _finalize_parsed(parsed, raw_text_for_enrich=parsed.raw_text), None
