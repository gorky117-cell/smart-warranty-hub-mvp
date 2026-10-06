"""Per-brand permission to show a brand's own wording to customers (terms source order, step 1).

data/brand_reuse_policy.json: {"default": "link_only", "brands": {"<Company>": {"policy": ..., "granted_by":
..., "granted_on": "YYYY-MM-DD", "note": ...}}}

- link_only (default): customers see facts written by SWH, a link to the brand's page and the date we
  checked it; no text copied from the brand's pages.
- summary_ok: as link_only, plus short tips condensed from the brand's text (care guides) - no quotes.
- full_text_ok: the brand's own wording may be shown (terms as written, quotes in care guides).
A policy other than link_only is only valid with who granted it and when.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

LINK_ONLY, SUMMARY_OK, FULL_TEXT_OK = "link_only", "summary_ok", "full_text_ok"
_ORDER = {LINK_ONLY: 0, SUMMARY_OK: 1, FULL_TEXT_OK: 2}
_PATH = Path(__file__).resolve().parents[2] / "data" / "brand_reuse_policy.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"default": LINK_ONLY, "brands": {}}


def reset_cache() -> None:
    _load.cache_clear()


def policy_for(company: Optional[str]) -> str:
    data = _load()
    default = data.get("default") if data.get("default") in _ORDER else LINK_ONLY
    wanted = (company or "").strip().lower()
    for name, entry in (data.get("brands") or {}).items():
        if name.strip().lower() != wanted or not isinstance(entry, dict):
            continue
        policy = entry.get("policy")
        # A permission counts only when it says who gave it and when.
        if policy in _ORDER and (policy == LINK_ONLY or (entry.get("granted_by") and entry.get("granted_on"))):
            return policy
    return default


def allows(company: Optional[str], needed: str) -> bool:
    return _ORDER[policy_for(company)] >= _ORDER[needed]
