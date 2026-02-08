from __future__ import annotations

import re
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import requests
from bs4 import BeautifulSoup

from .ocr import extract_text_with_meta
from .oem_parsers import parse_oem_html, parse_oem_text
import json


MAX_RAW_TEXT = 4000
_HEADLESS_ENABLED = os.getenv("HEADLESS_SCRAPE", "0").strip().lower() in ("1", "true", "yes")
_OEM_DOMAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_domains.json"


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


def _best_duration_months(text: str) -> Optional[int]:
    years = [int(m.group(1)) for m in _YEAR_RE.finditer(text)]
    months = [int(m.group(1)) for m in _MONTH_RE.finditer(text)]
    candidates = [y * 12 for y in years] + months
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


def parse_terms_from_text(text: str) -> ParsedTerms:
    text = (text or "").strip()
    lines = _split_lines(text)

    duration_months = _best_duration_months(text)
    exclusions = _extract_section(lines, ("exclusion", "not covered", "limitations"))
    claim_steps = _extract_section(lines, ("claim", "how to claim", "procedure", "steps"))

    terms: List[str] = []
    if duration_months:
        terms.append(f"Standard coverage for {duration_months} months from purchase date.")
    if not terms:
        terms = _extract_section(lines, ("coverage", "warranty", "includes"))

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
            return parse_terms_from_text(text or ""), None
        if local_path.suffix.lower() in (".html", ".htm"):
            return parse_terms_from_html(text or ""), None
        return parse_terms_from_text(text or ""), None

    if Path(url).exists():
        local_path = Path(url)
        text, err, is_pdf = _read_local_path(local_path)
        if err:
            return None, err
        if is_pdf:
            return parse_terms_from_text(text or ""), None
        if local_path.suffix.lower() in (".html", ".htm"):
            return parse_terms_from_html(text or ""), None
        return parse_terms_from_text(text or ""), None

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
            return parse_terms_from_text(text or ""), None
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
            return parse_terms_from_html(headless_html), None
    return parsed, None
