import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException


_LOCK = threading.Lock()
_DEFAULT_PATH = Path("data/ai_usage_quota.json")


def _truthy(value: str | None, default: str = "1") -> bool:
    return (value or default).strip().lower() in ("1", "true", "yes", "on")


def _quota_path() -> Path:
    return Path(os.getenv("AI_QUOTA_FILE", str(_DEFAULT_PATH)))


def _daily_limit() -> int:
    raw = (os.getenv("AI_DAILY_QUOTA_PER_USER") or "50").strip()
    try:
        parsed = int(raw)
    except ValueError:
        return 50
    return max(0, parsed)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def quota_enabled() -> bool:
    return _truthy(os.getenv("AI_QUOTA_ENABLED"), "1")


def check_and_consume(user_id: str, *, units: int = 1, feature: str = "ai") -> dict[str, Any]:
    if not quota_enabled():
        return {"ok": True, "enabled": False, "remaining": None}
    limit = _daily_limit()
    if limit <= 0:
        return {"ok": True, "enabled": True, "limit": 0, "remaining": None}
    user_key = (user_id or "anonymous").strip() or "anonymous"
    units = max(1, int(units or 1))
    today = _today()
    path = _quota_path()
    with _LOCK:
        data = _load(path)
        day_data = data.setdefault(today, {})
        user_data = day_data.setdefault(user_key, {"total": 0, "features": {}})
        used = int(user_data.get("total") or 0)
        if used + units > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ai_quota_exceeded",
                    "limit": limit,
                    "used": used,
                    "remaining": max(0, limit - used),
                },
            )
        user_data["total"] = used + units
        features = user_data.setdefault("features", {})
        features[feature] = int(features.get(feature) or 0) + units
        # Keep only the current day in this lightweight pilot store.
        _save(path, {today: day_data})
        return {
            "ok": True,
            "enabled": True,
            "limit": limit,
            "used": user_data["total"],
            "remaining": max(0, limit - user_data["total"]),
        }


def usage_for(user_id: str) -> dict[str, Any]:
    limit = _daily_limit()
    today = _today()
    data = _load(_quota_path())
    user_data = ((data.get(today) or {}).get(user_id or "anonymous") or {})
    used = int(user_data.get("total") or 0)
    return {
        "enabled": quota_enabled(),
        "date": today,
        "limit": limit,
        "used": used,
        "remaining": None if limit <= 0 else max(0, limit - used),
        "features": user_data.get("features") or {},
    }
