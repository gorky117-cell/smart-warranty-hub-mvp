from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse


_OEM_DOMAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_domains.json"
_OEM_VERIFIED_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_verified.json"


def normalize_domain(value: str) -> str:
    """Bare lower-case host: drops scheme, path, port and a leading "www." ("kia.com/in" -> "kia.com")."""
    raw = (value or "").strip().lower()
    host = urlparse(raw if "://" in raw else f"https://{raw}").hostname or ""
    return host[4:] if host.startswith("www.") else host


def _normalized(data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for brand, domains in (data or {}).items():
        hosts: List[str] = []
        for domain in domains or []:
            host = normalize_domain(domain)
            if host and host not in hosts:
                hosts.append(host)
        out[brand] = hosts
    return out


def load_oem_domains() -> Dict[str, List[str]]:
    if not _OEM_DOMAIN_PATH.exists():
        return {}
    try:
        return _normalized(json.loads(_OEM_DOMAIN_PATH.read_text(encoding="utf-8")))
    except Exception:
        return {}


def load_verified_domains() -> Dict[str, List[str]]:
    if not _OEM_VERIFIED_PATH.exists():
        return {}
    try:
        return json.loads(_OEM_VERIFIED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_verified_domains(data: Dict[str, List[str]]) -> None:
    _OEM_VERIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OEM_VERIFIED_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
