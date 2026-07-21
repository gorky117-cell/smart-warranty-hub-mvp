from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import requests

from . import oem_source_policy
from .oem_parsers import parse_oem_html, parse_oem_text


HEADERS = {
    "User-Agent": "SmartWarrantyHub/1.0 (+https://smartwarrantyhub.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class OemAdapter:
    brand: str
    approved_domains: tuple[str, ...]

    def supports(self, brand: Optional[str]) -> bool:
        return (brand or "").strip().lower() == self.brand.lower()

    def allows_url(self, url: str) -> bool:
        host = oem_source_policy.normalize_host(url)
        return oem_source_policy.host_matches_any(host, list(self.approved_domains))

    def fetch(self, *, url: str, model: str, region: Optional[str] = None, timeout: int = 20) -> Dict[str, object]:
        if not self.allows_url(url):
            return {
                "ok": False,
                "status": "blocked",
                "reason": "url_not_allowed_for_adapter",
                "brand": self.brand,
                "url": url,
            }
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
        text = " ".join(html.split())
        return {
            "ok": True,
            "status": "fetched",
            "brand": self.brand,
            "model": model,
            "region": region,
            "url": url,
            "source_type": "approved_oem_adapter",
            "parsed_text": parse_oem_text(text, self.brand),
            "parsed_html": parse_oem_html(html, self.brand),
            "text": text,
        }


_ADAPTERS = {
    "samsung": OemAdapter(
        brand="Samsung",
        approved_domains=("samsung.com", "samsungmobile.com"),
    )
}


def get_adapter(brand: Optional[str]) -> Optional[OemAdapter]:
    return _ADAPTERS.get((brand or "").strip().lower())


def list_adapters() -> Dict[str, Dict[str, object]]:
    return {
        key: {
            "brand": adapter.brand,
            "approved_domains": list(adapter.approved_domains),
            "source_type": "approved_oem_adapter",
        }
        for key, adapter in sorted(_ADAPTERS.items())
    }
