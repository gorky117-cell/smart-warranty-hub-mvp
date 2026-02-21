"""Phase 6 evaluator: service ticketing + parts mapping.

Pipeline under test:
  service.create_ticket -> storage.list_tickets

KPI focus:
- ticket creation success
- known-symptom parts mapping accuracy
- unknown-symptom handling (no false parts)
- evidence passthrough integrity
- draft status consistency
- retrieval completeness by warranty
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.abspath("."))


@dataclass
class CaseSpec:
    case_id: str
    user_id: str
    warranty_id: str
    symptom: str
    expected_parts: List[str]
    evidence: List[str]


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Phase 6 service ticket pipeline")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--out", default="data/service_phase6_eval_50.json")
    p.add_argument("--cases-out", default="test_data/service_phase6_cases_50.json")
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


def _build_cases(rows: int, mapping: Dict[str, List[str]]) -> List[CaseSpec]:
    known_symptoms = list(mapping.keys())
    unknown_symptoms = ["display_glitch", "wifi_drop", "random_restart", "slow_response"]
    known_rows = int(rows * 0.72)  # 36 of 50
    unknown_rows = rows - known_rows

    cases: List[CaseSpec] = []
    idx = 1
    for i in range(known_rows):
        symptom = known_symptoms[i % len(known_symptoms)]
        cid = f"SV{idx:03d}"
        cases.append(
            CaseSpec(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                symptom=symptom,
                expected_parts=list(mapping.get(symptom, [])),
                evidence=[f"log_{cid}.txt", f"photo_{cid}.jpg"],
            )
        )
        idx += 1
    for i in range(unknown_rows):
        symptom = unknown_symptoms[i % len(unknown_symptoms)]
        cid = f"SV{idx:03d}"
        cases.append(
            CaseSpec(
                case_id=cid,
                user_id=f"user_{cid.lower()}",
                warranty_id=f"wty_{cid.lower()}",
                symptom=symptom,
                expected_parts=[],
                evidence=[f"log_{cid}.txt"],
            )
        )
        idx += 1
    return cases


def main() -> int:
    args = _args()
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)

    from app.models import CanonicalWarranty
    from app.services.service import SYMPTOM_TO_PARTS, create_ticket
    from app.storage import store

    # Isolate in-memory state for deterministic run.
    store.tickets.clear()
    store.warranties.clear()

    cases = _build_cases(args.rows, SYMPTOM_TO_PARTS)
    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps([c.__dict__ for c in cases], indent=2), encoding="utf-8")

    latencies: List[float] = []
    case_rows: List[Dict] = []

    created_ok = 0
    known_total = 0
    known_map_ok = 0
    unknown_total = 0
    unknown_clean_ok = 0
    evidence_ok = 0
    draft_ok = 0
    retrieval_ok = 0

    for c in cases:
        # Seed a minimal warranty context (mirrors real flow dependency).
        store.warranties[c.warranty_id] = CanonicalWarranty(
            id=c.warranty_id,
            brand="LG",
            model_code=f"MOD-{c.case_id}",
            purchase_date=date.today() - timedelta(days=150),
            coverage_months=24,
            expiry_date=date.today() + timedelta(days=200),
        )

        t0 = time.perf_counter()
        tkt = create_ticket(
            user_id=c.user_id,
            warranty_id=c.warranty_id,
            symptom=c.symptom,
            evidence=list(c.evidence),
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed)

        create_success = bool(tkt and tkt.id and tkt.warranty_id == c.warranty_id)
        if create_success:
            created_ok += 1

        mapping_ok = list(tkt.recommended_parts) == list(c.expected_parts)
        if c.expected_parts:
            known_total += 1
            if mapping_ok:
                known_map_ok += 1
        else:
            unknown_total += 1
            if not tkt.recommended_parts:
                unknown_clean_ok += 1

        ev_ok = list(tkt.evidence) == list(c.evidence)
        if ev_ok:
            evidence_ok += 1

        st_ok = (tkt.status == "draft")
        if st_ok:
            draft_ok += 1

        listed = store.list_tickets(c.warranty_id)
        ret_ok = any(x.id == tkt.id for x in listed)
        if ret_ok:
            retrieval_ok += 1

        case_rows.append(
            {
                "case_id": c.case_id,
                "symptom": c.symptom,
                "expected_parts": c.expected_parts,
                "recommended_parts": list(tkt.recommended_parts),
                "create_success": create_success,
                "parts_mapping_ok": mapping_ok,
                "evidence_ok": ev_ok,
                "status_ok": st_ok,
                "retrieval_ok": ret_ok,
                "latency_ms": round(elapsed, 2),
            }
        )

    summary = {
        "dataset_rows": len(cases),
        "ticket_creation_success_pct": _pct(created_ok, len(cases)),
        "known_symptom_parts_accuracy_pct": _pct(known_map_ok, known_total),
        "unknown_symptom_no_false_parts_pct": _pct(unknown_clean_ok, unknown_total),
        "evidence_passthrough_pct": _pct(evidence_ok, len(cases)),
        "draft_status_consistency_pct": _pct(draft_ok, len(cases)),
        "ticket_retrieval_completeness_pct": _pct(retrieval_ok, len(cases)),
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
    }

    report = {
        "summary": summary,
        "symptom_mapping": SYMPTOM_TO_PARTS,
        "scenarios": {
            "known_symptoms": known_total,
            "unknown_symptoms": unknown_total,
        },
        "cases": case_rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 6 (Service Ticketing) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
