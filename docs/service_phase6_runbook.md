# Service Ticketing (Phase 6) KPI Runbook

## Scope
- Pipeline block: service ticket creation + symptom-to-parts mapping + evidence capture.

## Saved artifacts
- KPI report: `data/service_phase6_eval_50.json`
- Synthetic cases: `test_data/service_phase6_cases_50.json`
- Evaluator script: `scripts/eval_service_phase6.py`

## Re-run
```bash
python scripts/eval_service_phase6.py --rows 50 --out data/service_phase6_eval_50.json --cases-out test_data/service_phase6_cases_50.json
```

## Current KPI (50 cases)
- Ticket creation success: `100%`
- Known-symptom parts accuracy: `100%`
- Unknown-symptom no-false-parts: `100%`
- Evidence passthrough: `100%`
- Draft-status consistency: `100%`
- Ticket retrieval completeness: `100%`
- Latency: `p50 0.01 ms`, `p95 0.03 ms`

## Simple meaning
- Ticketing flow is stable.
- Known symptoms map to correct parts.
- Unknown symptoms do not get wrong part suggestions.
- Evidence is retained exactly as submitted.
