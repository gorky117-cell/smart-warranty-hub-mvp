"""Phase 9 evaluator: KPI watchdog policy + alerting + scheduler-ready run.

Outputs:
  - data/kpi_watchdog_phase9_eval_50.json
  - test_data/kpi_watchdog_phase9_cases_50.json
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
    p = argparse.ArgumentParser(description="Evaluate Phase 9 KPI watchdog")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/kpi_watchdog_phase9_eval.db")
    p.add_argument("--report-file", default="data/kpi_watchdog_phase9_report.json")
    p.add_argument("--policy-file", default="data/kpi_watchdog_phase9_policy.json")
    p.add_argument("--out", default="data/kpi_watchdog_phase9_eval_50.json")
    p.add_argument("--cases-out", default="test_data/kpi_watchdog_phase9_cases_50.json")
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


def _write_report(path: Path, rows: int, *, pass_rate: float, failing_count: int) -> Dict:
    kpis: List[Dict] = []
    pass_count = max(0, rows - failing_count)
    for i in range(pass_count):
        kpis.append(
            {
                "stakeholder": "Platform",
                "kpi": f"KPI-PASS-{i}",
                "value": 1.0,
                "status": "pass",
                "instrumented": True,
            }
        )
    for i in range(failing_count):
        kpis.append(
            {
                "stakeholder": "OEM",
                "kpi": f"KPI-FAIL-{i}",
                "value": 0.0,
                "status": "needs_improvement",
                "instrumented": True,
            }
        )
    case = {
        "pass_rate_pct": pass_rate,
        "failing_count": failing_count,
        "rows": len(kpis),
    }
    payload = {
        "summary": {
            "dataset_rows": len(kpis),
            "kpi_pass_rate_pct": pass_rate,
            "instrumented_kpis": len(kpis),
            "passing_kpis": pass_count,
        },
        "kpis": kpis,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return case


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    report_path = Path(args.report_file)
    policy_path = Path(args.policy_file)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    if report_path.exists():
        report_path.unlink()
    if policy_path.exists():
        policy_path.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["KPI_SCORECARD_REPORT_FILE"] = str(report_path).replace("\\", "/")
    os.environ["KPI_WATCHDOG_POLICY_FILE"] = str(policy_path).replace("\\", "/")

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.db_models import NotificationDB, UserDB  # noqa: E402
    from app.deps import hash_password  # noqa: E402
    from app.services import kpi_watchdog  # noqa: E402

    Base.metadata.create_all(bind=engine)

    cases: List[Dict] = []
    latencies_ms: List[float] = []

    with SessionLocal() as db:
        db.merge(
            UserDB(
                username="oem_phase9",
                role="oem",
                hashed_password=hash_password("pass123"),
                email="oem_phase9@example.com",
                consent_analytics=1,
            )
        )
        db.merge(
            UserDB(
                username="admin_phase9",
                role="admin",
                hashed_password=hash_password("pass123"),
                email="admin_phase9@example.com",
                consent_analytics=1,
            )
        )
        db.commit()

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

        # Run 1: degraded report -> alert expected.
        case1 = _write_report(report_path, rows=max(1, args.rows), pass_rate=72.0, failing_count=6)
        t0 = time.perf_counter()
        run1 = kpi_watchdog.run_kpi_watchdog(db, notify=True)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        case1["decision"] = run1.get("decision")
        case1["notified"] = int(run1.get("notified", 0) or 0)
        cases.append(case1)

        # Run 2: healthy report -> healthy expected.
        case2 = _write_report(report_path, rows=max(1, args.rows), pass_rate=96.0, failing_count=1)
        t0 = time.perf_counter()
        run2 = kpi_watchdog.run_kpi_watchdog(db, notify=True)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        case2["decision"] = run2.get("decision")
        case2["notified"] = int(run2.get("notified", 0) or 0)
        cases.append(case2)

        total_oem_watchdog_notifications = (
            db.query(NotificationDB)
            .filter(NotificationDB.audience == "oem", NotificationDB.type.in_(["kpi_watchdog_alert", "kpi_watchdog_healthy"]))
            .count()
        )

    decisions_ok = 0
    if run1.get("decision") == "alert":
        decisions_ok += 1
    if run2.get("decision") == "healthy":
        decisions_ok += 1

    summary = {
        "dataset_rows": int(args.rows),
        "run1_decision": run1.get("decision"),
        "run1_alert_ok": run1.get("decision") == "alert",
        "run1_notified": int(run1.get("notified", 0) or 0),
        "run2_decision": run2.get("decision"),
        "run2_healthy_ok": run2.get("decision") == "healthy",
        "run2_notified": int(run2.get("notified", 0) or 0),
        "total_watchdog_notifications": int(total_oem_watchdog_notifications),
        "latency_p50_ms": round(_percentile(latencies_ms, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies_ms, 0.95), 2),
        "decision_accuracy_pct": _pct(decisions_ok, 2),
    }

    report = {
        "summary": summary,
        "runs": {"run1_alert": run1, "run2_healthy": run2},
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "report_file": str(report_path).replace("\\", "/"),
            "policy_file": str(policy_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
    }

    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps(cases, indent=2), encoding="utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 9 (KPI Watchdog) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
