from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..db_models import UserDB
from .audit import log_action
from .notifications import create_oem_notification
from . import kpi_watchdog


def _history_path() -> Path:
    return Path(os.getenv("KPI_HISTORY_FILE", "data/kpi_history.json"))


def _latest_plan_path() -> Path:
    return Path(os.getenv("KPI_REMEDIATION_PLAN_FILE", "data/kpi_remediation_latest.json"))


def _load_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return fallback


def _write_json_file(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_history(limit: int = 30) -> List[Dict]:
    data = _load_json_file(_history_path(), [])
    if not isinstance(data, list):
        return []
    rows = [x for x in data if isinstance(x, dict)]
    rows.sort(key=lambda x: str(x.get("timestamp", "")))
    if limit > 0:
        rows = rows[-limit:]
    return rows


def append_snapshot(*, health: Dict, report_path: Optional[str], source: str = "manual") -> Dict:
    now = datetime.utcnow().isoformat()
    failing = [x for x in (health.get("failing_kpis") or []) if isinstance(x, dict)]
    rec = {
        "timestamp": now,
        "source": source,
        "decision": health.get("decision", "unknown"),
        "pass_rate_pct": float(health.get("pass_rate_pct", 0.0) or 0.0),
        "failing_kpis_count": int(health.get("failing_kpis_count", 0) or 0),
        "instrumented_kpis": int(health.get("instrumented_kpis", 0) or 0),
        "passing_kpis": int(health.get("passing_kpis", 0) or 0),
        "report_path": report_path,
        "failing_kpis": [
            {
                "stakeholder": str(x.get("stakeholder") or ""),
                "kpi": str(x.get("kpi") or ""),
                "value": x.get("value"),
                "target": x.get("target"),
                "status": x.get("status"),
            }
            for x in failing
        ],
    }
    history = get_history(limit=0)
    history.append(rec)
    _write_json_file(_history_path(), history)
    return rec


def _compute_alert_streak(history: List[Dict]) -> int:
    streak = 0
    for rec in reversed(history):
        if str(rec.get("decision")) == "alert":
            streak += 1
        else:
            break
    return streak


def compute_trend(history: List[Dict], window: int = 7) -> Dict:
    if not history:
        return {
            "window": window,
            "trend": "stable",
            "latest_pass_rate_pct": 0.0,
            "pass_rate_delta_pct": 0.0,
            "alert_streak": 0,
            "recurring_failing_kpis": [],
        }
    rows = history[-max(2, int(window)) :]
    latest = float(rows[-1].get("pass_rate_pct", 0.0) or 0.0)
    prior = rows[:-1]
    prior_avg = sum(float(x.get("pass_rate_pct", 0.0) or 0.0) for x in prior) / max(1, len(prior))
    delta = latest - prior_avg
    trend = "stable"
    if delta >= 2.0:
        trend = "improving"
    elif delta <= -2.0:
        trend = "worsening"

    counts: Dict[str, int] = {}
    for rec in rows:
        for k in rec.get("failing_kpis") or []:
            if not isinstance(k, dict):
                continue
            key = f"{str(k.get('stakeholder') or 'Unknown')}::{str(k.get('kpi') or 'Unknown')}"
            counts[key] = counts.get(key, 0) + 1
    recurring = [
        {"kpi_key": k, "occurrences": v}
        for k, v in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if v >= 2
    ][:5]

    return {
        "window": len(rows),
        "trend": trend,
        "latest_pass_rate_pct": round(latest, 2),
        "pass_rate_delta_pct": round(delta, 2),
        "alert_streak": _compute_alert_streak(history),
        "recurring_failing_kpis": recurring,
    }


def _action_template(kpi_name: str, stakeholder: str) -> Dict:
    name = (kpi_name or "").lower()
    if "precision" in name:
        return {"owner": "Data Science", "eta_days": 10, "action": "Retune high-risk threshold and retrain with latest labeled outcomes."}
    if "calibration" in name or "brier" in name:
        return {"owner": "ML Platform", "eta_days": 7, "action": "Apply probability calibration and monitor ECE/Brier per segment."}
    if "freshness" in name:
        return {"owner": "Data Engineering", "eta_days": 5, "action": "Tighten ingestion SLA and add lag alert for delayed telemetry jobs."}
    if "false alert" in name:
        return {"owner": "ML Platform", "eta_days": 7, "action": "Increase supporting-signal threshold before HIGH-risk alerting."}
    if "failure prevention" in name or "usefulness" in name:
        return {"owner": "Product", "eta_days": 14, "action": "Tune nudge policy and copy for higher action completion."}
    if "lead time" in name:
        return {"owner": "OEM Analytics", "eta_days": 10, "action": "Increase issue-feed cadence and expand early-warning signals."}
    owner = "Operations" if (stakeholder or "").lower() in ("oem", "tpa", "supplier") else "Platform"
    return {"owner": owner, "eta_days": 10, "action": "Run root-cause review and implement targeted corrective experiment."}


def generate_remediation_plan(health: Dict, trend: Dict) -> Dict:
    failing = [x for x in (health.get("failing_kpis") or []) if isinstance(x, dict)]
    tasks: List[Dict] = []
    is_alert = str(health.get("decision")) == "alert"
    alert_streak = int(trend.get("alert_streak", 0) or 0)

    for i, kpi in enumerate(failing, start=1):
        kpi_name = str(kpi.get("kpi") or "Unknown KPI")
        stakeholder = str(kpi.get("stakeholder") or "Unknown")
        tpl = _action_template(kpi_name, stakeholder)
        priority = "high" if is_alert or alert_streak >= 2 else "medium"
        if alert_streak >= 3:
            priority = "critical"
        tasks.append(
            {
                "id": f"T{i:02d}",
                "stakeholder": stakeholder,
                "kpi": kpi_name,
                "current_value": kpi.get("value"),
                "target": kpi.get("target"),
                "priority": priority,
                "owner": tpl["owner"],
                "eta_days": tpl["eta_days"],
                "action": tpl["action"],
            }
        )

    summary = (
        f"KPI trend={trend.get('trend')}, pass_rate={health.get('pass_rate_pct')}%, "
        f"failing={health.get('failing_kpis_count')}, alert_streak={alert_streak}."
    )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "decision": health.get("decision"),
        "summary": summary,
        "trend": trend,
        "tasks": tasks,
        "task_count": len(tasks),
    }


def save_latest_plan(plan: Dict) -> Dict:
    _write_json_file(_latest_plan_path(), plan)
    return plan


def load_latest_plan() -> Dict:
    data = _load_json_file(_latest_plan_path(), {})
    if isinstance(data, dict):
        return data
    return {}


def _recipients(db: Session, include_admin: bool = True) -> List[str]:
    out: List[str] = []
    for row in db.query(UserDB.username).filter(UserDB.role == "oem").all():
        if row and row[0]:
            out.append(str(row[0]))
    if include_admin:
        for row in db.query(UserDB.username).filter(UserDB.role == "admin").all():
            if row and row[0]:
                uid = str(row[0])
                if uid not in out:
                    out.append(uid)
    return out


def run_kpi_remediation_cycle(
    db: Session,
    *,
    report_file: Optional[str] = None,
    notify: bool = True,
    source: str = "manual",
) -> Dict:
    report = kpi_watchdog.load_kpi_report(report_file=report_file)
    health = kpi_watchdog.evaluate_kpi_health(report)
    if not health.get("ok"):
        log_action("kpi_remediation_error", str(health))
        return {"ok": False, "decision": "error", "detail": health}

    snapshot = append_snapshot(
        health=health,
        report_path=health.get("report_path"),
        source=source,
    )
    history = get_history(limit=180)
    trend = compute_trend(history, window=14)
    plan = generate_remediation_plan(health, trend)
    save_latest_plan(plan)

    notified = 0
    if notify and str(health.get("decision")) == "alert" and int(plan.get("task_count", 0)) > 0:
        msg = str(plan.get("summary") or "")
        for user_id in _recipients(db, include_admin=True):
            try:
                created = create_oem_notification(
                    db=db,
                    user_id=user_id,
                    ntype="kpi_remediation_plan",
                    title="KPI remediation plan generated",
                    message=msg,
                    severity="warning",
                )
                if created:
                    notified += 1
            except Exception:
                continue

    log_action(
        "kpi_remediation_cycle",
        f"decision={health.get('decision')} tasks={plan.get('task_count')} trend={trend.get('trend')} notified={notified}",
    )
    return {
        "ok": True,
        "decision": health.get("decision"),
        "pass_rate_pct": health.get("pass_rate_pct"),
        "failing_kpis_count": health.get("failing_kpis_count"),
        "trend": trend,
        "snapshot": snapshot,
        "task_count": plan.get("task_count", 0),
        "plan_path": str(_latest_plan_path()).replace("\\", "/"),
        "history_path": str(_history_path()).replace("\\", "/"),
        "notified": notified,
    }
