import json
import tempfile
from pathlib import Path

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB
from app.services import kpi_remediation, kpi_watchdog


def _write_report(path: Path, pass_rate: float, failing_names: list[str]) -> None:
    kpis = []
    for i in range(5):
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
    for name in failing_names:
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
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_kpi_remediation_cycle_writes_history_and_plan():
    tmp = Path(tempfile.mkdtemp(prefix="kpi_remediation_test_"))
    report_path = tmp / "report.json"
    policy_path = tmp / "watchdog_policy.json"
    history_path = tmp / "history.json"
    plan_path = tmp / "plan.json"

    _write_report(report_path, pass_rate=72.0, failing_names=["High-Risk Precision", "Model Calibration Error (ECE)"])

    old_env = {
        "KPI_SCORECARD_REPORT_FILE": kpi_remediation.os.getenv("KPI_SCORECARD_REPORT_FILE"),
        "KPI_WATCHDOG_POLICY_FILE": kpi_remediation.os.getenv("KPI_WATCHDOG_POLICY_FILE"),
        "KPI_HISTORY_FILE": kpi_remediation.os.getenv("KPI_HISTORY_FILE"),
        "KPI_REMEDIATION_PLAN_FILE": kpi_remediation.os.getenv("KPI_REMEDIATION_PLAN_FILE"),
    }
    kpi_remediation.os.environ["KPI_SCORECARD_REPORT_FILE"] = str(report_path).replace("\\", "/")
    kpi_remediation.os.environ["KPI_WATCHDOG_POLICY_FILE"] = str(policy_path).replace("\\", "/")
    kpi_remediation.os.environ["KPI_HISTORY_FILE"] = str(history_path).replace("\\", "/")
    kpi_remediation.os.environ["KPI_REMEDIATION_PLAN_FILE"] = str(plan_path).replace("\\", "/")

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

    try:
        with SessionLocal() as db:
            db.query(NotificationDB).filter(NotificationDB.type == "kpi_remediation_plan").delete()
            db.query(UserDB).filter(UserDB.username.in_(["oem_remed", "admin_remed"])).delete(synchronize_session=False)
            db.add(UserDB(username="oem_remed", role="oem", hashed_password="x", email="o@example.com", consent_analytics=1))
            db.add(UserDB(username="admin_remed", role="admin", hashed_password="x", email="a@example.com", consent_analytics=1))
            db.commit()

            out1 = kpi_remediation.run_kpi_remediation_cycle(db, notify=True, source="test")
            assert out1["ok"] is True
            assert out1["decision"] == "alert"
            assert int(out1["task_count"]) >= 1
            assert history_path.exists()
            assert plan_path.exists()
            assert len(kpi_remediation.get_history(limit=10)) >= 1

            _write_report(report_path, pass_rate=96.0, failing_names=["Stockout Rate"])
            out2 = kpi_remediation.run_kpi_remediation_cycle(db, notify=False, source="test")
            assert out2["ok"] is True
            assert out2["decision"] == "healthy"
            trend = out2.get("trend", {})
            assert trend.get("trend") in ("improving", "stable", "worsening")
            assert len(kpi_remediation.get_history(limit=10)) >= 2
    finally:
        for key, value in old_env.items():
            if value is None:
                kpi_remediation.os.environ.pop(key, None)
            else:
                kpi_remediation.os.environ[key] = value
