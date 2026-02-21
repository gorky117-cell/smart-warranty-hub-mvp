import json
import tempfile
from pathlib import Path

from app.db import SessionLocal
from app.db_models import NotificationDB, UserDB
from app.services import kpi_watchdog


def _write_report(path: Path, pass_rate: float, failing_count: int) -> None:
    kpis = []
    for i in range(5):
        kpis.append(
            {
                "stakeholder": "Platform",
                "kpi": f"KPI-{i}",
                "value": 1.0,
                "status": "pass",
                "instrumented": True,
            }
        )
    for i in range(failing_count):
        kpis.append(
            {
                "stakeholder": "OEM",
                "kpi": f"FAIL-{i}",
                "value": 0.0,
                "status": "needs_improvement",
                "instrumented": True,
            }
        )
    report = {
        "summary": {
            "kpi_pass_rate_pct": pass_rate,
            "instrumented_kpis": len(kpis),
            "passing_kpis": len([k for k in kpis if k["status"] == "pass"]),
        },
        "kpis": kpis,
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_evaluate_kpi_health_alert_and_healthy():
    bad = {
        "ok": True,
        "summary": {"kpi_pass_rate_pct": 70.0},
        "kpis": [{"instrumented": True, "status": "needs_improvement", "kpi": "x", "stakeholder": "OEM"}] * 4,
    }
    out_bad = kpi_watchdog.evaluate_kpi_health(
        bad,
        policy={"min_pass_rate_pct": 85.0, "max_failing_kpis": 2},
    )
    assert out_bad["decision"] == "alert"

    good = {
        "ok": True,
        "summary": {"kpi_pass_rate_pct": 96.0},
        "kpis": [{"instrumented": True, "status": "pass", "kpi": "x", "stakeholder": "OEM"}] * 5,
    }
    out_good = kpi_watchdog.evaluate_kpi_health(
        good,
        policy={"min_pass_rate_pct": 85.0, "max_failing_kpis": 2},
    )
    assert out_good["decision"] == "healthy"


def test_run_kpi_watchdog_sends_oem_notification_on_alert():
    tmp = Path(tempfile.mkdtemp(prefix="kpi_watchdog_test_"))
    report_path = tmp / "report.json"
    policy_path = tmp / "policy.json"
    _write_report(report_path, pass_rate=70.0, failing_count=3)

    old_report = kpi_watchdog.os.getenv("KPI_SCORECARD_REPORT_FILE")
    old_policy = kpi_watchdog.os.getenv("KPI_WATCHDOG_POLICY_FILE")
    kpi_watchdog.os.environ["KPI_SCORECARD_REPORT_FILE"] = str(report_path).replace("\\", "/")
    kpi_watchdog.os.environ["KPI_WATCHDOG_POLICY_FILE"] = str(policy_path).replace("\\", "/")
    kpi_watchdog.set_watchdog_policy(
        {
            "enabled": True,
            "report_file": str(report_path).replace("\\", "/"),
            "notify_oem": True,
            "notify_admin": False,
            "min_pass_rate_pct": 85.0,
            "max_failing_kpis": 2,
        }
    )

    try:
        with SessionLocal() as db:
            db.query(NotificationDB).delete()
            db.query(UserDB).filter(UserDB.username == "oem_watchdog").delete()
            db.add(UserDB(username="oem_watchdog", role="oem", hashed_password="x", email="x@example.com", consent_analytics=1))
            db.commit()

            out = kpi_watchdog.run_kpi_watchdog(db, notify=True)
            assert out["ok"] is True
            assert out["decision"] == "alert"

            rows = (
                db.query(NotificationDB)
                .filter(
                    NotificationDB.audience == "oem",
                    NotificationDB.user_id == "oem_watchdog",
                    NotificationDB.type == "kpi_watchdog_alert",
                )
                .all()
            )
            assert len(rows) >= 1
    finally:
        if old_report is None:
            kpi_watchdog.os.environ.pop("KPI_SCORECARD_REPORT_FILE", None)
        else:
            kpi_watchdog.os.environ["KPI_SCORECARD_REPORT_FILE"] = old_report
        if old_policy is None:
            kpi_watchdog.os.environ.pop("KPI_WATCHDOG_POLICY_FILE", None)
        else:
            kpi_watchdog.os.environ["KPI_WATCHDOG_POLICY_FILE"] = old_policy
