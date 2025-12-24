from __future__ import annotations

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

def fetch_terms(*, brand: Optional[str], model_code: Optional[str], category: Optional[str], region: Optional[str]) -> Optional[dict]:
    url = "https://example.com"
    try:
        resp = requests.get(url, timeout=6)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)
    except Exception:
        return None

    months = None
    match = re.search(r"(\d{1,2})\s*(month|months)", text.lower())
    if match:
        months = int(match.group(1))
    terms = [
        "Standard coverage applies under normal use.",
        "Manufacturing defects covered by OEM support.",
    ]
    exclusions = [
        "Damage due to misuse, accident, or liquid exposure.",
    ]
    claim_steps = [
        "Keep proof of purchase.",
        "Contact support with model and serial details.",
    ]
    return {
        "duration_months": months or 12,
        "terms": terms,
        "exclusions": exclusions,
        "claim_steps": claim_steps,
        "source_url": url,
        "raw_text": text[:1000],
    }
