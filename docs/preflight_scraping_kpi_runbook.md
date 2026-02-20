# Preflight + Scraping (Phase 2) KPI Runbook

## Saved artifacts
- KPI report: `data/preflight_scrape_eval_50.json`
- Synthetic case set (50): `test_data/preflight_scrape_cases_50.json`
- Isolated eval DB (cache writes): `data/preflight_eval.db`
- Evaluator script: `scripts/eval_preflight_scrape.py`

## Re-run command
```bash
python scripts/eval_preflight_scrape.py --rows 50 --out data/preflight_scrape_eval_50.json --cases-out test_data/preflight_scrape_cases_50.json --db data/preflight_eval.db
```

## Current KPI result (50 cases)
- Lookup success rate: `88%`
- Source expected match: `100%`
- Duration exact match: `100%`
- Official source rate: `100%`
- Preflight site-query usage: `100%`
- Strict preflight block accuracy: `100%`
- Parser failover success: `100%`
- Latency p50: `14.58 ms`
- Latency p95: `18.07 ms`

## KPI meaning in simple terms
- `Lookup success`: how many cases got scraped terms (not default fallback).
- `Source expected match`: pipeline chose the expected source type (`scraped` vs `default`).
- `Duration exact match`: warranty months matched expected months exactly.
- `Official source rate`: when brand is known, result came from official OEM domain.
- `Strict preflight block accuracy`: when OEM domain is not alive, broad search is correctly blocked.
- `Parser failover success`: if first URL parse fails, backup URL still succeeds.

## Notes
- This phase uses deterministic synthetic mocks to stress pipeline wiring safely.
- `88%` lookup success is expected in this test mix because a subset is intentionally `dead_default` to verify strict preflight fallback behavior.
