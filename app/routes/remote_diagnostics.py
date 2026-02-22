from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, require_oem_or_admin
from ..services import remote_diagnostics as rd_service


router = APIRouter()


class StartSessionRequest(BaseModel):
    user_id: str
    warranty_id: str
    connector_name: Optional[str] = None
    device_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    session_id: str
    command_type: str
    command_payload: Optional[Dict[str, Any]] = None
    require_review: bool = True
    review_reason: Optional[str] = None
    connector_name: Optional[str] = None
    execute_now: bool = False


class DecisionRequest(BaseModel):
    reason: Optional[str] = None
    execute_now: bool = False


class ExecuteRequest(BaseModel):
    force: bool = False


class QueueRunRequest(BaseModel):
    limit: int = 20


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _session_out(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "warranty_id": row.warranty_id,
        "requested_by": row.requested_by,
        "connector_name": row.connector_name,
        "device_id": row.device_id,
        "status": row.status,
        "context": row.context_json or {},
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "last_command_at": _dt(row.last_command_at),
    }


def _command_out(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "warranty_id": row.warranty_id,
        "user_id": row.user_id,
        "requested_by": row.requested_by,
        "command_type": row.command_type,
        "command_payload": row.command_payload or {},
        "status": row.status,
        "require_review": bool(row.require_review),
        "review_id": row.review_id,
        "review_reason": row.review_reason,
        "connector_name": row.connector_name,
        "attempt_count": int(row.attempt_count or 0),
        "executed_by": row.executed_by,
        "result": row.result_json,
        "error": row.error_text,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "executed_at": _dt(row.executed_at),
    }


@router.get("/health")
def diagnostics_health(db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    return rd_service.health(db)


@router.post("/sessions/start")
def start_session(payload: StartSessionRequest, db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    try:
        row = rd_service.create_session(
            db,
            user_id=payload.user_id,
            warranty_id=payload.warranty_id,
            requested_by=current.username,
            connector_name=payload.connector_name,
            device_id=payload.device_id,
            context=payload.context or {},
        )
        return {"ok": True, "session": _session_out(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sessions")
def list_sessions(
    user_id: str | None = None,
    warranty_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    rows = rd_service.list_sessions(
        db,
        user_id=user_id,
        warranty_id=warranty_id,
        status=status,
        limit=limit,
    )
    return {"ok": True, "count": len(rows), "sessions": [_session_out(r) for r in rows]}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    row = rd_service.get_session(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {"ok": True, "session": _session_out(row)}


@router.post("/commands/request")
def request_command(payload: CommandRequest, db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    try:
        row = rd_service.request_command(
            db,
            session_id=payload.session_id,
            command_type=payload.command_type,
            command_payload=payload.command_payload or {},
            requested_by=current.username,
            require_review=bool(payload.require_review),
            review_reason=payload.review_reason,
            connector_name=payload.connector_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result: Dict[str, Any] = {"ok": True, "command": _command_out(row)}
    if payload.execute_now and row.status == "queued":
        try:
            exec_res = rd_service.execute_command(db, command_id=row.id, executor=current.username, force=False)
            row = rd_service.get_command(db, row.id) or row
            result["execution"] = exec_res
            result["command"] = _command_out(row)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/commands")
def list_commands(
    session_id: str | None = None,
    warranty_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    rows = rd_service.list_commands(
        db,
        session_id=session_id,
        warranty_id=warranty_id,
        user_id=user_id,
        status=status,
        limit=limit,
    )
    return {"ok": True, "count": len(rows), "commands": [_command_out(r) for r in rows]}


@router.get("/commands/{command_id}")
def get_command(command_id: str, db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    row = rd_service.get_command(db, command_id)
    if not row:
        raise HTTPException(status_code=404, detail="command_not_found")
    exec_rows = rd_service.get_command_executions(db, command_id=command_id, limit=20)
    return {
        "ok": True,
        "command": _command_out(row),
        "executions": [
            {
                "id": e.id,
                "command_id": e.command_id,
                "session_id": e.session_id,
                "connector_name": e.connector_name,
                "http_status": e.http_status,
                "success": bool(e.success),
                "error": e.error_text,
                "latency_ms": e.latency_ms,
                "request": e.request_json or {},
                "response": e.response_json or {},
                "created_at": _dt(e.created_at),
            }
            for e in exec_rows
        ],
    }


@router.post("/commands/{command_id}/approve")
def approve_command(
    command_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    try:
        row = rd_service.decide_command(
            db,
            command_id=command_id,
            approved=True,
            reviewer=current.username,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    out: Dict[str, Any] = {"ok": True, "command": _command_out(row)}
    if payload.execute_now and row.status == "queued":
        try:
            exec_res = rd_service.execute_command(db, command_id=command_id, executor=current.username, force=False)
            row = rd_service.get_command(db, command_id) or row
            out["execution"] = exec_res
            out["command"] = _command_out(row)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return out


@router.post("/commands/{command_id}/reject")
def reject_command(
    command_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    try:
        row = rd_service.decide_command(
            db,
            command_id=command_id,
            approved=False,
            reviewer=current.username,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "command": _command_out(row)}


@router.post("/commands/{command_id}/execute")
def execute_command(
    command_id: str,
    payload: ExecuteRequest,
    db: Session = Depends(get_db),
    current=Depends(require_oem_or_admin),
):
    try:
        exec_res = rd_service.execute_command(
            db,
            command_id=command_id,
            executor=current.username,
            force=bool(payload.force),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = rd_service.get_command(db, command_id)
    return {"ok": True, "execution": exec_res, "command": _command_out(row) if row else None}


@router.post("/run-pending")
def run_pending(payload: QueueRunRequest, db: Session = Depends(get_db), current=Depends(require_oem_or_admin)):
    result = rd_service.run_pending_commands(
        db,
        limit=payload.limit,
        executor=current.username,
    )
    return {"ok": True, **result}
