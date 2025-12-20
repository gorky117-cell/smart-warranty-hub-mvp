import json
import uuid
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional

REC_PATH = Path("data/oem_recommendations.jsonl")


def _load(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []


def _write_all(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _append(path: Path, row: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def publish_recommendation(rec: Dict) -> Dict:
    now = dt.datetime.utcnow().isoformat()
    row = {
        "id": rec.get("id") or f"oemr_{uuid.uuid4().hex[:10]}",
        "created_at": now,
        "product_type": rec.get("product_type"),
        "brand": rec.get("brand"),
        "model": rec.get("model"),
        "region": rec.get("region"),
        "title": rec.get("title"),
        "message": rec.get("message"),
        "cta_label": rec.get("cta_label"),
        "cta_url": rec.get("cta_url"),
        "tags": rec.get("tags") or [],
        "risk_hint": rec.get("risk_hint"),
        "status": rec.get("status") or "active",
        "source": rec.get("source") or "oem_manual",
    }
    _append(REC_PATH, row)
    return row


def list_active(filters: Dict) -> List[Dict]:
    rows = _load(REC_PATH)
    out = []
    for r in rows:
        if r.get("status") != "active":
            continue
        if filters.get("brand") and r.get("brand") and r.get("brand") != filters.get("brand"):
            continue
        if filters.get("model") and r.get("model") and r.get("model") != filters.get("model"):
            continue
        if filters.get("product_type") and r.get("product_type") and r.get("product_type") != filters.get("product_type"):
            continue
        if filters.get("region") and r.get("region") and r.get("region") != filters.get("region"):
            continue
        out.append(r)
    return out


def disable_rec(rec_id: str) -> bool:
    rows = _load(REC_PATH)
    changed = False
    for r in rows:
        if r.get("id") == rec_id:
            r["status"] = "disabled"
            changed = True
    if changed:
        _write_all(REC_PATH, rows)
    return changed
