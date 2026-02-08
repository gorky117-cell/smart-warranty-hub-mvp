from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

import requests
from sqlalchemy.orm import Session

from .oem_issue_signals import record_issue_signal


DEFAULT_FEED_PATH = Path(__file__).resolve().parents[2] / "data" / "oem_issue_feeds.json"


def _load_feed_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def ingest_oem_issue_feeds(db: Session, feed_path: Path | None = None, timeout: int = 8) -> int:
    """
    Load issue feeds and insert issue signals.
    Feed format: list of feed objects { "url": "...", "region": "IN" }
    Each feed returns JSON array of {brand, model_code, product_type, region, issue_type, severity, count, source_url}
    """
    path = feed_path or DEFAULT_FEED_PATH
    feeds = _load_feed_list(path)
    total = 0
    for feed in feeds:
        url = feed.get("url")
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=timeout)
        except requests.exceptions.RequestException:
            continue
        if resp.status_code != 200:
            continue
        try:
            payload = resp.json()
        except Exception:
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            rec = record_issue_signal(
                db,
                brand=item.get("brand"),
                model_code=item.get("model_code"),
                product_type=item.get("product_type"),
                region=item.get("region") or feed.get("region"),
                issue_type=item.get("issue_type"),
                severity=item.get("severity"),
                count=item.get("count"),
                source_url=item.get("source_url") or url,
            )
            if rec:
                total += 1
    return total
