# Smart Warranty Hub - KPI Master Scorecard

Date context: current project state as of February 22, 2026.  
Primary evidence files: `data/*phase*eval*_50.json`

## 1. Phase 1C - Ingestion + OCR

Source: `data/ingestion_eval_current_50_pdf.json`

1. Dataset rows: 50
2. OCR success: 100.0%
3. OCR empty rate: 0.0%
4. Latency P50/P95: 7.18 / 125.54 ms
5. Field F1:
   - brand: 0.8889
   - model_code: 0.6667
   - purchase_date: 0.8889
   - serial_no: 1.0000
   - invoice_no: 0.7500
   - coverage_months: 1.0000
   - product_category: 0.4444

## 2. Phase 2 - Preflight + Official Scraping

Source: `data/preflight_scrape_eval_50.json`

1. Lookup success rate: 88.0%
2. Parse success per case: 88.0%
3. Source expected match: 100.0%
4. Duration exact match: 100.0%
5. Official source rate: 100.0%
6. Site-query usage rate: 100.0%
7. Strict preflight block accuracy: 100.0%
8. Parser failover success: 100.0%
9. Latency P50/P95: 14.58 / 18.07 ms
10. Scenario mix:
   - alive_success: 32
   - dead_default: 6
   - no_brand_broad: 6
   - parse_failover: 6

## 3. Phase 3 - Terms NLP Enrichment

Source: `data/terms_nlp_eval_50.json`

1. Duration exact match: 100.0%
2. Section completeness: 100.0%
3. Low-confidence enrich success: 100.0%
4. High-confidence skip-enrich correctness: 100.0%
5. Deterministic duration preserved: 100.0%
6. Enrich calls total: 30
7. Scenario mix:
   - high_conf_deterministic: 20
   - low_conf_enrich: 20
   - partial_duration_keep: 10

## 4. Phase 4 - Predictive

Source: `data/predictive_phase4_eval_50.json`

1. Label accuracy: 100.0%
2. Behaviour delta direction accuracy: 100.0%
3. Score monotonicity: true
4. Latency P50/P95: 4.64 / 8.93 ms
5. Risk refresh scored: 50 (first), 50 (second)
6. Changed-case notification recall: 100.0%

## 5. Phase 5 - NIP/Nudges

Source: `data/nip_phase5_eval_50.json`

1. Risk band accuracy: 100.0%
2. Bundle generation success: 100.0%
3. Care nudge recall: 100.0%
4. Care nudge false positive: 0.0%
5. Expiry nudge recall: 100.0%
6. Expiry nudge false positive: 0.0%
7. Variant stability: 100.0%
8. Variant split: A=32, B=18
9. Variant balance: 56.25%
10. Latency P50/P95: 11.23 / 17.03 ms

## 6. Phase 6 - Service Workflow

Source: `data/service_phase6_eval_50.json`

1. Ticket creation success: 100.0%
2. Known symptom parts accuracy: 100.0%
3. Unknown symptom no-false-parts: 100.0%
4. Evidence passthrough: 100.0%
5. Draft status consistency: 100.0%
6. Retrieval completeness: 100.0%
7. Latency P50/P95: 0.01 / 0.03 ms

## 7. Phase 7 - OEM Dispatch

Source: `data/oem_phase7_eval_50.json`

1. Run1 send rate: 100.0%
2. Run2 rate-limit block pct: 100.0%
3. Trace integrity checks: pass
4. Dry-run behavior: pass
5. Insufficient signal notify behavior: pass
6. Total traces: sent 50, blocked 50
7. Latency P50/P95: 1037.0 / 16512.91 ms

## 8. Phase 8 - KPI Scorecard

Source: `data/kpi_phase8_eval_50.json`

1. Instrumented KPIs: 10
2. Pass rate: 100.0%
3. Failure prevention rate: 26.67%
4. Alert usefulness rate: 40.0%
5. False alert rate: 6.67%
6. OEM high-risk precision: 60.0%
7. Early warning lead time median: 21.0 days
8. Data freshness SLA: 98.0%
9. Calibration ECE: 0.1162
10. Brier score: 0.1896
11. Drift PSI: 0.1169
12. A/B variant gap: 0

## 9. Phase 9 - KPI Watchdog

Source: `data/kpi_watchdog_phase9_eval_50.json`

1. Run1 decision alert: pass
2. Run2 decision healthy: pass
3. Decision accuracy: 100.0%
4. Total watchdog notifications: 4
5. Latency P50/P95: 68.8 / 83.62 ms

## 10. Phase 10 - KPI Remediation

Source: `data/kpi_phase10_eval_50.json`

1. Run sequence logic: pass
2. Alert streak behavior: pass
3. Healthy transition behavior: pass
4. Decision accuracy: 100.0%
5. History persistence: pass
6. Remediation notifications: 2
7. Latency P50/P95: 111.29 / 261.94 ms

## 11. Phase 12 - KPI Execution Lifecycle

Source: `data/kpi_phase12_eval_50.json`

1. Tasks seeded: 3
2. Task lifecycle integrity: true
3. Overdue alert behavior: true
4. Execution success: 100.0%
5. Run2 completion rate: 33.33%
6. Run2 overdue active: 1
7. Run2 overdue notify count: 2
8. Latency P50/P95: 77.55 / 83.54 ms

## 12. New Modules KPI Readiness (IoT + Non-IoT Diagnostics)

Current state:

1. Remote diagnostics module: implemented and smoke-validated.
2. Guided diagnostics module: implemented and smoke-validated.
3. Dashboard auto-routing capability: implemented and validated.

Note:

Business KPIs for these new modules (adoption, first-time-fix, OEM turnaround impact) require live production observation window after rollout.
