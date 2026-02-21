# KPI Automation (Phase 8) Runbook

## Scope
- Pipeline block: KPI scorecard automation across user, OEM, and platform metrics.
- Includes A/B balance check, calibration/drift monitoring, and CSV export for monthly review.

## Saved artifacts
- KPI report: `data/kpi_phase8_eval_50.json`
- KPI scorecard CSV: `data/kpi_phase8_scorecard_50.csv`
- Synthetic cases: `test_data/kpi_phase8_cases_50.json`
- Isolated eval DB: `data/kpi_phase8_eval.db`
- Evaluator script: `scripts/eval_kpi_phase8.py`

## Re-run
```bash
python scripts/eval_kpi_phase8.py --rows 50 --db data/kpi_phase8_eval.db --out data/kpi_phase8_eval_50.json --scorecard-csv data/kpi_phase8_scorecard_50.csv --cases-out test_data/kpi_phase8_cases_50.json
```

## Current KPI (50 cases)
- Instrumented KPI pass rate: `100%` (`10/10`)
- Failure prevention rate: `26.67%`
- Alert usefulness rate: `40.0%`
- False alert rate: `6.67%`
- OEM high-risk precision: `60.0%`
- OEM early warning lead time (median): `21.0 days`
- Data freshness SLA: `98.0%`
- Calibration ECE: `0.1162`
- Brier score: `0.1896`
- Drift PSI: `0.1169` (stable)
- A/B variant split (phase8_kpi_ab): `A=15`, `B=15` (gap `0`)

## Simple meaning
- KPI automation and monthly export are now wired and repeatable.
- A/B balancing is healthy in the current run.
- Data freshness, user-facing advisory KPIs, and model quality KPIs are all within target in this benchmark run.
