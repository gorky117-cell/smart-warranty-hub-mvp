# NIP / Advisories (Phase 5) KPI Runbook

## Scope
- Pipeline block: `risk -> policy variant -> nudge generation -> nudge event logging`.
- Goal: confirm advisory bundle quality and stability.

## Saved artifacts
- KPI report: `data/nip_phase5_eval_50.json`
- Synthetic cases: `test_data/nip_phase5_cases_50.json`
- Isolated eval DB: `data/nip_phase5_eval.db`
- Evaluator script: `scripts/eval_nip_phase5.py`

## Re-run
```bash
python scripts/eval_nip_phase5.py --rows 50 --db data/nip_phase5_eval.db --out data/nip_phase5_eval_50.json --cases-out test_data/nip_phase5_cases_50.json
```

## Current KPI (50 cases)
- Risk-band accuracy: `100%`
- Bundle generation success: `100%`
- Care nudge recall (for medium/high): `100%`
- Care nudge false positives (for low risk): `0%`
- Expiry nudge recall (near-expiry): `100%`
- Expiry nudge false positives (far-expiry): `0%`
- Variant stability (same user+warranty): `100%`
- Variant split: `A=32`, `B=18`
- Nudge-event integrity: `100%`
- Latency: `p50 11.23 ms`, `p95 17.03 ms`

## Simple meaning
- Users always get a nudge bundle.
- Care nudges appear only when risk is medium/high.
- Expiry nudges appear only near expiry.
- A/B variant sticks consistently per user+warranty.
- Nudge action/ignore events are saved correctly.
