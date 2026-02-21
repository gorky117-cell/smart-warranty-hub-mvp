# OEM Dispatch (Phase 7) KPI Runbook

## Scope
- Pipeline block: OEM weekly analysis + monthly dispatch decisioning.
- Includes send path, rate-limit blocking, dry-run behavior, and insufficient-signal OEM notification.

## Saved artifacts
- KPI report: `data/oem_phase7_eval_50.json`
- Synthetic cases: `test_data/oem_phase7_cases_50.json`
- Isolated eval DB: `data/oem_phase7_eval.db`
- Isolated policy file: `data/oem_dispatch_policy_phase7_eval.json`
- Evaluator script: `scripts/eval_oem_phase7.py`

## Re-run
```bash
python scripts/eval_oem_phase7.py --rows 50 --db data/oem_phase7_eval.db --policy-file data/oem_dispatch_policy_phase7_eval.json --out data/oem_phase7_eval_50.json --cases-out test_data/oem_phase7_cases_50.json
```

## Current KPI (50 cases)
- Run1 (strong signal) decision: `completed`
- Run1 send rate: `100%`
- Run2 (immediate rerun) rate-limit block: `100%`
- Run3 dry-run sent-zero check: `true`
- Run4 insufficient-signal decision: `insufficient_signal`
- Run4 OEM notify count: `1` (expected >=1)
- Total trace sent: `50`
- Total trace blocked: `50`
- Dispatch summary notifications: `1`
- Runtime latency: `p50 1037 ms`, `p95 16512.91 ms`

## Simple meaning
- When signals are strong, dispatch sends correctly.
- Repeat outreach is blocked by rate-limit guardrails.
- Dry-run does not send user messages.
- When signals are weak, system skips user outreach and informs OEM.
