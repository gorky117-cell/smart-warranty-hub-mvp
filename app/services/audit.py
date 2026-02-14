from datetime import datetime
import os
import json
import requests

from ..db import SessionLocal
from ..db_models import AuditLogDB
from sqlalchemy.exc import ProgrammingError, OperationalError, DBAPIError

MAX_DETAIL_LEN = 2000
_AUDIT_TABLE_READY = False


def _trim(detail: str) -> str:
    if len(detail) > MAX_DETAIL_LEN:
        return detail[:MAX_DETAIL_LEN] + "...(truncated)"
    return detail


def _ensure_audit_table(db) -> None:
    global _AUDIT_TABLE_READY
    if _AUDIT_TABLE_READY:
        return
    try:
        AuditLogDB.__table__.create(bind=db.get_bind(), checkfirst=True)
        _AUDIT_TABLE_READY = True
    except Exception:
        _AUDIT_TABLE_READY = False


def log_action(action: str, detail: str) -> None:
    with SessionLocal() as db:
        _ensure_audit_table(db)
        entry = AuditLogDB(action=action, detail=_trim(detail), created_at=datetime.utcnow())
        try:
            db.add(entry)
            db.commit()
        except (ProgrammingError, OperationalError, DBAPIError) as exc:
            # Safety for partially-migrated DBs: create table and retry once.
            db.rollback()
            msg = str(exc).lower()
            if "audit_logs" in msg and ("does not exist" in msg or "undefinedtable" in msg):
                try:
                    _ensure_audit_table(db)
                    AuditLogDB.__table__.create(bind=db.get_bind(), checkfirst=True)
                    db.add(AuditLogDB(action=action, detail=_trim(detail), created_at=datetime.utcnow()))
                    db.commit()
                except Exception:
                    db.rollback()
            else:
                db.rollback()
        except Exception:
            db.rollback()
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
