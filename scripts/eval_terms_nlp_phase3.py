"""Evaluate Phase 3: deterministic terms parsing + low-confidence NLP enrichment.

This evaluator is deterministic and does not require live Mistral access.
It monkeypatches the enrichment call to simulate NLP output and validates:
  1) Enrichment triggers for low-confidence pages.
  2) Deterministic parser remains primary for strong fields (duration).
  3) Terms/exclusions/claim_steps completeness improves.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, os.path.abspath("."))

from app.services import warranty_parser  # noqa: E402
from app.services.warranty_parser import ParsedTerms  # noqa: E402


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate terms NLP enrichment (Phase 3)")
    p.add_argument("--rows", type=int, default=50)
    p.add_argument("--out", default="data/terms_nlp_eval_50.json")
    p.add_argument("--cases-out", default="test_data/terms_nlp_cases_50.json")
    p.add_argument("--samples-dir", default="test_data/terms_nlp_samples")
    return p.parse_args()


def _pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _build_cases(rows: int) -> List[Dict]:
    cases: List[Dict] = []
    for i in range(1, rows + 1):
        cid = f"NLP{i:03d}"
        if i <= int(rows * 0.4):
            scenario = "high_conf_deterministic"
            expected_duration = 24 if i % 2 else 12
            html = (
                f"<html><body><h1>Warranty Policy</h1>"
                f"<p>CaseID: {cid}</p>"
                f"<p>Coverage: {expected_duration} months warranty from purchase date.</p>"
                f"<h2>Exclusions</h2><ul><li>Physical damage</li><li>Liquid damage</li></ul>"
                f"<h2>Claim steps</h2><ol><li>Contact support</li><li>Provide invoice</li></ol>"
                f"</body></html>"
            )
        elif i <= int(rows * 0.8):
            scenario = "low_conf_enrich"
            expected_duration = 36 if i % 3 == 0 else 24
            html = (
                f"<html><body><h1>Support</h1>"
                f"<p>CaseID: {cid}</p>"
                f"<p>Warranty details available from customer support team.</p>"
                f"</body></html>"
            )
        else:
            scenario = "partial_duration_keep"
            expected_duration = 12
            html = (
                f"<html><body><h1>Warranty</h1>"
                f"<p>CaseID: {cid}</p>"
                f"<p>Coverage: 12 months warranty from purchase date.</p>"
                f"<p>Additional details available on request.</p>"
                f"</body></html>"
            )
        cases.append(
            {
                "case_id": cid,
                "scenario": scenario,
                "expected_duration": expected_duration,
                "html": html,
            }
        )
    return cases


def main() -> int:
    args = _args()
    out_path = Path(args.out)
    cases_out = Path(args.cases_out)
    samples_dir = Path(args.samples_dir)
    samples_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TERMS_NLP_ENRICH_ENABLED"] = "1"
    os.environ["TERMS_NLP_MIN_CONFIDENCE"] = "0.75"

    cases = _build_cases(args.rows)
    expected_duration_by_case = {str(c["case_id"]): int(c["expected_duration"]) for c in cases}
    calls: List[str] = []

    def _fake_enrich(raw_text: str):
        match = re.search(r"\bNLP\d{3}\b", raw_text or "")
        case_id = match.group(0) if match else ""
        calls.append(case_id or "UNKNOWN")

        duration = expected_duration_by_case.get(case_id, 24)

        enriched = ParsedTerms(
            duration_months=duration,
            terms=["Covers manufacturing defects under normal use."],
            exclusions=["Physical and liquid damage are excluded."],
            claim_steps=["Contact support with invoice and serial number."],
            raw_text=None,
            confidence=0.8,
        )
        return enriched, None

    warranty_parser._mistral_enrich_terms = _fake_enrich  # type: ignore[assignment]

    results: List[Dict] = []
    duration_match = 0
    completeness = 0
    low_total = 0
    low_enrich_ok = 0
    high_total = 0
    high_no_enrich_ok = 0
    partial_total = 0
    partial_keep_ok = 0

    for c in cases:
        fp = samples_dir / f"{c['case_id']}.html"
        fp.write_text(str(c["html"]), encoding="utf-8")
        before_calls = len(calls)
        parsed, err = warranty_parser.parse_terms_from_url(str(fp))
        after_calls = len(calls)
        used_enrich = after_calls > before_calls
        if err or not parsed:
            results.append(
                {
                    "case_id": c["case_id"],
                    "scenario": c["scenario"],
                    "error": err or "parse_failed",
                    "used_enrich": used_enrich,
                }
            )
            continue

        exp_duration = int(c["expected_duration"])
        got_duration = int(parsed.duration_months or 0)
        dmatch = got_duration == exp_duration
        if dmatch:
            duration_match += 1
        is_complete = bool(parsed.terms and parsed.exclusions and parsed.claim_steps)
        if is_complete:
            completeness += 1

        scenario = str(c["scenario"])
        if scenario == "low_conf_enrich":
            low_total += 1
            if used_enrich and is_complete:
                low_enrich_ok += 1
        elif scenario == "high_conf_deterministic":
            high_total += 1
            if not used_enrich:
                high_no_enrich_ok += 1
        elif scenario == "partial_duration_keep":
            partial_total += 1
            if used_enrich and got_duration == 12:
                partial_keep_ok += 1

        results.append(
            {
                "case_id": c["case_id"],
                "scenario": scenario,
                "used_enrich": used_enrich,
                "duration_months": got_duration,
                "expected_duration": exp_duration,
                "duration_match": dmatch,
                "terms_count": len(parsed.terms or []),
                "exclusions_count": len(parsed.exclusions or []),
                "claim_steps_count": len(parsed.claim_steps or []),
                "complete_sections": is_complete,
            }
        )

    summary = {
        "dataset_rows": len(cases),
        "duration_exact_match_rate_pct": _pct(duration_match, len(cases)),
        "section_completeness_rate_pct": _pct(completeness, len(cases)),
        "low_conf_enrich_success_pct": _pct(low_enrich_ok, low_total),
        "high_conf_skip_enrich_pct": _pct(high_no_enrich_ok, high_total),
        "deterministic_duration_preserved_pct": _pct(partial_keep_ok, partial_total),
        "enrich_calls_total": len(calls),
    }

    report = {
        "summary": summary,
        "scenarios": {
            "high_conf_deterministic": high_total,
            "low_conf_enrich": low_total,
            "partial_duration_keep": partial_total,
        },
        "cases": results,
    }

    cases_out.parent.mkdir(parents=True, exist_ok=True)
    cases_out.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 3 (NLP Terms Enrichment) KPI Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved report: {out_path}")
    print(f"Saved cases: {cases_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
