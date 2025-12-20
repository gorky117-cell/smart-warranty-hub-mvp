import re
from datetime import date, timedelta
from typing import Dict, Optional, Tuple

from bs4 import BeautifulSoup


def parse_oem_text(text: str, brand_hint: str | None = None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    brand = re.search(r"brand[:\s]+([A-Za-z0-9 \-]{2,40})", text, re.IGNORECASE)
    model = re.search(r"model[:\s]+([A-Za-z0-9 \-]{2,40})", text, re.IGNORECASE)
    coverage = re.search(r"(\d{1,2})\s*(month|months|mo)", text, re.IGNORECASE)
    warranty_years = re.search(r"(\d)\s*year", text, re.IGNORECASE)
    exclusions = re.findall(r"exclusion[:\s-]+([A-Za-z0-9 ,\-]{2,80})", text, re.IGNORECASE)

    if brand:
        out["brand"] = brand.group(1).strip()
    if model:
        out["model_code"] = model.group(1).strip()
    if coverage:
        out["coverage_months"] = coverage.group(1)
    elif warranty_years:
        out["coverage_months"] = str(int(warranty_years.group(1)) * 12)
    if exclusions:
        out["exclusions"] = exclusions

    # Brand-specific cues
    brand_patterns = {
        "samsung": [
            r"(compressor|panel)\s*warranty\s*:?(\d+)\s*(year|years)",
            r"(digital\s*inverter)\s*:?(\d+)\s*(year|years)",
        ],
        "lg": [
            r"(motor|compressor)\s*:?(\d+)\s*(year|years)",
            r"(smart\s*inverter)\s*:?(\d+)\s*(year|years)",
        ],
        "bosch": [
            r"(motor|drum)\s*:?(\d+)\s*(year|years)",
        ],
        "whirlpool": [
            r"(compressor)\s*:?(\d+)\s*(year|years)",
        ],
    }
    target_patterns = brand_patterns.get((brand_hint or "").lower(), [])
    all_patterns = target_patterns if target_patterns else [p for lst in brand_patterns.values() for p in lst]
    for pat in all_patterns:
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                part, years = m.group(1), m.group(2)
                out.setdefault("extended_parts", {})[part] = f"{years} years"
    return out


def _extract_first(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            return node.get_text(" ", strip=True)
    return None


def parse_oem_html(html: str, brand_hint: str | None = None) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors: Dict[str, Dict[str, list[str]]] = {
        "samsung": {
            "coverage": [".warranty-coverage", "#coverage", ".coverage-details"],
            "terms": [".terms", "#terms", ".conditions"],
        },
        "lg": {
            "coverage": [".warranty-details", "#warranty", ".coverage"],
            "terms": [".terms", "#terms", ".fine-print"],
        },
        "bosch": {
            "coverage": [".warranty", ".service-info", "#coverage"],
            "terms": [".conditions", ".terms"],
        },
        "whirlpool": {
            "coverage": [".warranty", "#warranty", ".coverage"],
            "terms": [".terms", ".conditions"],
        },
    }
    sel = selectors.get((brand_hint or "").lower(), {})
    out: Dict[str, str] = {}
    cov_text = _extract_first(soup, sel.get("coverage", []))
    if cov_text:
        out["coverage_block"] = cov_text
    terms_text = _extract_first(soup, sel.get("terms", []))
    if terms_text:
        out["terms_block"] = terms_text
    return out


def heuristic_expiry(purchase_date: Optional[date], coverage_months: Optional[int]) -> Optional[date]:
    if not purchase_date or not coverage_months:
        return None
    month = (purchase_date.month - 1 + coverage_months) % 12 + 1
    year = purchase_date.year + (purchase_date.month - 1 + coverage_months) // 12
    day = min(
        purchase_date.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
            month - 1
        ],
    )
    return date(year, month, day)
