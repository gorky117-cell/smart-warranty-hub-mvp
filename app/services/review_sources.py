from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict


def load_review_sources() -> List[Dict]:
    path = Path(__file__).resolve().parents[2] / "data" / "review_sources.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
