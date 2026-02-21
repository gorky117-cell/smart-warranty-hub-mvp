"""Phase 4 evaluator: predictive risk + refresh notifications.

Purpose:
- Stress test predictive/risk pipeline on 50 synthetic realistic cases.
- Validate label quality, score separation, behaviour delta direction,
  latency, and risk-refresh notification behavior.

Design choice:
- Force deterministic fallback scoring path (model-independent) by stubbing
  predictive_model.predict -> (None, None, None). This validates pipeline
  wiring even when model artifacts vary across environments.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

# Important: configure DB before importing app.db.
sys.path.insert(0, os.path.abspath("."))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 4 predictive risk pipeline")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/predictive_phase4_eval.db")
    p.add_argument("--out", default="data/predictive_phase4_eval_50.json")
    p.add_argument("--cases-out", default="test_data/predictive_phase4_cases_50.json")
    return p.parse_args()


def _pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    pos = q * (len(v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    frac = pos - lo
    return v[lo] * (1.0 - frac) + v[hi] * frac


@dataclass
class CaseSpec:
    case_id: str
    user_id: str
    warranty_id: str
    expected_label: str
    scenario: str
    usage_events: int
    base_usage_hours: int
    last_usage_hours: int
    last_usage_errors: int
    error_events: int
    failure_events: int
    maintenance_events: int
    purchase_days_ago: int
    expiry_days_left: int


def _build_cases(rows: int) -> List[CaseSpec]:
    low_count = int(rows * 0.4)   # 20 of 50
    med_count = int(rows * 0.3)   # 15 of 50
    high_count = rows - low_count - med_count  # 15 of 50

    cases: List[CaseSpec] = []
    idx = 1

    for _ in range(low_count):
        cid = f"P{idx:03d}"
        cases.append(
            CaseSpec(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                expected_label="LOW",
                scenario="low_stable",
                usage_events=3,
                base_usage_hours=5,
                last_usage_hours=6,
                last_usage_errors=0,
                error_events=0,
                failure_events=0,
                maintenance_events=2,
                purchase_days_ago=120,
                expiry_days_left=180,
            )
        )
        idx += 1

    for _ in range(med_count):
        cid = f"P{idx:03d}"
        cases.append(
            CaseSpec(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                expected_label="MEDIUM",
                scenario="medium_warning",
                usage_events=4,
                base_usage_hours=5,
                last_usage_hours=20,
                last_usage_errors=1,
                error_events=1,
                failure_events=0,
                maintenance_events=0,
                purchase_days_ago=220,
                expiry_days_left=90,
            )
        )
        idx += 1

    for _ in range(high_count):
        cid = f"P{idx:03d}"
        cases.append(
            CaseSpec(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                expected_label="HIGH",
                scenario="high_risk",
                usage_events=8,
                base_usage_hours=10,
                last_usage_hours=620,
                last_usage_errors=4,
                error_events=3,
                failure_events=1,
                maintenance_events=0,
                purchase_days_ago=400,
                expiry_days_left=30,
            )
        )
        idx += 1

    return cases


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["RAG_ENABLED"] = "0"

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.db_models import BehaviourProfile, NotificationDB, WarrantyDB  # noqa: E402
    from app.models import CanonicalWarranty, TelemetryEvent  # noqa: E402
    from app.services import predictive, risk_refresh  # noqa: E402
    from app.storage import store  # noqa: E402

    Base.metadata.create_all(bind=engine)

    # Isolate in-memory state for this run.
    store.warranties.clear()
    store.telemetry.clear()
    store.behaviour_events.clear()

    # Deterministic fallback path: no trained model dependency.
    predictive.predictive_model.predict = lambda vec: (None, None, None)  # type: ignore[assignment]
    predictive.predictive_model.error = None
    predictive.predictive_model.model = None

    # Keep policy/issue deltas neutral for phase KPI stability.
    predictive.regional_policy_service.evaluate_region_policy = (  # type: ignore[assignment]
        lambda db, **kwargs: SimpleNamespace(risk_delta=0.0, reasons=[], min_coverage_months=None)
    )
    predictive.oem_issue_service.summarize_issue_signals = (  # type: ignore[assignment]
        lambda db, **kwargs: SimpleNamespace(risk_delta=0.0, reasons=[])
    )

    cases = _build_cases(args.rows)
    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(
        json.dumps([c.__dict__ for c in cases], indent=2),
        encoding="utf-8",
    )

    # Seed DB + store.
    with SessionLocal() as db:
        for c in cases:
            purchase_date = datetime.combine(
                date.today() - timedelta(days=c.purchase_days_ago), datetime.min.time()
            )
            expiry_date = datetime.combine(
                date.today() + timedelta(days=c.expiry_days_left), datetime.min.time()
            )

            # Store warranty (used by predictive feature vector).
            store.warranties[c.warranty_id] = CanonicalWarranty(
                id=c.warranty_id,
                product_name="appliance",
                brand="LG",
                model_code=f"MOD-{c.case_id}",
                serial_no=f"SN-{c.case_id}",
                purchase_date=purchase_date.date(),
                coverage_months=24,
                expiry_date=expiry_date.date(),
            )

            # DB warranty (used by score_warranty policy branch lookups).
            db.merge(
                WarrantyDB(
                    id=c.warranty_id,
                    product_name="appliance",
                    brand="LG",
                    model_code=f"MOD-{c.case_id}",
                    serial_no=f"SN-{c.case_id}",
                    purchase_date=purchase_date,
                    coverage_months=24,
                    expiry_date=expiry_date,
                    created_at=datetime.utcnow(),
                )
            )

            # BehaviourProfile pair is used by refresh_risk_snapshots distinct scan.
            db.add(
                BehaviourProfile(
                    user_id=c.user_id,
                    product_type="appliance",
                    warranty_id=c.warranty_id,
                    behaviour_score=0.5,
                    care_score=0.5,
                    responsiveness_score=0.5,
                    last_updated_at=datetime.utcnow(),
                )
            )
        db.commit()

    # Load telemetry through store path.
    event_counter = 0
    now = datetime.utcnow()
    for c in cases:
        usage_base_ts = now - timedelta(days=3)
        for i in range(c.usage_events):
            event_counter += 1
            hours = c.base_usage_hours
            usage_errors = 0
            if i == c.usage_events - 1:
                hours = c.last_usage_hours
                usage_errors = c.last_usage_errors
            store.add_telemetry(
                TelemetryEvent(
                    id=f"tev_{event_counter:06d}",
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    model_code=f"MOD-{c.case_id}",
                    region="IN",
                    timezone="Asia/Kolkata",
                    event_type="usage",
                    payload={"hours": hours, "errors": usage_errors},
                    timestamp=usage_base_ts + timedelta(minutes=i),
                )
            )
        for i in range(c.error_events):
            event_counter += 1
            store.add_telemetry(
                TelemetryEvent(
                    id=f"tev_{event_counter:06d}",
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    model_code=f"MOD-{c.case_id}",
                    region="IN",
                    timezone="Asia/Kolkata",
                    event_type="error",
                    payload={"code": "E101"},
                    timestamp=now - timedelta(days=2, minutes=i),
                )
            )
        for i in range(c.failure_events):
            event_counter += 1
            store.add_telemetry(
                TelemetryEvent(
                    id=f"tev_{event_counter:06d}",
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    model_code=f"MOD-{c.case_id}",
                    region="IN",
                    timezone="Asia/Kolkata",
                    event_type="failure",
                    payload={"reason": "motor_trip"},
                    timestamp=now - timedelta(days=1, minutes=i),
                )
            )
        for i in range(c.maintenance_events):
            event_counter += 1
            store.add_telemetry(
                TelemetryEvent(
                    id=f"tev_{event_counter:06d}",
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    model_code=f"MOD-{c.case_id}",
                    region="IN",
                    timezone="Asia/Kolkata",
                    event_type="maintenance",
                    payload={"kind": "cleaning"},
                    timestamp=now - timedelta(days=1, minutes=30 + i),
                )
            )

    # Score and capture KPIs.
    lat_ms: List[float] = []
    label_ok = 0
    delta_ok = 0
    by_expected_scores: Dict[str, List[float]] = defaultdict(list)
    case_rows: List[Dict] = []

    for c in cases:
        t0 = time.perf_counter()
        scored = predictive.score_warranty(c.user_id, c.warranty_id)
        elapsed = (time.perf_counter() - t0) * 1000.0
        lat_ms.append(elapsed)

        got_label = str(scored.get("risk_label", "UNKNOWN")).upper()
        got_score = float(scored.get("risk_score", 0.0) or 0.0)
        got_delta = float(scored.get("behaviour_delta", 0.0) or 0.0)
        label_match = got_label == c.expected_label
        if label_match:
            label_ok += 1

        expected_delta_positive = c.expected_label in ("MEDIUM", "HIGH")
        delta_match = (got_delta > 0) if expected_delta_positive else (got_delta <= 0)
        if delta_match:
            delta_ok += 1

        by_expected_scores[c.expected_label].append(got_score)

        case_rows.append(
            {
                "case_id": c.case_id,
                "scenario": c.scenario,
                "expected_label": c.expected_label,
                "predicted_label": got_label,
                "risk_score": round(got_score, 3),
                "behaviour_delta": round(got_delta, 3),
                "label_match": label_match,
                "delta_direction_match": delta_match,
                "latency_ms": round(elapsed, 2),
            }
        )

    avg_low = sum(by_expected_scores["LOW"]) / max(1, len(by_expected_scores["LOW"]))
    avg_med = sum(by_expected_scores["MEDIUM"]) / max(1, len(by_expected_scores["MEDIUM"]))
    avg_high = sum(by_expected_scores["HIGH"]) / max(1, len(by_expected_scores["HIGH"]))
    monotonic_ok = bool(avg_high > avg_med > avg_low)

    # Refresh-risk notification behavior check.
    with SessionLocal() as db:
        first_refresh_count = risk_refresh.refresh_risk_snapshots(db)
        notif_first = db.query(NotificationDB).filter(NotificationDB.type.like("risk_%")).count()

    # Push first 5 LOW cases into HIGH via extra telemetry.
    changed_cases = [c for c in cases if c.expected_label == "LOW"][:5]
    for c in changed_cases:
        event_counter += 1
        store.add_telemetry(
            TelemetryEvent(
                id=f"tev_{event_counter:06d}",
                user_id=c.user_id,
                warranty_id=c.warranty_id,
                model_code=f"MOD-{c.case_id}",
                region="IN",
                timezone="Asia/Kolkata",
                event_type="usage",
                payload={"hours": 700, "errors": 4},
                timestamp=datetime.utcnow(),
            )
        )
        for _ in range(2):
            event_counter += 1
            store.add_telemetry(
                TelemetryEvent(
                    id=f"tev_{event_counter:06d}",
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    model_code=f"MOD-{c.case_id}",
                    region="IN",
                    timezone="Asia/Kolkata",
                    event_type="failure",
                    payload={"reason": "compressor_fail"},
                    timestamp=datetime.utcnow(),
                )
            )

    with SessionLocal() as db:
        notif_before_second = db.query(NotificationDB).filter(NotificationDB.type.like("risk_%")).count()
        second_refresh_count = risk_refresh.refresh_risk_snapshots(db)
        notif_after_second = db.query(NotificationDB).filter(NotificationDB.type.like("risk_%")).count()

        changed_notified = 0
        for c in changed_cases:
            cnt = (
                db.query(NotificationDB)
                .filter_by(user_id=c.user_id, warranty_id=c.warranty_id)
                .filter(NotificationDB.type.like("risk_%"))
                .count()
            )
            # One notification from first refresh + at least one new one after change.
            if cnt >= 2:
                changed_notified += 1

    summary = {
        "dataset_rows": len(cases),
        "label_accuracy_pct": _pct(label_ok, len(cases)),
        "behaviour_delta_direction_accuracy_pct": _pct(delta_ok, len(cases)),
        "avg_score_low": round(avg_low, 3),
        "avg_score_medium": round(avg_med, 3),
        "avg_score_high": round(avg_high, 3),
        "score_monotonicity_ok": monotonic_ok,
        "latency_p50_ms": round(_percentile(lat_ms, 0.50), 2),
        "latency_p95_ms": round(_percentile(lat_ms, 0.95), 2),
        "risk_refresh_first_scored": int(first_refresh_count),
        "risk_refresh_second_scored": int(second_refresh_count),
        "risk_notifications_first_total": int(notif_first),
        "risk_notifications_second_new": int(notif_after_second - notif_before_second),
        "changed_case_notification_recall_pct": _pct(changed_notified, len(changed_cases)),
    }

    report = {
        "summary": summary,
        "scenarios": {
            "low_stable": len([c for c in cases if c.expected_label == "LOW"]),
            "medium_warning": len([c for c in cases if c.expected_label == "MEDIUM"]),
            "high_risk": len([c for c in cases if c.expected_label == "HIGH"]),
        },
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
        "cases": case_rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 4 (Predictive Risk) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
