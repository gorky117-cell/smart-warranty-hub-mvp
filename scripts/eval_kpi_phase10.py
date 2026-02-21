"""Phase 10 evaluator: KPI trend memory + remediation planning loop.

Outputs:
  - data/kpi_phase10_eval_50.json
  - test_data/kpi_phase10_cases_50.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.abspath("."))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 10 KPI remediation loop")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/kpi_phase10_eval.db")
    p.add_argument("--report-file", default="data/kpi_phase10_report.json")
    p.add_argument("--policy-file", default="data/kpi_phase10_policy.json")
    p.add_argument("--history-file", default="data/kpi_phase10_history.json")
    p.add_argument("--plan-file", default="data/kpi_phase10_plan.json")
    p.add_argument("--out", default="data/kpi_phase10_eval_50.json")
    p.add_argument("--cases-out", default="test_data/kpi_phase10_cases_50.json")
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


def _write_report(path: Path, pass_rate: float, fail_names: List[str], rows: int) -> Dict:
    kpis: List[Dict] = []
    pass_rows = max(1, rows - len(fail_names))
    for i in range(pass_rows):
        kpis.append(
            {
                "stakeholder": "Platform",
                "kpi": f"KPI-PASS-{i}",
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
    return {"pass_rate_pct": pass_rate, "failing": fail_names, "rows": len(kpis)}


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    report_path = Path(args.report_file)
    policy_path = Path(args.policy_file)
    history_path = Path(args.history_file)
    plan_path = Path(args.plan_file)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for p in [db_path, report_path, policy_path, history_path, plan_path]:
        if p.exists():
            p.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["KPI_SCORECARD_REPORT_FILE"] = str(report_path).replace("\\", "/")
    os.environ["KPI_WATCHDOG_POLICY_FILE"] = str(policy_path).replace("\\", "/")
    os.environ["KPI_HISTORY_FILE"] = str(history_path).replace("\\", "/")
    os.environ["KPI_REMEDIATION_PLAN_FILE"] = str(plan_path).replace("\\", "/")

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.db_models import NotificationDB, UserDB  # noqa: E402
    from app.deps import hash_password  # noqa: E402
    from app.services import kpi_remediation, kpi_watchdog  # noqa: E402

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
    case_rows: List[Dict] = []
    with SessionLocal() as db:
        db.merge(
            UserDB(
                username="oem_phase10",
                role="oem",
                hashed_password=hash_password("pass123"),
                email="oem_phase10@example.com",
                consent_analytics=1,
            )
        )
        db.merge(
            UserDB(
                username="admin_phase10",
                role="admin",
                hashed_password=hash_password("pass123"),
                email="admin_phase10@example.com",
                consent_analytics=1,
            )
        )
        db.commit()

        # Run 1: alert
        c1 = _write_report(report_path, 72.0, ["High-Risk Precision", "Model Calibration Error (ECE)", "Brier Score"], args.rows)
        t0 = time.perf_counter()
        run1 = kpi_remediation.run_kpi_remediation_cycle(db, notify=True, source="eval")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        c1["decision"] = run1.get("decision")
        c1["task_count"] = int(run1.get("task_count", 0) or 0)
        c1["trend"] = run1.get("trend", {}).get("trend")
        case_rows.append(c1)

        # Run 2: repeated alert (streak)
        c2 = _write_report(report_path, 74.0, ["High-Risk Precision", "Model Calibration Error (ECE)"], args.rows)
        t0 = time.perf_counter()
        run2 = kpi_remediation.run_kpi_remediation_cycle(db, notify=True, source="eval")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        c2["decision"] = run2.get("decision")
        c2["task_count"] = int(run2.get("task_count", 0) or 0)
        c2["alert_streak"] = int(run2.get("trend", {}).get("alert_streak", 0) or 0)
        case_rows.append(c2)

        # Run 3: healthy
        c3 = _write_report(report_path, 95.0, ["Stockout Rate"], args.rows)
        t0 = time.perf_counter()
        run3 = kpi_remediation.run_kpi_remediation_cycle(db, notify=False, source="eval")
        latencies.append((time.perf_counter() - t0) * 1000.0)
        c3["decision"] = run3.get("decision")
        c3["task_count"] = int(run3.get("task_count", 0) or 0)
        c3["trend"] = run3.get("trend", {}).get("trend")
        case_rows.append(c3)

        notif_count = (
            db.query(NotificationDB)
            .filter(NotificationDB.audience == "oem", NotificationDB.type == "kpi_remediation_plan")
            .count()
        )

    history = kpi_remediation.get_history(limit=365)
    latest_plan = kpi_remediation.load_latest_plan()
    summary = {
        "dataset_rows": int(args.rows),
        "run1_decision": run1.get("decision"),
        "run1_alert_ok": run1.get("decision") == "alert",
        "run1_tasks": int(run1.get("task_count", 0) or 0),
        "run2_decision": run2.get("decision"),
        "run2_alert_streak": int(run2.get("trend", {}).get("alert_streak", 0) or 0),
        "run2_streak_ok": int(run2.get("trend", {}).get("alert_streak", 0) or 0) >= 2,
        "run3_decision": run3.get("decision"),
        "run3_healthy_ok": run3.get("decision") == "healthy",
        "run3_trend": run3.get("trend", {}).get("trend"),
        "history_rows": len(history),
        "history_persist_ok": len(history) >= 3,
        "latest_plan_task_count": int(latest_plan.get("task_count", 0) or 0),
        "remediation_notifications": int(notif_count),
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
        "decision_accuracy_pct": _pct(
            sum(
                [
                    1 if run1.get("decision") == "alert" else 0,
                    1 if run2.get("decision") == "alert" else 0,
                    1 if run3.get("decision") == "healthy" else 0,
                ]
            ),
            3,
        ),
    }

    report = {
        "summary": summary,
        "runs": {"run1": run1, "run2": run2, "run3": run3},
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "report_file": str(report_path).replace("\\", "/"),
            "policy_file": str(policy_path).replace("\\", "/"),
            "history_file": str(history_path).replace("\\", "/"),
            "plan_file": str(plan_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
    }

    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps(case_rows, indent=2), encoding="utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 10 (KPI Remediation Loop) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
