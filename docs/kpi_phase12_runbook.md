# KPI Execution Tracking (Phase 12) Runbook

## Scope
- Pipeline block: execution tracking for remediation tasks.
- Adds task board sync, status lifecycle management, overdue alerting, and closure metrics.

## What was added
- Service: `app/services/kpi_execution.py`
- Scheduler hook: `app/services/scheduler.py`
- Admin APIs in `app/main.py`:
  - `GET /admin/kpi/tasks`
  - `POST /admin/kpi/tasks/{task_key}`
  - `GET /admin/kpi/execution/metrics`
  - `POST /admin/kpi/execution/run`

## Saved artifacts
- KPI report: `data/kpi_phase12_eval_50.json`
- Synthetic cases: `test_data/kpi_phase12_cases_50.json`
- Isolated eval DB: `data/kpi_phase12_eval.db`
- Isolated report input: `data/kpi_phase12_report.json`
- Isolated policy file: `data/kpi_phase12_policy.json`
- Isolated history file: `data/kpi_phase12_history.json`
- Isolated plan file: `data/kpi_phase12_plan.json`
- Isolated task board file: `data/kpi_phase12_board.json`
- Evaluator script: `scripts/eval_kpi_phase12.py`

## Re-run
```bash
python scripts/eval_kpi_phase12.py --rows 50 --db data/kpi_phase12_eval.db --report-file data/kpi_phase12_report.json --policy-file data/kpi_phase12_policy.json --history-file data/kpi_phase12_history.json --plan-file data/kpi_phase12_plan.json --board-file data/kpi_phase12_board.json --out data/kpi_phase12_eval_50.json --cases-out test_data/kpi_phase12_cases_50.json
```

## Current KPI (50 cases)
- Remediation tasks seeded: `3`
- Execution sync run tasks: `3` (added `3`)
- Lifecycle status counts: `done=1`, `in_progress=1`, `blocked=1`
- Completion rate: `33.33%`
- Overdue active tasks: `1`
- Overdue alert notifications: `2`
- Task lifecycle integrity: `true`
- Overdue alert path: `true`
- Execution success: `100%`
- Runtime latency: `p50 77.55 ms`, `p95 83.54 ms`

## Scheduler knobs
- `KPI_EXECUTION_ENABLED=true|false` (default `true`)
- `KPI_EXECUTION_MINUTES` (default `720`)
- `KPI_TASK_BOARD_FILE` (default `data/kpi_task_board.json`)
