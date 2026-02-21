"""Phase 5 evaluator: NIP/advisories + nudge policy + event logging.

Pipeline under test:
  compute_risk -> assign_variant -> generate_nudges -> log_nudge_event/fetch_stats

Outputs:
  - data/nip_phase5_eval_50.json
  - test_data/nip_phase5_cases_50.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

# Configure path/env before app imports.
sys.path.insert(0, os.path.abspath("."))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 5 NIP/advisories")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/nip_phase5_eval.db")
    p.add_argument("--out", default="data/nip_phase5_eval_50.json")
    p.add_argument("--cases-out", default="test_data/nip_phase5_cases_50.json")
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
    profile: str  # low_stable | medium_attention | high_urgent
    expiry_bucket: str  # near | far
    expected_risk_band: str  # low | medium | high


def _build_cases(rows: int) -> List[CaseSpec]:
    # Keep fixed proportions for stable KPI.
    low = int(rows * 0.4)
    med = int(rows * 0.3)
    high = rows - low - med

    cases: List[CaseSpec] = []
    idx = 1

    def _add(n: int, profile: str, expected: str, near_ratio: float) -> None:
        nonlocal idx
        near_count = int(round(n * near_ratio))
        for i in range(n):
            cid = f"NIP{idx:03d}"
            expiry_bucket = "near" if i < near_count else "far"
            cases.append(
                CaseSpec(
                    case_id=cid,
                    user_id=f"user_{cid.lower()}",
                    warranty_id=f"wty_{cid.lower()}",
                    profile=profile,
                    expiry_bucket=expiry_bucket,
                    expected_risk_band=expected,
                )
            )
            idx += 1

    _add(low, "low_stable", "low", near_ratio=0.40)       # 8 near / 12 far
    _add(med, "medium_attention", "medium", near_ratio=0.53)  # 8 near / 7 far
    _add(high, "high_urgent", "high", near_ratio=0.67)     # 10 near / 5 far
    return cases


def _event_counts_for_profile(profile: str) -> Dict[str, int]:
    # Mirrors compute_risk inputs:
    # base 0.35 + dismisses(0.05 cap 0.25) - completions(0.03 cap 0.15) + issues(0.1 cap 0.3) -0.05 if expiry known
    if profile == "low_stable":
        return {"dismissed": 0, "completed": 2, "issues": 0}  # ~0.24 low
    if profile == "medium_attention":
        return {"dismissed": 3, "completed": 1, "issues": 1}  # ~0.52 medium
    return {"dismissed": 5, "completed": 0, "issues": 3}      # ~0.85 high


def _classify_nudge_type(title: str) -> str:
    t = (title or "").strip().lower()
    if "snapshot" in t or "quick view" in t:
        return "snapshot"
    if "care" in t or "do it now" in t:
        return "care"
    if "expiry" in t or "lose it" in t:
        return "expiry"
    if "all good" in t:
        return "all_good"
    return "other"


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.models import BehaviourEvent, CanonicalWarranty  # noqa: E402
    from app.services import policy  # noqa: E402
    from app.services.nudge import generate_nudges  # noqa: E402
    from app.services.nudges import fetch_stats, log_nudge_event  # noqa: E402
    from app.services.risk import compute_risk  # noqa: E402
    from app.storage import store  # noqa: E402

    Base.metadata.create_all(bind=engine)

    # Isolate in-memory state for deterministic run.
    store.warranties.clear()
    store.behaviour_events.clear()
    store.policy_assignments.clear()

    random.seed(42)
    cases = _build_cases(args.rows)
    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps([c.__dict__ for c in cases], indent=2), encoding="utf-8")

    latencies: List[float] = []
    case_rows: List[Dict] = []

    risk_label_ok = 0
    bundle_ok = 0
    care_expected = 0
    care_hit = 0
    care_false_positive = 0
    low_cases = 0
    expiry_expected = 0
    expiry_hit = 0
    expiry_false_positive = 0
    expiry_not_expected = 0
    variant_stable = 0
    event_integrity_ok = 0
    variant_counts: Dict[str, int] = {}

    for c in cases:
        expiry_days = 30 if c.expiry_bucket == "near" else 180
        warranty = CanonicalWarranty(
            id=c.warranty_id,
            product_name="appliance",
            brand="LG",
            model_code=f"MOD-{c.case_id}",
            serial_no=f"SN-{c.case_id}",
            purchase_date=date.today() - timedelta(days=200),
            coverage_months=24,
            expiry_date=date.today() + timedelta(days=expiry_days),
        )
        store.warranties[c.warranty_id] = warranty

        counts = _event_counts_for_profile(c.profile)
        for i in range(counts["dismissed"]):
            store.add_behaviour_event(
                BehaviourEvent(
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    event_type="nudge_dismissed",
                    details={"i": i},
                )
            )
        for i in range(counts["completed"]):
            store.add_behaviour_event(
                BehaviourEvent(
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    event_type="task_completed",
                    details={"i": i},
                )
            )
        for i in range(counts["issues"]):
            store.add_behaviour_event(
                BehaviourEvent(
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    event_type="issue_reported",
                    details={"i": i},
                )
            )

        t0 = time.perf_counter()
        risk = compute_risk(c.user_id, c.warranty_id)
        v1 = policy.assign_variant(c.user_id, c.warranty_id, experiment="fogg_nudge", variants=("A", "B"))
        v2 = policy.assign_variant(c.user_id, c.warranty_id, experiment="fogg_nudge", variants=("A", "B"))
        nudges = generate_nudges(risk, v1)
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed)

        variant_counts[v1] = variant_counts.get(v1, 0) + 1
        if v1 == v2:
            variant_stable += 1

        risk_match = risk.band == c.expected_risk_band
        if risk_match:
            risk_label_ok += 1

        if nudges:
            bundle_ok += 1

        nudge_types = [_classify_nudge_type(n.title) for n in nudges]
        has_care = "care" in nudge_types
        has_expiry = "expiry" in nudge_types

        if c.expected_risk_band in ("medium", "high"):
            care_expected += 1
            if has_care:
                care_hit += 1
        else:
            low_cases += 1
            if has_care:
                care_false_positive += 1

        if c.expiry_bucket == "near":
            expiry_expected += 1
            if has_expiry:
                expiry_hit += 1
        else:
            expiry_not_expected += 1
            if has_expiry:
                expiry_false_positive += 1

        # Log one acted and one ignored event per case.
        log_nudge_event(c.user_id, c.warranty_id, v1, "snapshot", acted=True)
        log_nudge_event(c.user_id, c.warranty_id, v1, "care", acted=False)
        with SessionLocal() as db:
            shown, acted, ignored = fetch_stats(db, c.user_id, c.warranty_id)
        event_ok = (shown == 2 and acted == 1 and ignored == 1)
        if event_ok:
            event_integrity_ok += 1

        case_rows.append(
            {
                "case_id": c.case_id,
                "profile": c.profile,
                "expiry_bucket": c.expiry_bucket,
                "expected_risk_band": c.expected_risk_band,
                "actual_risk_band": risk.band,
                "risk_value": risk.value,
                "variant_first": v1,
                "variant_second": v2,
                "variant_stable": v1 == v2,
                "nudge_count": len(nudges),
                "nudge_types": nudge_types,
                "care_present": has_care,
                "expiry_present": has_expiry,
                "event_integrity_ok": event_ok,
                "latency_ms": round(elapsed, 2),
            }
        )

    a = variant_counts.get("A", 0)
    b = variant_counts.get("B", 0)
    variant_balance_pct = _pct(min(a, b), max(a, b)) if max(a, b) > 0 else 0.0

    summary = {
        "dataset_rows": len(cases),
        "risk_band_accuracy_pct": _pct(risk_label_ok, len(cases)),
        "bundle_generation_success_pct": _pct(bundle_ok, len(cases)),
        "care_nudge_recall_pct": _pct(care_hit, care_expected),
        "care_nudge_false_positive_pct": _pct(care_false_positive, low_cases),
        "expiry_nudge_recall_pct": _pct(expiry_hit, expiry_expected),
        "expiry_nudge_false_positive_pct": _pct(expiry_false_positive, expiry_not_expected),
        "variant_stability_pct": _pct(variant_stable, len(cases)),
        "variant_a_count": a,
        "variant_b_count": b,
        "variant_balance_pct": variant_balance_pct,
        "nudge_event_integrity_pct": _pct(event_integrity_ok, len(cases)),
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
    }

    report = {
        "summary": summary,
        "scenarios": {
            "low_stable": len([c for c in cases if c.profile == "low_stable"]),
            "medium_attention": len([c for c in cases if c.profile == "medium_attention"]),
            "high_urgent": len([c for c in cases if c.profile == "high_urgent"]),
            "near_expiry": len([c for c in cases if c.expiry_bucket == "near"]),
            "far_expiry": len([c for c in cases if c.expiry_bucket == "far"]),
        },
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
        "cases": case_rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 5 (NIP Advisories) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
