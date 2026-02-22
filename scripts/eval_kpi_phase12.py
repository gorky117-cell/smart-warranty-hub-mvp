"""Phase 12 evaluator: remediation execution tracking + closure KPI loop.

Outputs:
  - data/kpi_phase12_eval_50.json
  - test_data/kpi_phase12_cases_50.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.abspath("."))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 12 KPI execution tracking")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/kpi_phase12_eval.db")
    p.add_argument("--report-file", default="data/kpi_phase12_report.json")
    p.add_argument("--policy-file", default="data/kpi_phase12_policy.json")
    p.add_argument("--history-file", default="data/kpi_phase12_history.json")
    p.add_argument("--plan-file", default="data/kpi_phase12_plan.json")
    p.add_argument("--board-file", default="data/kpi_phase12_board.json")
    p.add_argument("--out", default="data/kpi_phase12_eval_50.json")
    p.add_argument("--cases-out", default="test_data/kpi_phase12_cases_50.json")
    return p.parse_args()


def _pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _write_report(path: Path, pass_rate: float, fail_names: List[str], rows: int) -> None:
    kpis: List[Dict] = []
    pass_rows = max(1, rows - len(fail_names))
    for i in range(pass_rows):
        kpis.append(
            {
                "stakeholder": "Platform",
                "kpi": f"PASS-{i}",
                "status": "pass",
                "instrumented": True,
                "value": 1.0,
                "target": "ok",
            }
        )
    for name in fail_names:
        kpis.append(
            {
                "stakeholder": "OEM",
                "kpi": name,
                "status": "needs_improvement",
                "instrumented": True,
                "value": 0.0,
                "target": "improve",
            }
        )
    payload = {
        "summary": {
            "kpi_pass_rate_pct": pass_rate,
            "instrumented_kpis": len(kpis),
            "passing_kpis": len([x for x in kpis if x["status"] == "pass"]),
        },
        "kpis": kpis,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    report_path = Path(args.report_file)
    policy_path = Path(args.policy_file)
    history_path = Path(args.history_file)
    plan_path = Path(args.plan_file)
    board_path = Path(args.board_file)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    for p in [db_path, report_path, policy_path, history_path, plan_path, board_path]:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            p.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["KPI_SCORECARD_REPORT_FILE"] = str(report_path).replace("\\", "/")
    os.environ["KPI_WATCHDOG_POLICY_FILE"] = str(policy_path).replace("\\", "/")
    os.environ["KPI_HISTORY_FILE"] = str(history_path).replace("\\", "/")
    os.environ["KPI_REMEDIATION_PLAN_FILE"] = str(plan_path).replace("\\", "/")
    os.environ["KPI_TASK_BOARD_FILE"] = str(board_path).replace("\\", "/")

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.db_models import NotificationDB, UserDB  # noqa: E402
    from app.deps import hash_password  # noqa: E402
    from app.services import kpi_watchdog, kpi_remediation, kpi_execution  # noqa: E402

    Base.metadata.create_all(bind=engine)

    kpi_watchdog.set_watchdog_policy(
        {
            "enabled": True,
            "report_file": str(report_path).replace("\\", "/"),
            "min_pass_rate_pct": 85.0,
            "max_failing_kpis": 2,
            "notify_oem": True,
            "notify_admin": True,
        }
    )

    latencies: List[float] = []
    cases: List[Dict] = []
    with SessionLocal() as db:
        db.merge(UserDB(username="oem_phase12", role="oem", hashed_password=hash_password("pass123"), email="oem12@example.com", consent_analytics=1))
        db.merge(UserDB(username="admin_phase12", role="admin", hashed_password=hash_password("pass123"), email="admin12@example.com", consent_analytics=1))
        db.commit()

        # Build latest plan via remediation cycle (alert).
        _write_report(report_path, 73.0, ["High-Risk Precision", "Model Calibration Error (ECE)", "Brier Score"], args.rows)
        rem = kpi_remediation.run_kpi_remediation_cycle(db, notify=True, source="eval_phase12")

        # Run 1: execution sync from latest plan.
        t0 = time.perf_counter()
        run1 = kpi_execution.run_execution_cycle(db, notify=False, source="eval_phase12")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        case1 = {
            "case": "sync_from_plan",
            "tasks_total": int(run1.get("metrics", {}).get("tasks_total", 0)),
            "added": int(run1.get("sync", {}).get("added", 0)),
            "decision": "ok" if int(run1.get("metrics", {}).get("tasks_total", 0)) > 0 else "fail",
        }
        cases.append(case1)

        # Apply status transitions.
        tasks = kpi_execution.list_tasks(limit=10)
        if tasks:
            kpi_execution.update_task_status(tasks[0]["task_key"], status="done", notes="completed in eval")
        if len(tasks) >= 2:
            kpi_execution.update_task_status(tasks[1]["task_key"], status="in_progress", notes="ongoing")
        if len(tasks) >= 3:
            kpi_execution.update_task_status(tasks[2]["task_key"], status="blocked", notes="dependency")

        # Force one task overdue to validate overdue alert path.
        board = kpi_execution._load_board()
        if board.get("tasks"):
            for row in board["tasks"]:
                st = str(row.get("status", "")).lower()
                if st not in ("done", "dropped"):
                    row["due_at"] = (datetime.utcnow() - timedelta(days=1)).isoformat()
                    break
            kpi_execution._save_board(board)

        # Run 2: execution with notify.
        t0 = time.perf_counter()
        run2 = kpi_execution.run_execution_cycle(db, notify=True, source="eval_phase12")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        metrics2 = run2.get("metrics", {})
        case2 = {
            "case": "status_and_overdue",
            "completion_rate_pct": float(metrics2.get("completion_rate_pct", 0.0) or 0.0),
            "overdue_active": int(metrics2.get("overdue_active", 0) or 0),
            "notified": int(run2.get("notified", 0) or 0),
            "decision": "ok" if int(metrics2.get("overdue_active", 0) or 0) >= 1 else "fail",
        }
        cases.append(case2)

        notif_count = (
            db.query(NotificationDB)
            .filter(NotificationDB.audience == "oem", NotificationDB.type == "kpi_execution_overdue")
            .count()
        )

    metrics_final = kpi_execution.execution_metrics()
    summary = {
        "dataset_rows": int(args.rows),
        "remediation_task_seeded": int(rem.get("task_count", 0) or 0),
        "run1_tasks_total": int(run1.get("metrics", {}).get("tasks_total", 0)),
        "run1_sync_added": int(run1.get("sync", {}).get("added", 0)),
        "run2_done_count": int(metrics_final.get("status_counts", {}).get("done", 0)),
        "run2_in_progress_count": int(metrics_final.get("status_counts", {}).get("in_progress", 0)),
        "run2_blocked_count": int(metrics_final.get("status_counts", {}).get("blocked", 0)),
        "run2_completion_rate_pct": float(metrics_final.get("completion_rate_pct", 0.0) or 0.0),
        "run2_overdue_active": int(metrics_final.get("overdue_active", 0) or 0),
        "run2_overdue_notify_count": int(notif_count),
        "task_lifecycle_integrity_ok": (
            int(metrics_final.get("status_counts", {}).get("done", 0)) >= 1
            and int(metrics_final.get("status_counts", {}).get("in_progress", 0)) >= 1
            and int(metrics_final.get("status_counts", {}).get("blocked", 0)) >= 1
        ),
        "overdue_alert_ok": int(metrics_final.get("overdue_active", 0) or 0) >= 1 and int(notif_count) >= 1,
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
        "execution_success_pct": _pct(
            sum(
                [
                    1 if case1["decision"] == "ok" else 0,
                    1 if case2["decision"] == "ok" else 0,
                    1 if int(metrics_final.get("status_counts", {}).get("done", 0)) >= 1 else 0,
                ]
            ),
            3,
        ),
    }

    report = {
        "summary": summary,
        "runs": {"remediation_seed": rem, "run1_sync": run1, "run2_execution": run2},
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "report_file": str(report_path).replace("\\", "/"),
            "policy_file": str(policy_path).replace("\\", "/"),
            "history_file": str(history_path).replace("\\", "/"),
            "plan_file": str(plan_path).replace("\\", "/"),
            "board_file": str(board_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
    }

    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps(cases, indent=2), encoding="utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 12 (KPI Execution Tracking) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
