from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


_OEM_DOMAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_domains.json"
_OEM_VERIFIED_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_verified.json"


def load_oem_domains() -> Dict[str, List[str]]:
    if not _OEM_DOMAIN_PATH.exists():
        return {}
    try:
        return json.loads(_OEM_DOMAIN_PATH.read_text(encoding="utf-8"))
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
