from datetime import datetime

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


def log_redacted(action: str, content: str, keep: int = 128) -> None:
    snippet = content[:keep]
    log_action(action, f"len={len(content)} preview={snippet}")
