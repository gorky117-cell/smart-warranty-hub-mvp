from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from ..db_models import (
    RemoteDiagnosticSessionDB,
    RemoteDiagnosticCommandDB,
    RemoteDiagnosticExecutionDB,
    ReviewDB,
    WarrantyDB,
)
from ..models import TelemetryEvent
from ..services.connection_registry import registry
from ..services.review import create_review
from ..storage import generate_id, store


def _now() -> datetime:
    return datetime.utcnow()


def _allowed_command_types() -> set[str]:
    raw = os.getenv(
        "REMOTE_DIAGNOSTICS_ALLOWED_COMMANDS",
        "health_check,collect_logs,run_self_test,network_check,sensor_snapshot,firmware_info",
    )
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _sanitize_json(value: Any, max_text: int = 5000) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, str):
        return value[:max_text]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _sanitize_json(v, max_text=max_text)
        return out
    if isinstance(value, list):
        return [_sanitize_json(v, max_text=max_text) for v in value[:200]]
    return str(value)[:max_text]


def _connector_url(connector_endpoint: str, execute_path: Optional[str]) -> str:
    base = (connector_endpoint or "").strip().rstrip("/")
    path = (execute_path or "").strip()
    if not path:
        return base
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}/{path.lstrip('/')}"


def _resolve_connector(connector_name: Optional[str] = None):
    if connector_name:
        c = registry.get(connector_name)
        if c:
            return c
    env_name = os.getenv("REMOTE_DIAGNOSTICS_CONNECTOR", "").strip()
    if env_name:
        c = registry.get(env_name)
        if c:
            return c
    by_kind = registry.list("remote_diagnostics")
    if by_kind:
        return next(iter(by_kind.values()))
    telemetry_kind = registry.list("telemetry")
    if telemetry_kind:
        return next(iter(telemetry_kind.values()))
    return None


def _mark_review_state(db: Session, review_id: Optional[str], status: str, reason: Optional[str]) -> None:
    if not review_id:
        return
    item = db.get(ReviewDB, review_id)
    if not item:
        return
    item.status = status
    item.reason = reason
    item.resolved_at = _now()
    db.add(item)
    db.commit()


def create_session(
    db: Session,
    *,
    user_id: str,
    warranty_id: str,
    requested_by: str,
    connector_name: Optional[str] = None,
    device_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> RemoteDiagnosticSessionDB:
    w = db.query(WarrantyDB).filter_by(id=warranty_id).first()
    if not w:
        raise ValueError("warranty_not_found")
    row = RemoteDiagnosticSessionDB(
        id=generate_id("rds"),
        user_id=user_id,
        warranty_id=warranty_id,
        requested_by=requested_by,
        connector_name=connector_name,
        device_id=device_id,
        status="open",
        context_json=_sanitize_json(context or {}),
        created_at=_now(),
        updated_at=_now(),
        last_command_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: str) -> Optional[RemoteDiagnosticSessionDB]:
    return db.query(RemoteDiagnosticSessionDB).filter_by(id=session_id).first()


def list_sessions(
    db: Session,
    *,
    user_id: Optional[str] = None,
    warranty_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[RemoteDiagnosticSessionDB]:
    q = db.query(RemoteDiagnosticSessionDB)
    if user_id:
        q = q.filter(RemoteDiagnosticSessionDB.user_id == user_id)
    if warranty_id:
        q = q.filter(RemoteDiagnosticSessionDB.warranty_id == warranty_id)
    if status:
        q = q.filter(RemoteDiagnosticSessionDB.status == status)
    return q.order_by(RemoteDiagnosticSessionDB.created_at.desc()).limit(max(1, min(int(limit), 500))).all()


def request_command(
    db: Session,
    *,
    session_id: str,
    command_type: str,
    command_payload: Optional[Dict[str, Any]],
    requested_by: str,
    require_review: bool = True,
    review_reason: Optional[str] = None,
    connector_name: Optional[str] = None,
) -> RemoteDiagnosticCommandDB:
    session = get_session(db, session_id)
    if not session:
        raise ValueError("session_not_found")
    if session.status != "open":
        raise ValueError("session_closed")

    normalized_type = (command_type or "").strip().lower()
    if not normalized_type:
        raise ValueError("missing_command_type")
    if normalized_type not in _allowed_command_types():
        raise ValueError("unsupported_command_type")

    review_id: Optional[str] = None
    status = "pending_review" if require_review else "queued"
    if require_review:
        review = create_review(
            "device_actuation",
            {
                "session_id": session.id,
                "warranty_id": session.warranty_id,
                "user_id": session.user_id,
                "command_type": normalized_type,
                "command_payload": _sanitize_json(command_payload or {}),
                "requested_by": requested_by,
            },
        )
        review_id = review.id

    cmd = RemoteDiagnosticCommandDB(
        id=generate_id("rdc"),
        session_id=session.id,
        warranty_id=session.warranty_id,
        user_id=session.user_id,
        requested_by=requested_by,
        command_type=normalized_type,
        command_payload=_sanitize_json(command_payload or {}),
        status=status,
        require_review=1 if require_review else 0,
        review_id=review_id,
        review_reason=review_reason,
        connector_name=connector_name,
        attempt_count=0,
        executed_by=None,
        result_json=None,
        error_text=None,
        created_at=_now(),
        updated_at=_now(),
        executed_at=None,
    )
    session.last_command_at = _now()
    session.updated_at = _now()
    db.add(session)
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


def get_command(db: Session, command_id: str) -> Optional[RemoteDiagnosticCommandDB]:
    return db.query(RemoteDiagnosticCommandDB).filter_by(id=command_id).first()


def list_commands(
    db: Session,
    *,
    session_id: Optional[str] = None,
    warranty_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[RemoteDiagnosticCommandDB]:
    q = db.query(RemoteDiagnosticCommandDB)
    if session_id:
        q = q.filter(RemoteDiagnosticCommandDB.session_id == session_id)
    if warranty_id:
        q = q.filter(RemoteDiagnosticCommandDB.warranty_id == warranty_id)
    if user_id:
        q = q.filter(RemoteDiagnosticCommandDB.user_id == user_id)
    if status:
        q = q.filter(RemoteDiagnosticCommandDB.status == status)
    return q.order_by(RemoteDiagnosticCommandDB.created_at.desc()).limit(max(1, min(int(limit), 500))).all()


def decide_command(
    db: Session,
    *,
    command_id: str,
    approved: bool,
    reviewer: str,
    reason: Optional[str] = None,
) -> RemoteDiagnosticCommandDB:
    cmd = get_command(db, command_id)
    if not cmd:
        raise ValueError("command_not_found")
    if cmd.status != "pending_review":
        raise ValueError("command_not_pending_review")

    if approved:
        cmd.status = "queued"
        cmd.error_text = None
        _mark_review_state(db, cmd.review_id, "approved", reason)
    else:
        cmd.status = "rejected"
        cmd.error_text = reason or "rejected_by_reviewer"
        _mark_review_state(db, cmd.review_id, "rejected", reason)

    cmd.updated_at = _now()
    cmd.executed_by = reviewer
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


def _record_execution(
    db: Session,
    *,
    cmd: RemoteDiagnosticCommandDB,
    connector_name: Optional[str],
    request_json: Dict[str, Any],
    response_json: Optional[Dict[str, Any]],
    http_status: Optional[int],
    success: bool,
    error_text: Optional[str],
    latency_ms: Optional[float],
) -> RemoteDiagnosticExecutionDB:
    row = RemoteDiagnosticExecutionDB(
        command_id=cmd.id,
        session_id=cmd.session_id,
        connector_name=connector_name,
        request_json=_sanitize_json(request_json),
        response_json=_sanitize_json(response_json or {}),
        http_status=http_status,
        success=1 if success else 0,
        error_text=(error_text or None),
        latency_ms=latency_ms,
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def execute_command(
    db: Session,
    *,
    command_id: str,
    executor: str,
    force: bool = False,
) -> Dict[str, Any]:
    cmd = get_command(db, command_id)
    if not cmd:
        raise ValueError("command_not_found")
    if cmd.status == "pending_review" and not force:
        raise ValueError("review_required")
    if cmd.status in ("executed", "executing") and not force:
        raise ValueError("already_executed_or_running")
    if cmd.status in ("rejected", "cancelled") and not force:
        raise ValueError("command_not_executable")

    session = get_session(db, cmd.session_id)
    if not session:
        raise ValueError("session_not_found")

    connector = _resolve_connector(cmd.connector_name or session.connector_name)
    if not connector:
        cmd.status = "failed"
        cmd.error_text = "no_remote_diagnostics_connector"
        cmd.updated_at = _now()
        cmd.executed_by = executor
        db.add(cmd)
        db.commit()
        return {
            "ok": False,
            "command_id": cmd.id,
            "status": cmd.status,
            "error": cmd.error_text,
        }

    execute_path = (connector.metadata or {}).get("execute_path", "/diagnostics/execute")
    timeout_sec = int((connector.metadata or {}).get("timeout_sec", os.getenv("REMOTE_DIAGNOSTICS_TIMEOUT_SEC", "20")))
    url = _connector_url(connector.endpoint, execute_path)
    headers = {"Content-Type": "application/json"}
    if connector.auth_token:
        headers["Authorization"] = f"Bearer {connector.auth_token}"

    outbound = {
        "command_id": cmd.id,
        "session_id": session.id,
        "warranty_id": cmd.warranty_id,
        "user_id": cmd.user_id,
        "device_id": session.device_id,
        "command_type": cmd.command_type,
        "command_payload": _sanitize_json(cmd.command_payload or {}),
        "context": _sanitize_json(session.context_json or {}),
    }

    cmd.status = "executing"
    cmd.attempt_count = int(cmd.attempt_count or 0) + 1
    cmd.updated_at = _now()
    cmd.executed_by = executor
    db.add(cmd)
    db.commit()

    started = time.perf_counter()
    err: Optional[str] = None
    http_status: Optional[int] = None
    response_payload: Dict[str, Any] = {}
    success = False

    try:
        resp = requests.post(
            url,
            json=outbound,
            headers=headers,
            timeout=max(5, timeout_sec),
        )
        http_status = resp.status_code
        try:
            parsed = resp.json()
            response_payload = parsed if isinstance(parsed, dict) else {"data": parsed}
        except Exception:
            response_payload = {"raw_text": (resp.text or "")[:5000]}
        success = http_status < 400 and response_payload.get("ok", True) is not False
        if not success:
            err = response_payload.get("error") or f"http_{http_status}"
    except requests.exceptions.RequestException as exc:
        err = f"request_failed: {exc}"
        success = False

    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

    cmd.status = "executed" if success else "failed"
    cmd.result_json = _sanitize_json(response_payload)
    cmd.error_text = err
    cmd.executed_at = _now()
    cmd.updated_at = _now()
    db.add(cmd)
    db.commit()
    db.refresh(cmd)

    _record_execution(
        db,
        cmd=cmd,
        connector_name=connector.name,
        request_json=outbound,
        response_json=response_payload,
        http_status=http_status,
        success=success,
        error_text=err,
        latency_ms=latency_ms,
    )

    # Feed execution result back into telemetry/RAG path for downstream scoring.
    try:
        ev = TelemetryEvent(
            id=generate_id("tel"),
            warranty_id=cmd.warranty_id,
            user_id=cmd.user_id,
            model_code=None,
            region=None,
            timezone=None,
            event_type="remote_diagnostic_result",
            payload={
                "command_id": cmd.id,
                "command_type": cmd.command_type,
                "connector": connector.name,
                "success": success,
                "http_status": http_status,
                "error": err,
                "result": _sanitize_json(response_payload),
            },
        )
        store.add_telemetry(ev)
    except Exception:
        pass

    try:
        from .rag import add_event_documents, rag_enabled

        if rag_enabled():
            add_event_documents(
                db,
                doc_type="diagnostic",
                doc_id=f"diag:{cmd.id}:{int(time.time())}",
                content=(
                    f"user={cmd.user_id} warranty={cmd.warranty_id} command={cmd.command_type} "
                    f"success={success} error={err or ''} response={_sanitize_json(response_payload)}"
                ),
                metadata={
                    "user_id": cmd.user_id,
                    "warranty_id": cmd.warranty_id,
                    "command_type": cmd.command_type,
                    "status": cmd.status,
                    "connector": connector.name,
                },
            )
    except Exception:
        pass

    return {
        "ok": success,
        "command_id": cmd.id,
        "status": cmd.status,
        "http_status": http_status,
        "error": err,
        "latency_ms": latency_ms,
        "result": _sanitize_json(response_payload),
    }


def run_pending_commands(db: Session, *, limit: int = 20, executor: str = "scheduler") -> Dict[str, Any]:
    queued = (
        db.query(RemoteDiagnosticCommandDB)
        .filter(RemoteDiagnosticCommandDB.status == "queued")
        .order_by(RemoteDiagnosticCommandDB.created_at.asc())
        .limit(max(1, min(int(limit), 200)))
        .all()
    )
    out = {"queued": len(queued), "executed": 0, "failed": 0, "errors": []}
    for cmd in queued:
        try:
            res = execute_command(db, command_id=cmd.id, executor=executor, force=False)
            if res.get("ok"):
                out["executed"] += 1
            else:
                out["failed"] += 1
                out["errors"].append({"command_id": cmd.id, "error": res.get("error")})
        except Exception as exc:
            out["failed"] += 1
            out["errors"].append({"command_id": cmd.id, "error": str(exc)})
    return out


def get_command_executions(db: Session, command_id: str, limit: int = 20) -> List[RemoteDiagnosticExecutionDB]:
    return (
        db.query(RemoteDiagnosticExecutionDB)
        .filter(RemoteDiagnosticExecutionDB.command_id == command_id)
        .order_by(RemoteDiagnosticExecutionDB.created_at.desc())
        .limit(max(1, min(int(limit), 200)))
        .all()
    )


def health(db: Session) -> Dict[str, Any]:
    connector = _resolve_connector(None)
    queued = db.query(RemoteDiagnosticCommandDB).filter(RemoteDiagnosticCommandDB.status == "queued").count()
    pending_review = db.query(RemoteDiagnosticCommandDB).filter(RemoteDiagnosticCommandDB.status == "pending_review").count()
    return {
        "ok": bool(connector),
        "connector": connector.name if connector else None,
        "queued_commands": int(queued),
        "pending_review_commands": int(pending_review),
        "allowed_commands": sorted(_allowed_command_types()),
    }
