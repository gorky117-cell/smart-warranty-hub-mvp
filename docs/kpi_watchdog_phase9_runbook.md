# KPI Watchdog (Phase 9) Runbook

## Scope
- Pipeline block: production KPI guardrails and alerting.
- Adds policy-driven KPI health checks, OEM/admin notifications, admin APIs, and scheduler integration.

## What was added
- Service: `app/services/kpi_watchdog.py`
- Scheduler hook: `app/services/scheduler.py`
- Admin APIs in `app/main.py`:
  - `GET /admin/kpi-watchdog/policy`
  - `POST /admin/kpi-watchdog/policy`
  - `GET /admin/kpi/report`
  - `POST /admin/kpi/watchdog/run`

## Saved artifacts
- KPI report: `data/kpi_watchdog_phase9_eval_50.json`
- Synthetic cases: `test_data/kpi_watchdog_phase9_cases_50.json`
- Isolated eval DB: `data/kpi_watchdog_phase9_eval.db`
- Isolated watchdog policy: `data/kpi_watchdog_phase9_policy.json`
- Isolated watchdog report input: `data/kpi_watchdog_phase9_report.json`
- Evaluator script: `scripts/eval_kpi_watchdog_phase9.py`

## Re-run
```bash
python scripts/eval_kpi_watchdog_phase9.py --rows 50 --db data/kpi_watchdog_phase9_eval.db --report-file data/kpi_watchdog_phase9_report.json --policy-file data/kpi_watchdog_phase9_policy.json --out data/kpi_watchdog_phase9_eval_50.json --cases-out test_data/kpi_watchdog_phase9_cases_50.json
```

## Current KPI (50 cases)
- Run1 degraded report decision: `alert`
- Run1 OEM/admin notified: `2`
- Run2 healthy report decision: `healthy`
- Run2 OEM/admin notified: `2`
- Total watchdog notifications: `4`
- Decision accuracy: `100%`
- Runtime latency: `p50 68.8 ms`, `p95 83.62 ms`

## Policy knobs
- `min_pass_rate_pct` (default `85.0`)
- `max_failing_kpis` (default `2`)
- `notify_oem` (default `true`)
- `notify_admin` (default `true`)
- `report_file` path (default `data/kpi_phase8_eval_50.json`)

## Scheduler knobs
- `KPI_WATCHDOG_ENABLED=true|false` (default `true`)
- `KPI_WATCHDOG_MINUTES` (default `1440`)
- `KPI_SCORECARD_REPORT_FILE` path (optional override)
- `KPI_WATCHDOG_POLICY_FILE` path (optional override)
