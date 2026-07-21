# Smart Warranty Hub - Investor Demo KPI Baseline

Date: 2026-07-22

This file records the current synthetic KPI baseline for investor/demo review. These results are controlled repository evaluations, not live customer or production business outcomes.

## Repository And Test State

- Active repo branch: `master`
- GitHub repo: `https://github.com/gorky117-cell/smart-warranty-hub-mvp`
- Pull check: `git pull --ff-only origin master` returned already up to date.
- Full regression: `122 passed`
- Local warning: Paddle reports missing `ccache`; this does not fail tests.

## Synthetic KPI Results

| Area | Dataset | Current result |
| --- | ---: | --- |
| Phase 1C ingestion/OCR PDF | 50 | 100.0% OCR success; 0 missing files |
| OCR key fields | 50 | Brand/model/purchase date/invoice/coverage/category F1 = 1.0 |
| OCR serial number | 50 | Precision/recall/F1 = 0.925 |
| Phase 2 preflight scraping | 50 | 88.0% lookup/parse success; 100.0% official source and strict-block accuracy |
| Phase 3 terms NLP | 50 | 100.0% duration match, section completeness and enrichment policy checks |
| Phase 4 predictive risk | 50 | 100.0% label accuracy; 100.0% changed-case notification recall |
| Phase 5 NIP advisories | 50 | 100.0% risk-band accuracy, bundle success and nudge event integrity |
| Phase 6 service ticketing | 50 | 100.0% ticket creation, part mapping and retrieval completeness |
| Phase 7 OEM dispatch | 50 | Controlled sends blocked by design; 100.0% rate-limit block in run 2 |
| Phase 8 KPI automation | 50 | 10/10 instrumented KPIs passing; KPI pass rate 100.0% |
| Phase 9 KPI watchdog | 50 | 100.0% decision accuracy |
| Phase 10 remediation loop | 50 | 100.0% decision accuracy; history persistence verified |
| Phase 12 execution tracking | 50 | 100.0% execution success; lifecycle integrity verified |

## KPI Automation Details

Instrumented KPIs currently passing:

- Failure prevention rate: 26.67% against target `>= 25%`
- Alert usefulness rate: 40.0% against target `>= 35%`
- False alert rate: 6.67% against target `<= 20%`
- OEM early warning lead time: 21 days median against target `>= 14 days`
- OEM high-risk precision: 60.0% against target `>= 55%`
- Data freshness SLA: 98.0% against target `>= 98%`
- Model calibration ECE: 0.1162 against target `<= 0.12`
- Brier score: 0.1896 against target `<= 0.22`
- Drift PSI: 0.1169 against target `<= 0.20`
- A/B variant balance gap: 0 against target `<= 1`

Not yet instrumented:

- TPA claim turnaround time
- Retailer escalations per 1,000 units
- Supplier stockout rate

## Investor Demo Wording

Use this wording:

> Smart Warranty Hub has controlled 50-case synthetic evaluations across ingestion/OCR, warranty terms enrichment, predictive risk, nudges, service ticketing, OEM dispatch, KPI watchdog, remediation and execution tracking. These tests validate the product mechanics and measurement design. They are not live customer impact claims yet.

Avoid claiming production-grade reduction in warranty cost, claim turnaround time, stockouts, escalations or field failures until those metrics are measured from live pilots.

## Refinement Priorities Before Wider Sharing

1. Improve OCR serial-number extraction from 92.5% F1 toward 100%.
2. Improve preflight scraping lookup/parse success from 88.0% by expanding controlled fixtures/parser coverage.
3. Add real instrumentation for TPA claim TAT, retailer escalations and supplier stockout metrics.
4. Keep GitHub reviewers on `master`, or change the repository default branch from `main` to `master`.
5. Keep production claims conservative until persistence and shared infrastructure are upgraded beyond local/process-level pilot stores.
