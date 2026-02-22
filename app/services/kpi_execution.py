from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from .audit import log_action
from .notifications import create_oem_notification
from ..db_models import UserDB
from . import kpi_remediation


VALID_STATUSES = {"open", "in_progress", "blocked", "done", "dropped"}


def _board_path() -> Path:
    return Path(os.getenv("KPI_TASK_BOARD_FILE", "data/kpi_task_board.json"))


def _load_board() -> Dict:
    path = _board_path()
    if not path.exists():
        return {"tasks": [], "updated_at": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": [], "updated_at": None}
    if not isinstance(raw, dict):
        return {"tasks": [], "updated_at": None}
    tasks = raw.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    return {"tasks": [t for t in tasks if isinstance(t, dict)], "updated_at": raw.get("updated_at")}


def _save_board(board: Dict) -> Dict:
    board = dict(board or {})
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    board["tasks"] = tasks
    board["updated_at"] = datetime.utcnow().isoformat()
    path = _board_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    return board


def _task_key(task: Dict) -> str:
    if task.get("task_key"):
        return str(task.get("task_key"))
    task_id = task.get("id") or task.get("task_id") or ""
    return f"{task.get('kpi','')}::{task_id}"


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def sync_from_latest_plan(plan: Optional[Dict] = None) -> Dict:
    plan = plan if isinstance(plan, dict) and plan else kpi_remediation.load_latest_plan()
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    board = _load_board()
    existing = board.get("tasks", [])
    by_key = {_task_key(t): t for t in existing if isinstance(t, dict)}
    now = datetime.utcnow().isoformat()
    added = 0
    updated = 0

    for task in tasks:
        if not isinstance(task, dict):
            continue
        key = _task_key(task)
        eta_days = int(task.get("eta_days", 10) or 10)
        due_at = (datetime.utcnow() + timedelta(days=max(1, eta_days))).isoformat()
        if key in by_key:
            row = by_key[key]
            row["priority"] = task.get("priority")
            row["owner"] = task.get("owner")
            row["eta_days"] = eta_days
            row["action"] = task.get("action")
            row["target"] = task.get("target")
            row["current_value"] = task.get("current_value")
            row["updated_at"] = now
            updated += 1
        else:
            by_key[key] = {
                "task_id": task.get("id"),
                "task_key": key,
                "kpi": task.get("kpi"),
                "stakeholder": task.get("stakeholder"),
                "owner": task.get("owner"),
                "priority": task.get("priority", "medium"),
                "status": "open",
                "eta_days": eta_days,
                "due_at": due_at,
                "target": task.get("target"),
                "current_value": task.get("current_value"),
                "action": task.get("action"),
                "notes": "",
                "created_at": now,
                "updated_at": now,
            }
            added += 1

    merged = list(by_key.values())
    merged.sort(key=lambda x: (str(x.get("status")), str(x.get("priority")), str(x.get("kpi"))))
    board["tasks"] = merged
    _save_board(board)
    return {"ok": True, "tasks_total": len(merged), "added": added, "updated": updated, "board_file": str(_board_path()).replace("\\", "/")}


def list_tasks(status: Optional[str] = None, limit: int = 200) -> List[Dict]:
    rows = _load_board().get("tasks", [])
    if status:
        s = str(status).strip().lower()
        rows = [r for r in rows if str(r.get("status", "")).lower() == s]
    return rows[: max(1, int(limit or 200))]


def update_task_status(task_key: str, *, status: str, notes: Optional[str] = None, owner: Optional[str] = None) -> Dict:
    new_status = str(status or "").strip().lower()
    if new_status not in VALID_STATUSES:
        return {"ok": False, "error": "invalid_status", "valid_statuses": sorted(VALID_STATUSES)}
    board = _load_board()
    tasks = board.get("tasks", [])
    for row in tasks:
        if str(row.get("task_key")) == str(task_key):
            row["status"] = new_status
            if notes is not None:
                row["notes"] = str(notes)
            if owner:
                row["owner"] = str(owner)
            row["updated_at"] = datetime.utcnow().isoformat()
            if new_status == "done":
                row["done_at"] = datetime.utcnow().isoformat()
            _save_board(board)
            return {"ok": True, "task": row}
    return {"ok": False, "error": "task_not_found"}


def execution_metrics() -> Dict:
    rows = _load_board().get("tasks", [])
    now = datetime.utcnow()
    counts = {"open": 0, "in_progress": 0, "blocked": 0, "done": 0, "dropped": 0}
    overdue_open = 0
    overdue_all = 0
    for row in rows:
        st = str(row.get("status", "open")).lower()
        if st not in counts:
            st = "open"
        counts[st] += 1
        due = _parse_iso(row.get("due_at"))
        if due and due < now and st not in ("done", "dropped"):
            overdue_all += 1
            if st == "open":
                overdue_open += 1
    total = len(rows)
    done = counts["done"]
    completion_rate = round((done / total) * 100.0, 2) if total else 0.0
    return {
        "tasks_total": total,
        "status_counts": counts,
        "completion_rate_pct": completion_rate,
        "overdue_open": overdue_open,
        "overdue_active": overdue_all,
        "board_file": str(_board_path()).replace("\\", "/"),
    }


def _recipients(db: Session) -> List[str]:
    out: List[str] = []
    for row in db.query(UserDB.username).filter(UserDB.role.in_(["oem", "admin"])).all():
        if row and row[0]:
            uid = str(row[0])
            if uid not in out:
                out.append(uid)
    return out


def run_execution_cycle(db: Session, *, notify: bool = True, source: str = "manual") -> Dict:
    plan = kpi_remediation.load_latest_plan()
    sync = sync_from_latest_plan(plan)
    metrics = execution_metrics()

    notified = 0
    if notify and int(metrics.get("overdue_active", 0) or 0) > 0:
        msg = (
            f"KPI execution overdue tasks detected: {metrics.get('overdue_active')} active overdue "
            f"({metrics.get('overdue_open')} still open)."
        )
        for uid in _recipients(db):
            try:
                created = create_oem_notification(
                    db=db,
                    user_id=uid,
                    ntype="kpi_execution_overdue",
                    title="KPI execution overdue tasks",
                    message=msg,
                    severity="warning",
                )
                if created:
                    notified += 1
            except Exception:
                continue

    log_action(
        "kpi_execution_cycle",
        f"source={source} total={metrics.get('tasks_total')} completion={metrics.get('completion_rate_pct')} overdue={metrics.get('overdue_active')} notified={notified}",
    )
    return {
        "ok": True,
        "source": source,
        "sync": sync,
        "metrics": metrics,
        "notified": notified,
    }
