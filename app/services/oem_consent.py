import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()
_DEFAULT_PATH = Path("data/oem_direct_consent.json")


def _truthy(value: str | None, default: str = "1") -> bool:
    return (value or default).strip().lower() in ("1", "true", "yes", "on")


def direct_consent_required() -> bool:
    return _truthy(os.getenv("REQUIRE_OEM_DIRECT_CONSENT"), "1")


def _path() -> Path:
    return Path(os.getenv("OEM_DIRECT_CONSENT_FILE", str(_DEFAULT_PATH)))


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


def get_oem_direct_consent(user_id: str) -> dict[str, Any]:
    user_key = (user_id or "").strip()
    if not user_key:
        return {"user_id": user_id, "oem_direct_sharing": False}
    data = _load(_path())
    row = data.get(user_key) if isinstance(data.get(user_key), dict) else {}
    return {
        "user_id": user_key,
        "oem_direct_sharing": bool(row.get("oem_direct_sharing", False)),
        "updated_at": row.get("updated_at"),
    }


def has_oem_direct_consent(user_id: str) -> bool:
    return bool(get_oem_direct_consent(user_id).get("oem_direct_sharing"))


def set_oem_direct_consent(user_id: str, enabled: bool) -> dict[str, Any]:
    user_key = (user_id or "").strip()
    if not user_key:
        return {"user_id": user_id, "oem_direct_sharing": False}
    path = _path()
    with _LOCK:
        data = _load(path)
        data[user_key] = {
            "oem_direct_sharing": bool(enabled),
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save(path, data)
        return get_oem_direct_consent(user_key)
