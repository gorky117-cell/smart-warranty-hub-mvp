"""Phase 7 evaluator: OEM analysis + monthly dispatch pipeline.

Scenarios covered in one run:
1) Strong signal dispatch (send path)
2) Immediate rerun to validate recipient rate-limit blocking
3) Dry-run behavior (eligible computed, no sends)
4) Insufficient-signal behavior with OEM summary notification
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.abspath("."))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 7 OEM dispatch pipeline")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--db", default="data/oem_phase7_eval.db")
    p.add_argument("--policy-file", default="data/oem_dispatch_policy_phase7_eval.json")
    p.add_argument("--out", default="data/oem_phase7_eval_50.json")
    p.add_argument("--cases-out", default="test_data/oem_phase7_cases_50.json")
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


@dataclass
class DispatchCase:
    case_id: str
    user_id: str
    warranty_id: str
    brand: str
    model_code: str
    region: str


def _build_cases(rows: int) -> List[DispatchCase]:
    out: List[DispatchCase] = []
    brands = ["Samsung", "LG", "Sony", "Apple"]
    regions = ["IN", "US", "EU", "IN"]
    for i in range(1, rows + 1):
        cid = f"OEM{i:03d}"
        brand = brands[(i - 1) % len(brands)]
        model = f"{brand[:2].upper()}-M{(i - 1) % 5}"
        region = regions[(i - 1) % len(regions)]
        out.append(
            DispatchCase(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                brand=brand,
                model_code=model,
                region=region,
            )
        )
    return out


def main() -> int:
    args = _args()
    db_path = Path(args.db)
    policy_path = Path(args.policy_file)
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    if policy_path.exists():
        policy_path.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["OEM_DISPATCH_POLICY_FILE"] = str(policy_path).replace("\\", "/")

    from app.db import Base, SessionLocal, engine  # noqa: E402
    import app.db_models as _db_models  # noqa: F401, E402
    from app.db_models import (
        BehaviourProfile,
        NotificationDB,
        OemIssueSignalDB,
        OemCommunicationTraceDB,
        UserDB,
        WarrantyDB,
    )  # noqa: E402
    from app.deps import hash_password  # noqa: E402
    from app.services import oem_dispatch  # noqa: E402

    Base.metadata.create_all(bind=engine)

    cases = _build_cases(args.rows)
    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps([c.__dict__ for c in cases], indent=2), encoding="utf-8")

    sender_user = "oem_sender_phase7"

    with SessionLocal() as db:
        # sender and recipient users
        db.merge(
            UserDB(
                username=sender_user,
                role="oem",
                hashed_password=hash_password("pass123"),
                email=f"{sender_user}@example.com",
                consent_analytics=1,
            )
        )
        for c in cases:
            db.merge(
                UserDB(
                    username=c.user_id,
                    role="user",
                    hashed_password=hash_password("pass123"),
                    email=f"{c.user_id}@example.com",
                    consent_analytics=1,
                )
            )
            db.merge(
                WarrantyDB(
                    id=c.warranty_id,
                    product_name="Device",
                    brand=c.brand,
                    model_code=c.model_code,
                    region_code=c.region,
                    coverage_months=12,
                    created_at=datetime.utcnow(),
                )
            )
            db.add(
                BehaviourProfile(
                    user_id=c.user_id,
                    warranty_id=c.warranty_id,
                    product_type="device",
                    behaviour_score=0.65,
                    care_score=0.60,
                    responsiveness_score=0.62,
                    last_updated_at=datetime.utcnow(),
                )
            )
        db.commit()

        # issue signals for all brand/model combos in dataset
        seen = set((c.brand, c.model_code, c.region) for c in cases)
        for brand, model, region in seen:
            db.add(
                OemIssueSignalDB(
                    brand=brand,
                    model_code=model,
                    product_type="device",
                    region=region,
                    issue_type="reliability_notice",
                    severity=0.85,
                    count=2,
                    source_url=f"https://www.{brand.lower()}.com/support",
                    created_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
            )
        db.commit()

        # Common dispatch policy for strong-signal scenarios.
        base_policy = {
            "enabled": True,
            "allowed_kinds": ["important_update"],
            "send_product_recommendations": False,
            "max_targets_per_run": max(1, args.rows),
            "min_eligible_for_send": 2,
            "min_issue_count": 1,
            "min_issue_severity": 0.5,
            "issue_lookback_days": 90,
            "notify_oem_when_no_signal": True,
            "notify_oem_summary": True,
            "sender_user_id": sender_user,
            "sender_role": "oem",
        }
        oem_dispatch.set_dispatch_policy(base_policy)

        latencies: List[float] = []

        t0 = time.perf_counter()
        run1 = oem_dispatch.run_weekly_dispatch(db, dry_run=False)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        run2 = oem_dispatch.run_weekly_dispatch(db, dry_run=False)  # should mostly block by rate-limit
        latencies.append((time.perf_counter() - t0) * 1000.0)

        t0 = time.perf_counter()
        run3 = oem_dispatch.run_weekly_dispatch(db, dry_run=True)  # no send in dry-run
        latencies.append((time.perf_counter() - t0) * 1000.0)

        # Force insufficient signal.
        oem_dispatch.set_dispatch_policy(
            {
                **base_policy,
                "min_issue_count": 999,
                "min_eligible_for_send": 2,
                "notify_oem_when_no_signal": True,
                "notify_oem_summary": False,
            }
        )
        t0 = time.perf_counter()
        run4 = oem_dispatch.run_weekly_dispatch(db, dry_run=False)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        sent_total = db.query(OemCommunicationTraceDB).filter_by(decision="sent").count()
        blocked_total = db.query(OemCommunicationTraceDB).filter_by(decision="blocked").count()
        oem_dispatch_notifs = (
            db.query(NotificationDB)
            .filter(NotificationDB.type == "oem_dispatch_summary")
            .count()
        )

    # KPI calculations
    run1_eligible = int(run1.get("eligible", 0) or 0)
    run1_sent = int(run1.get("sent", 0) or 0)
    run2_eligible = int(run2.get("eligible", 0) or 0)
    run2_blocked = int(run2.get("blocked", 0) or 0)

    summary = {
        "dataset_rows": len(cases),
        "run1_decision": run1.get("decision"),
        "run1_send_rate_pct": _pct(run1_sent, run1_eligible),
        "run1_trace_integrity_ok": (run1_sent + int(run1.get("blocked", 0) or 0)) == run1_eligible,
        "run2_decision": run2.get("decision"),
        "run2_rate_limit_block_pct": _pct(run2_blocked, run2_eligible),
        "run2_trace_integrity_ok": (int(run2.get("sent", 0) or 0) + run2_blocked) == run2_eligible,
        "run3_decision": run3.get("decision"),
        "run3_sent_zero_ok": int(run3.get("sent", 0) or 0) == 0,
        "run4_decision": run4.get("decision"),
        "run4_oem_notified": int(run4.get("oem_notified", 0) or 0),
        "run4_insufficient_signal_notify_ok": (run4.get("decision") == "insufficient_signal" and int(run4.get("oem_notified", 0) or 0) >= 1),
        "total_trace_sent": sent_total,
        "total_trace_blocked": blocked_total,
        "total_oem_dispatch_notifications": oem_dispatch_notifs,
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
    }

    report = {
        "summary": summary,
        "runs": {
            "run1_strong_signal": run1,
            "run2_rate_limit": run2,
            "run3_dry_run": run3,
            "run4_insufficient_signal": run4,
        },
        "artifacts": {
            "db_file": str(db_path).replace("\\", "/"),
            "policy_file": str(policy_path).replace("\\", "/"),
            "cases_file": str(cases_out).replace("\\", "/"),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 7 (OEM Dispatch) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
