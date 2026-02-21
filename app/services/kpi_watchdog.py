from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..db_models import UserDB
from .audit import log_action
from .notifications import create_oem_notification


def _policy_path() -> Path:
    return Path(os.getenv("KPI_WATCHDOG_POLICY_FILE", "data/kpi_watchdog_policy.json"))


def _default_report_path() -> Path:
    return Path(os.getenv("KPI_SCORECARD_REPORT_FILE", "data/kpi_phase8_eval_50.json"))


def _default_policy() -> Dict:
    return {
        "enabled": True,
        "report_file": str(_default_report_path()).replace("\\", "/"),
        "min_pass_rate_pct": 85.0,
        "max_failing_kpis": 2,
        "notify_oem": True,
        "notify_admin": True,
        "sender_label": "kpi-watchdog",
        "severity_on_alert": "warning",
    }


def get_watchdog_policy() -> Dict:
    path = _policy_path()
    if not path.exists():
        return _default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _default_policy()
        out = _default_policy()
        out.update(raw)
        return out
    except Exception:
        return _default_policy()


def set_watchdog_policy(payload: Dict) -> Dict:
    if not isinstance(payload, dict):
        payload = {}
    current = get_watchdog_policy()
    current.update(payload)
    path = _policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def load_kpi_report(report_file: Optional[str] = None) -> Dict:
    path = Path(report_file) if report_file else Path(get_watchdog_policy().get("report_file") or _default_report_path())
    if not path.exists():
        return {"ok": False, "error": "report_not_found", "path": str(path).replace("\\", "/")}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": "report_parse_error", "detail": str(exc), "path": str(path).replace("\\", "/")}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "report_invalid_type", "path": str(path).replace("\\", "/")}
    payload["ok"] = True
    payload["path"] = str(path).replace("\\", "/")
    return payload


@dataclass
class KpiHealth:
    decision: str
    pass_rate_pct: float
    instrumented_kpis: int
    passing_kpis: int
    failing_kpis: List[Dict]
    summary: Dict


def evaluate_kpi_health(report: Dict, policy: Optional[Dict] = None) -> Dict:
    policy = policy or get_watchdog_policy()
    if not isinstance(report, dict) or not report.get("ok"):
        return {
            "ok": False,
            "decision": "error",
            "error": "invalid_report",
            "detail": report.get("error") if isinstance(report, dict) else "not_a_dict",
        }

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    kpis = report.get("kpis") if isinstance(report.get("kpis"), list) else []

    instrumented = [k for k in kpis if isinstance(k, dict) and bool(k.get("instrumented"))]
    passing = [k for k in instrumented if str(k.get("status")) == "pass"]
    failing = [k for k in instrumented if str(k.get("status")) != "pass"]

    pass_rate = float(summary.get("kpi_pass_rate_pct", 0.0) or 0.0)
    if pass_rate <= 0 and instrumented:
        pass_rate = (len(passing) / len(instrumented)) * 100.0

    min_pass_rate = float(policy.get("min_pass_rate_pct", 85.0) or 85.0)
    max_failing = int(policy.get("max_failing_kpis", 2) or 2)
    alert = pass_rate < min_pass_rate or len(failing) > max_failing
    decision = "alert" if alert else "healthy"

    return {
        "ok": True,
        "decision": decision,
        "pass_rate_pct": round(pass_rate, 2),
        "instrumented_kpis": len(instrumented),
        "passing_kpis": len(passing),
        "failing_kpis": failing,
        "failing_kpis_count": len(failing),
        "thresholds": {
            "min_pass_rate_pct": min_pass_rate,
            "max_failing_kpis": max_failing,
        },
        "summary": summary,
        "report_path": report.get("path"),
    }


def _oem_recipients(db: Session, notify_admin: bool) -> List[str]:
    q = db.query(UserDB.username).filter(UserDB.role == "oem")
    rows = q.all()
    out = [str(r[0]) for r in rows if r and r[0]]
    if notify_admin:
        rows_admin = db.query(UserDB.username).filter(UserDB.role == "admin").all()
        for r in rows_admin:
            if r and r[0]:
                uid = str(r[0])
                if uid not in out:
                    out.append(uid)
    return out


def _compose_alert_message(health: Dict) -> str:
    failing = health.get("failing_kpis") or []
    if not failing:
        return (
            f"KPI pass rate is {health.get('pass_rate_pct')}%, "
            f"instrumented={health.get('instrumented_kpis')}, passing={health.get('passing_kpis')}."
        )
    top = [f"{x.get('stakeholder')}:{x.get('kpi')}={x.get('value')}" for x in failing[:3] if isinstance(x, dict)]
    return (
        f"KPI pass rate is {health.get('pass_rate_pct')}% with {health.get('failing_kpis_count')} failing KPI(s). "
        f"Top gaps: {'; '.join(top)}."
    )


def run_kpi_watchdog(db: Session, *, report_file: Optional[str] = None, notify: bool = True) -> Dict:
    policy = get_watchdog_policy()
    if not bool(policy.get("enabled", True)):
        return {"ok": True, "enabled": False, "decision": "disabled"}

    report = load_kpi_report(report_file=report_file or str(policy.get("report_file") or ""))
    health = evaluate_kpi_health(report, policy=policy)
    if not health.get("ok"):
        log_action("kpi_watchdog_error", str(health))
        return health

    log_action(
        "kpi_watchdog_scan",
        f"decision={health.get('decision')} pass_rate={health.get('pass_rate_pct')} "
        f"failing={health.get('failing_kpis_count')} report={health.get('report_path')}",
    )

    notified = 0
    if notify and bool(policy.get("notify_oem", True)):
        recipients = _oem_recipients(db, notify_admin=bool(policy.get("notify_admin", True)))
        if health.get("decision") == "alert":
            title = "KPI watchdog alert"
            msg = _compose_alert_message(health)
            sev = str(policy.get("severity_on_alert", "warning") or "warning")
            ntype = "kpi_watchdog_alert"
        else:
            title = "KPI watchdog healthy"
            msg = (
                f"KPI scorecard healthy: pass_rate={health.get('pass_rate_pct')}%, "
                f"failing={health.get('failing_kpis_count')}."
            )
            sev = "info"
            ntype = "kpi_watchdog_healthy"
        for user_id in recipients:
            try:
                created = create_oem_notification(
                    db=db,
                    user_id=user_id,
                    ntype=ntype,
                    title=title,
                    message=msg,
                    severity=sev,
                )
                if created:
                    notified += 1
            except Exception:
                continue

    return {
        "ok": True,
        "enabled": True,
        "decision": health.get("decision"),
        "pass_rate_pct": health.get("pass_rate_pct"),
        "failing_kpis_count": health.get("failing_kpis_count"),
        "instrumented_kpis": health.get("instrumented_kpis"),
        "passing_kpis": health.get("passing_kpis"),
        "report_path": health.get("report_path"),
        "notified": notified,
        "thresholds": health.get("thresholds", {}),
    }
