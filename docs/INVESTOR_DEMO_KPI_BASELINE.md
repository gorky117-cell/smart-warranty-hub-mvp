# Smart Warranty Hub - Investor Demo KPI Baseline

Date: 2026-07-22 (corrected 2026-10-03: OCR, predictive and partner KPI rows; see MEMORY.md entry 90)

This file records the current synthetic KPI baseline for investor/demo review. These results are controlled repository evaluations, not live customer or production business outcomes.

## Repository And Test State

- Active repo branch: `master`
- GitHub repo: `https://github.com/gorky117-cell/smart-warranty-hub-mvp`
- Pull check: `git pull --ff-only origin master` returned already up to date.
- Full regression: `249 passed` (re-run 2026-10-03; was `122 passed` on 2026-07-22)
- Local warning: Paddle reports missing `ccache`; this does not fail tests.

## Synthetic KPI Results

| Area | Dataset | Current result |
| --- | ---: | --- |
| Phase 1C ingestion PDF | 50 | 50/50 processed; selectable-text PDFs only; image OCR not yet measured (text came from the PDF text layer, OCR did not run) |
| Invoice key fields | 50 | Measured on selectable-text PDFs only; image OCR not yet measured |
| Phase 2 preflight scraping | 50 | 88.0% lookup/parse success; 100.0% official source and strict-block accuracy |
| Phase 3 terms NLP | 50 | 100.0% duration match, section completeness and enrichment policy checks |
| Phase 4 predictive risk | 50 | Recorded 100.0% label accuracy and changed-case notification recall; unverified after scoring changes in MEMORY.md entries 87-88 |
| Phase 5 NIP advisories | 50 | 100.0% risk-band accuracy, bundle success and nudge event integrity |
| Phase 6 service ticketing | 50 | 100.0% ticket creation, part mapping and retrieval completeness |
| Phase 7 OEM dispatch | 50 | Controlled sends blocked by design; 100.0% rate-limit block in run 2 |
| Phase 8 KPI automation | 50 | 10/10 instrumented KPIs passing; KPI pass rate 100.0% |
| Phase 9 KPI watchdog | 50 | 100.0% decision accuracy |
| Phase 10 remediation loop | 50 | 100.0% decision accuracy; history persistence verified |
| Phase 10A partner KPI coverage | 50 | Not measured: the evaluator generates baseline and "with SWH" values from a seeded random generator and runs no SWH code |
| Phase 10B user journey coverage | 50 | 8/8 synthetic user journey checks passing |
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

Partner KPIs (TPA claim turnaround, retailer escalations, supplier stockouts and excess inventory) are **not yet measured**. Earlier versions of this file listed values from `scripts/eval_partner_kpi_phase10a.py`; that script draws both baseline and "with SWH" values from a seeded random generator without running SWH code, so those values were removed.

User journey coverage now covered by Phase 10B synthetic evaluation:

- Personas covered: new customer, missing fields, near expiry, expired warranty, claim needed, consent denied and mobile-first.
- Checks passing: 8/8.
- Covered areas: upload, summary, predictive risk, notification expectations, cross-user blocking, direct OEM consent blocking, draft-only agent behavior and mobile-first journey inclusion.

## Investor Demo Wording

Use this wording:

> Smart Warranty Hub has controlled 50-case synthetic evaluations across PDF ingestion, warranty terms enrichment, predictive risk, nudges, service ticketing, OEM dispatch, KPI watchdog, remediation, execution tracking and user journey coverage. Image OCR accuracy and partner KPIs are not yet measured. These tests validate the product mechanics and measurement design. They are not live customer or partner impact claims yet.

Avoid claiming production-grade reduction in warranty cost, claim turnaround time, stockouts, escalations or field failures until those metrics are measured from live pilots.

## Refinement Priorities Before Wider Sharing

1. Measure image OCR on the labelled image set (`test_data/ingestion_ocr_50_labeled.csv`) before quoting any OCR accuracy.
2. Improve preflight scraping lookup/parse success from 88.0% by expanding controlled fixtures/parser coverage.
3. Convert Phase 10A synthetic partner KPI coverage into pilot-data instrumentation once partner feeds exist.
4. Keep GitHub reviewers on `master`, or change the repository default branch from `main` to `master`.
5. Keep production claims conservative until persistence and shared infrastructure are upgraded beyond local/process-level pilot stores.
