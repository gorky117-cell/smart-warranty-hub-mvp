from datetime import datetime
import os
import json
import requests

from ..db import SessionLocal
from ..db_models import AuditLogDB

MAX_DETAIL_LEN = 2000


def _trim(detail: str) -> str:
    if len(detail) > MAX_DETAIL_LEN:
        return detail[:MAX_DETAIL_LEN] + "...(truncated)"
    return detail


def log_action(action: str, detail: str) -> None:
    with SessionLocal() as db:
        entry = AuditLogDB(action=action, detail=_trim(detail), created_at=datetime.utcnow())
        db.add(entry)
        db.commit()
    _maybe_alert(action, detail)


def log_redacted(action: str, content: str, keep: int = 128) -> None:
    snippet = content[:keep]
    log_action(action, f"len={len(content)} preview={snippet}")


def _maybe_alert(action: str, detail: str) -> None:
    hook = os.getenv("ALERT_WEBHOOK_URL")
    if not hook:
        return
    if not any(k in action for k in ("fail", "error", "critical")):
        return
    payload = {
        "action": action,
        "detail": _trim(detail),
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        requests.post(hook, json=payload, timeout=5)
    except Exception:
        pass
