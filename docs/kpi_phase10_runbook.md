# KPI Remediation Loop (Phase 10) Runbook

## Scope
- Pipeline block: closed-loop KPI operations after watchdog.
- Adds history persistence, trend detection, and remediation plan generation.
- Adds admin APIs and scheduler support for continuous KPI governance.

## What was added
- Service: `app/services/kpi_remediation.py`
- Scheduler hook: `app/services/scheduler.py`
- Admin APIs in `app/main.py`:
  - `GET /admin/kpi/history`
  - `GET /admin/kpi/remediation/latest`
  - `POST /admin/kpi/remediation/run`

## Saved artifacts
- KPI report: `data/kpi_phase10_eval_50.json`
- Synthetic cases: `test_data/kpi_phase10_cases_50.json`
- Isolated eval DB: `data/kpi_phase10_eval.db`
- Isolated report input: `data/kpi_phase10_report.json`
- Isolated policy file: `data/kpi_phase10_policy.json`
- Isolated history file: `data/kpi_phase10_history.json`
- Isolated remediation plan file: `data/kpi_phase10_plan.json`
- Evaluator script: `scripts/eval_kpi_phase10.py`

## Re-run
```bash
python scripts/eval_kpi_phase10.py --rows 50 --db data/kpi_phase10_eval.db --report-file data/kpi_phase10_report.json --policy-file data/kpi_phase10_policy.json --history-file data/kpi_phase10_history.json --plan-file data/kpi_phase10_plan.json --out data/kpi_phase10_eval_50.json --cases-out test_data/kpi_phase10_cases_50.json
```

## Current KPI (50 cases)
- Run1 decision: `alert` and remediation tasks: `3`
- Run2 decision: `alert` and alert streak: `2`
- Run3 decision: `healthy` and trend: `improving`
- History persistence rows: `3`
- Latest remediation plan task count: `1`
- Remediation notifications: `2`
- Decision accuracy: `100%`
- Runtime latency: `p50 111.29 ms`, `p95 261.94 ms`

## Scheduler knobs
- `KPI_REMEDIATION_ENABLED=true|false` (default `true`)
- `KPI_REMEDIATION_MINUTES` (default `1440`)
- `KPI_HISTORY_FILE` (default `data/kpi_history.json`)
- `KPI_REMEDIATION_PLAN_FILE` (default `data/kpi_remediation_latest.json`)
