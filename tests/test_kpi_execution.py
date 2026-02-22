import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import json

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB
from app.services import kpi_execution, kpi_remediation


def _seed_latest_plan(path: Path) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "decision": "alert",
        "summary": "test plan",
        "trend": {"trend": "worsening"},
        "task_count": 2,
        "tasks": [
            {
                "id": "T01",
                "stakeholder": "OEM",
                "kpi": "High-Risk Precision",
                "current_value": 40,
                "target": ">=55",
                "priority": "high",
                "owner": "Data Science",
                "eta_days": 7,
                "action": "retune",
            },
            {
                "id": "T02",
                "stakeholder": "Platform",
                "kpi": "Model Calibration Error (ECE)",
                "current_value": 0.2,
                "target": "<=0.12",
                "priority": "high",
                "owner": "ML Platform",
                "eta_days": 5,
                "action": "calibrate",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_sync_update_and_metrics():
    tmp = Path(tempfile.mkdtemp(prefix="kpi_execution_test_"))
    board_file = tmp / "board.json"
    plan_file = tmp / "plan.json"
    _seed_latest_plan(plan_file)

    old_board = kpi_execution.os.getenv("KPI_TASK_BOARD_FILE")
    old_plan = kpi_remediation.os.getenv("KPI_REMEDIATION_PLAN_FILE")
    kpi_execution.os.environ["KPI_TASK_BOARD_FILE"] = str(board_file).replace("\\", "/")
    kpi_remediation.os.environ["KPI_REMEDIATION_PLAN_FILE"] = str(plan_file).replace("\\", "/")
    try:
        synced = kpi_execution.sync_from_latest_plan()
        assert synced["ok"] is True
        assert synced["tasks_total"] == 2
        # Re-sync should not duplicate tasks.
        synced2 = kpi_execution.sync_from_latest_plan()
        assert synced2["tasks_total"] == 2
        assert synced2["added"] == 0

        rows = kpi_execution.list_tasks()
        assert len(rows) == 2
        task_key = rows[0]["task_key"]
        upd = kpi_execution.update_task_status(task_key, status="done", notes="completed")
        assert upd["ok"] is True
        assert upd["task"]["status"] == "done"

        m = kpi_execution.execution_metrics()
        assert m["tasks_total"] == 2
        assert m["status_counts"]["done"] >= 1
    finally:
        if old_board is None:
            kpi_execution.os.environ.pop("KPI_TASK_BOARD_FILE", None)
        else:
            kpi_execution.os.environ["KPI_TASK_BOARD_FILE"] = old_board
        if old_plan is None:
            kpi_remediation.os.environ.pop("KPI_REMEDIATION_PLAN_FILE", None)
        else:
            kpi_remediation.os.environ["KPI_REMEDIATION_PLAN_FILE"] = old_plan


def test_execution_cycle_overdue_notification():
    tmp = Path(tempfile.mkdtemp(prefix="kpi_execution_notify_"))
    board_file = tmp / "board.json"
    plan_file = tmp / "plan.json"
    _seed_latest_plan(plan_file)

    old_board = kpi_execution.os.getenv("KPI_TASK_BOARD_FILE")
    old_plan = kpi_remediation.os.getenv("KPI_REMEDIATION_PLAN_FILE")
    kpi_execution.os.environ["KPI_TASK_BOARD_FILE"] = str(board_file).replace("\\", "/")
    kpi_remediation.os.environ["KPI_REMEDIATION_PLAN_FILE"] = str(plan_file).replace("\\", "/")
    try:
        with SessionLocal() as db:
            db.query(NotificationDB).filter(NotificationDB.type == "kpi_execution_overdue").delete()
            db.query(UserDB).filter(UserDB.username == "oem_exec").delete(synchronize_session=False)
            db.add(UserDB(username="oem_exec", role="oem", hashed_password="x", email="x@example.com", consent_analytics=1))
            db.commit()

            kpi_execution.sync_from_latest_plan()
            board = kpi_execution._load_board()  # test-only internal access
            board["tasks"][0]["due_at"] = (datetime.utcnow() - timedelta(days=1)).isoformat()
            kpi_execution._save_board(board)  # test-only internal access

            out = kpi_execution.run_execution_cycle(db, notify=True, source="test")
            assert out["ok"] is True
            assert int(out["metrics"]["overdue_active"]) >= 1
            rows = (
                db.query(NotificationDB)
                .filter(NotificationDB.type == "kpi_execution_overdue", NotificationDB.audience == "oem")
                .all()
            )
            assert len(rows) >= 1
    finally:
        if old_board is None:
            kpi_execution.os.environ.pop("KPI_TASK_BOARD_FILE", None)
        else:
            kpi_execution.os.environ["KPI_TASK_BOARD_FILE"] = old_board
        if old_plan is None:
            kpi_remediation.os.environ.pop("KPI_REMEDIATION_PLAN_FILE", None)
        else:
            kpi_remediation.os.environ["KPI_REMEDIATION_PLAN_FILE"] = old_plan
