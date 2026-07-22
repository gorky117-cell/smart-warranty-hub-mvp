# Smart Warranty Hub

Smart Warranty Hub is an MVP for post-purchase warranty intelligence. It turns invoices, product records, behaviour signals and optional telemetry into structured warranty guidance for customers, plus privacy-safe operational insight for OEM, TPA, retailer and supplier workflows.

The current repo is positioned for MVP/investor review, not full production scale. It includes working FastAPI flows, dashboards/templates, controlled synthetic KPI evaluations, pilot safety hardening and documentation that separates tested evidence from future production claims.

## Review First

- Investor/demo KPI baseline: `docs/INVESTOR_DEMO_KPI_BASELINE.md`
- Documentation index: `docs/DOCS_INDEX.md`
- Project reference: `docs/PROJECT_REFERENCE.md`
- Golden path test checklist: `docs/GOLDEN_PATH_TEST.md`
- Phase 10A partner KPI runbook: `docs/partner_kpi_phase10a_runbook.md`

## Current Evidence Snapshot

- Full local regression: `122 passed`
- Phase 1C OCR PDF synthetic set: 50/50 processed, 100.0% OCR success
- Phase 8 KPI automation: 10/10 instrumented KPIs passing
- Phase 10A partner KPI synthetic coverage: 4/4 partner KPIs passing
- Partner KPI synthetic values:
  - TPA claim TAT improvement: 39.29%
  - Retailer escalation reduction: 26.04%
  - Supplier stockout rate: 2.6%
  - Supplier excess inventory reduction: 20.4%

Important claim boundary: these KPI numbers are controlled synthetic evaluation results, not live customer or partner production outcomes.

## Quick Start

- Install Python 3.11+.
- Create and activate a virtual environment.
- Install dependencies with `pip install -r requirements.txt`.
- Start the API with `uvicorn app.main:app --reload`.
- Open `http://127.0.0.1:8000/docs` for the interactive API.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\eval_partner_kpi_phase10a.py
.\.venv\Scripts\python.exe scripts\eval_kpi_phase8.py
.\.venv\Scripts\python.exe scripts\eval_ingestion_ocr.py --csv test_data\ingestion_ocr_50_labeled_pdf.csv --base-dir . --out data\ingestion_eval_current_50_pdf.json
```

## Optional OCR / LLM

- Default OCR hook expects `paddleocr` for image/PDF ingestion.
- LLM connectors are optional. The platform keeps deterministic fallbacks so the core flow can work without a live LLM provider.
- Connectors are configured in `data/connectors.json`.

## MVP Coverage

- **Ingestion:** upload invoices/manuals/labels/portal artefacts with OCR-capable extraction.
- **Canonicalisation:** create warranty records with product details, coverage, expiry, terms, exclusions and claim steps.
- **Customer guidance:** show coverage summaries, expiry/care nudges, predictive risk and notifications.
- **Resolution support:** generate draft-only warranty resolution checklists with audit traces.
- **OEM/TPA workflows:** expose aggregate insight, controlled question/recommendation flows and OEM dispatch policy checks.
- **KPI automation:** evaluate customer, OEM, platform and partner KPI coverage on controlled synthetic datasets.
- **Pilot safety:** ownership checks, CSRF protection, rate limits, request IDs, per-user AI quotas and direct OEM consent controls.

## Sample Workflow

```bash
curl -X POST http://localhost:8000/artifacts \
  -H "Content-Type: application/json" \
  -d '{"type":"invoice","content":"Brand: AcmeCo Model: WM-900 Serial: SN123456 Purchase: 11-10-2025 24 months warranty"}'

curl -X POST http://localhost:8000/warranties/from-artifact \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"<artifact_id_from_step_1>","overrides":{"product_name":"Washer 900 Pro"}}'

curl "http://localhost:8000/advisories/<warranty_id>?user_id=user-1"
```

## Repo Layout

- `app/main.py` - FastAPI entrypoint and route surface.
- `app/services/` - ingestion, warranty parsing, risk, nudges, OEM workflows, KPI automation, consent, quotas and safety services.
- `templates/` - server-rendered dashboards and UI pages.
- `scripts/` - KPI evaluators, smoke checks, health checks and utility scripts.
- `data/` - controlled evaluation reports, fixture data and local pilot stores.
- `test_data/` - synthetic 50-case KPI datasets and OCR fixtures.
- `docs/` - architecture, audit, KPI, deployment, runbook and investor-demo documentation.

## Current Limits

- Local SQLite/JSON/runtime files are acceptable for the current MVP/demo stage.
- Paid production migration to Postgres, object storage, Redis/queues, managed retrieval and observability is deferred until pilot/funding need.
- Synthetic KPI results should be presented as validation evidence, not live production impact.
- Live partner KPIs require consented pilot data and partner integrations.
