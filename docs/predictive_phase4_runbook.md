# Predictive Risk (Phase 4) KPI Runbook

## Scope
- Pipeline block: behavioural monitor + predictive risk engine + risk refresh notifications.
- Goal: verify scoring quality and downstream notification wiring under stress.

## Saved artifacts
- KPI report: `data/predictive_phase4_eval_50.json`
- Synthetic cases: `test_data/predictive_phase4_cases_50.json`
- Isolated eval DB: `data/predictive_phase4_eval.db`
- Evaluator script: `scripts/eval_predictive_phase4.py`

## Re-run
```bash
python scripts/eval_predictive_phase4.py --rows 50 --db data/predictive_phase4_eval.db --out data/predictive_phase4_eval_50.json --cases-out test_data/predictive_phase4_cases_50.json
```

## Current KPI (50 cases)
- Label accuracy: `100%`
- Behaviour delta direction accuracy: `100%`
- Score separation:
  - LOW avg: `0.00`
  - MEDIUM avg: `0.43`
  - HIGH avg: `1.00`
- Monotonic order check: `true` (`HIGH > MEDIUM > LOW`)
- Latency: `p50 4.64 ms`, `p95 8.93 ms`
- Risk refresh run-1 scored: `50`
- Risk refresh run-2 scored: `50`
- New notifications after forced label-change: `5`
- Label-change notification recall: `100%`

## Simple meaning
- Risk scoring now cleanly separates low/medium/high synthetic usage patterns.
- Behaviour delta is moving in the expected direction.
- Scheduled risk refresh is correctly generating notifications when labels change.
