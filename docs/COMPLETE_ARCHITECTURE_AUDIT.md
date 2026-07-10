# Smart Warranty Hub — Complete Architecture Audit

**Audit date:** 2026-07-10
**Repository root:** `<repository-root>`
**Active branch:** `master`
**Primary application:** `app.main:app`
**Audit scope:** source tree, route registration, templates, database models, services, tests, scripts, runtime data, deployment files, Git topology and existing documentation.

This document is intentionally evidence-based. “Implemented” means code exists in the repository. “Configured” means an external environment variable/credential/connector is still required. “Pilot-ready” does not mean unrestricted enterprise production-ready.

---

## 1. Executive architecture

Smart Warranty Hub (SWH) is a multi-role warranty intelligence platform.

```text
Customer / OEM / TPA / Admin browser
        │
        ▼
Jinja dashboards and optional React/Vite dashboard
        │
        ▼
FastAPI (`app/main.py`)
        │
        ├── Authentication, roles, ownership and consent
        ├── Artifact/invoice intake and pipeline jobs
        ├── Canonical warranty, terms, summary and export
        ├── Behaviour, risk, predictive care, recommendations, notifications
        ├── OEM intelligence, communications and controlled dispatch
        ├── Guided and remote diagnostics/service workflows
        ├── Review crawling, RAG and KPI operations
        └── Scheduler and health surfaces
                 │
                 ├── SQLite locally / PostgreSQL via `DATABASE_URL`
                 ├── local uploads/object-store abstraction
                 ├── JSON/JSONL fallback/config artifacts
                 ├── Optional OCR, LLM, RAG and search providers
                 └── Optional OEM/device connectors
```

The core product principle is **evidence first, enrichment second, safe fallback always**. An invoice may prove a purchase but not contain the complete warranty contract. SWH uses parsing, source discovery, cache, controlled web lookup and optional AI enrichment to construct a confidence-aware customer-facing warranty view.

---

## 2. Runtime boot, deployment and persistence

### 2.1 Application startup

| File | What it does |
|---|---|
| `run_app.py` | Reads `PORT` (default `8000`) and starts `uvicorn app.main:app`. Used by the container. |
| `app/main.py` | Defines FastAPI app, lifespan, routes, template path and middleware. |
| `app/deps.py` | `init_db()` creates schema/admin seed and auth helpers. |
| `app/services/scheduler.py` | Started from the app lifespan, subject to scheduler configuration. |
| `Dockerfile` | Python 3.11 slim image; installs `tesseract-ocr`, Poppler, OpenCV libraries and pip dependencies. |

### 2.2 Persistence

| Layer | Current implementation | Production target |
|---|---|---|
| Application database | SQLite `data/app.db` by default; SQLAlchemy supports PostgreSQL through `DATABASE_URL`. | Managed PostgreSQL, backups and versioned migrations. |
| Uploads/evidence | Local files by default, with `object_store.py` abstraction. | Private object storage (S3-compatible) with lifecycle, encryption and signed access. |
| OEM questions/recommendations | JSONL fallback files under `data/`. | Database tables with tenant ownership/audit. |
| Jobs/scheduler | Database jobs plus in-process scheduler. | Durable job queue/worker and separate scheduler. |
| RAG embeddings | `DocumentEmbeddingDB`; JSON embedding fallback / optional pgvector support. | PostgreSQL + pgvector or managed vector store with authorization controls. |

### 2.3 Runtime status definitions

- **Healthy:** core API/database/predictive components are available.
- **Degraded but usable:** optional OCR, LLM, RAG, web search, scraping or OEM connectors are unavailable; deterministic paths still work.
- **Not safe for production:** insecure credentials/default secrets, local-only persistence, no monitoring/backups, unvalidated partner integrations, or missing governance.

---

## 3. UI and browser surfaces

| Route | Template / front-end file | Role | Notes |
|---|---|---|---|
| `/` | `templates/public_site.html` | Public landing/SEO page. | Marketing entry. |
| `/login` | `templates/login.html` | Customer/OEM/Admin sign-in and sign-up. | `/auth/login` is the API/browser login action. |
| `/ui/neo-dashboard` | `templates/neo_dashboard.html` | Customer Care Dashboard. | Main customer workflow. |
| `/ui/console` | `templates/console.html` | Power-user/debug console. | Uses core APIs; raw JSON/debug visibility. |
| `/ui/oem-dashboard` | `templates/oem_dashboard.html` | OEM/TPA analytics and content operations. | Uses OEM APIs/filters/charts. |
| `/ui/admin-hub` | `templates/admin_hub.html` | Admin controls. | Policy/KPI links. |
| `/ui/scheduler` | `templates/scheduler.html` | Scheduler status/control surface. | Admin-oriented. |
| `/ui/warranty/{id}` | `templates/warranty.html` | Warranty display page. | Alternative presentation. |
| `/ui/warranty-tabs` | `templates/warranty_tabs.html` | Tabbed warranty view. | Alternative presentation. |
| `/ui/react-dashboard` | `templates/react_dashboard.html` | React dashboard entry/redirect. | Separate legacy/demo surface. |
| `/dashboard` | `frontend/dist` if built | Static Vite/React dashboard. | Mounted only when `frontend/dist` exists. |
| `/dashboard-dev` | Vite URL from `VITE_DEV_URL` | Development dashboard redirect. | Requires configuration and auth. |

### 3.1 Neo customer dashboard contract

The main customer template keeps several important UI compatibility rules:

1. Step 1 loads product/warranty data.
2. **See full summary controls only Step 2 — Details & Care.**
3. Step 3 (receipt/bill) and Step 4 (Usage & Health) must remain outside that toggle.
4. Receipt entry supports upload, camera and manual inputs.
5. Full warranty content is formatted for customers; raw JSON is debug-only.
6. Notifications display a product label plus warranty ID and support one-click mark-read.
7. Behaviour questions support choices, booleans and text.
8. Existing browser IDs/functions such as warranty loading and notification controls are compatibility-sensitive.

### 3.2 React/Vite surface

`frontend/` contains a minimal React 18 + Vite + Chart.js dashboard:

- `frontend/src/main.jsx` calls warranty, summary, advisory and predictive APIs.
- `frontend/src/style.css` provides a dark card UI.
- `frontend/package.json` declares React, React DOM, Chart.js and Vite.

It is not the same as the main Jinja customer UI. It is a separate optional dashboard build.

---

## 4. Auth, RBAC, consent and ownership

| File | Actual responsibility |
|---|---|
| `app/deps.py` | JWT token creation/verification, `access_token` cookie/Bearer auth, password hash/verify, `require_user`, `require_oem_or_admin`, `require_admin`, DB initialization. |
| `app/main.py` | Signup/login/logout/password-change/session endpoints, UI redirects and warranty ownership checks. |
| `app/db_models.py` | `UserDB`, `WarrantyOwnerDB`, `AuditLogDB`. |
| `app/services/audit.py` | Audit-table resilience and redacted logging helpers. |
| `app/services/data_governance.py` | Retention cleanup helpers. |

### Role rules

- `user`: customer warranty, behaviour, recommendations, telemetry and customer UI features.
- `oem`, `tpa`, `admin`: OEM/TPA intelligence features where `require_oem_or_admin` is used.
- `admin`: policy, scheduler/KPI, connectors and review administration.

### Security caveat discovered in audit

Importing the app locally prints warnings that `JWT_SECRET` and `JWT_SALT` are using insecure compatibility defaults when environment values are absent. This is intentional local compatibility behavior in current code, but it must be disabled for a real deployment with `ALLOW_INSECURE_DEFAULTS=false` and real secrets.

---

## 5. Data model inventory

All are in `app/db_models.py`.

### Identity, audit and ownership

- `UserDB`
- `AuditLogDB`
- `WarrantyOwnerDB`

### Customer warranty and evidence

- `ArtifactDB`
- `WarrantyDB`
- `PipelineJobDB`
- `ParsedFieldDB`
- `WarrantyTermsCacheDB`
- `WarrantySummaryDB`

### Behaviour, care and predictive context

- `TelemetryEventDB`
- `EVTelemetryDB`
- `BehaviourQuestion`
- `BehaviourAnswer`
- `BehaviourProfile`
- `NudgeEvents`
- `RecommendationRule`
- `RecommendationEvent`
- `PeerReviewSignals`
- `SymptomSearch`
- `RegionalPolicyDB`
- `OemIssueSignalDB`
- `RiskSnapshotDB`

### Notifications, communications and OEM operations

- `NotificationDB`
- `OEMFetchDB`
- `OemCommunicationTraceDB`

### Retrieval, reviews and diagnostics

- `DocumentEmbeddingDB`
- `ProductReviewDB`
- `ReviewPageDB`
- `RemoteDiagnosticSessionDB`
- `RemoteDiagnosticCommandDB`
- `RemoteDiagnosticExecutionDB`
- `GuidedDiagnosticSessionDB`
- `GuidedDiagnosticAnswerDB`
- `GuidedDiagnosticEvidenceDB`

---

## 6. Invoice, OCR and canonical warranty flow

### 6.1 Public API flow

```text
POST /artifacts/upload
        │
        ├── save artifact/evidence
        ├── create/update warranty record and ownership
        ├── create PipelineJobDB job
        └── start background invoice pipeline
                │
                ├── extracting_text
                ├── OCR if needed
                ├── parsed_fields
                ├── terms_lookup
                ├── summarized
                └── done / failed

GET /jobs/{job_id}               → current status
GET /warranties/{id}             → canonical product/warranty
GET /warranties/{id}/summary     → best structured summary
```

### 6.2 Service map

| File | Real function |
|---|---|
| `app/services/invoice_pipeline.py` | Creates/updates pipeline jobs; parses text; updates warranty; invokes terms lookup and summary; stores result. |
| `app/services/ocr.py` | PDF text first, DOCX text support, image/PDF OCR fallback, Tesseract environment fallback and Paddle optional/lazy. |
| `app/services/ingestion.py` | Regex/heuristic extraction of brand, model, product category, serial/IMEI, invoice number, purchase date and coverage hints. |
| `app/services/canonical.py` | Builds canonical warranty details and expiry calculation. |
| `app/services/warranty_status.py` | Computes active/expiring/expired/unknown status and customer claim wording. |
| `app/services/exporter.py` | Exports warranty summary as TXT, HTML or PDF. |
| `app/services/object_store.py` | Local/S3-style object storage helper. |

### 6.3 OCR reality

- The environment fallback is `OCR_ENGINE=tesseract` when no OCR connector is configured.
- The tracked `data/connectors.json` declares `ocr-default` with `metadata.engine="paddleocr"`. `ocr.py` now normalizes `paddleocr`/`paddle` aliases and uses Tesseract as a safe fallback when Paddle cannot run, so configured image OCR no longer silently selects the wrong branch.
- `PaddleOCR` is optional and loaded lazily when selected.
- Tesseract still requires its system binary in the environment; the Dockerfile installs it.
- If PDF text exists, OCR may be avoided entirely.
- If OCR fails, the app should retain the artifact and use manual/partial extraction rather than crash.
- `GET /health/ocr` reports actual configured-engine availability.

### 6.4 Summary reality

- `summary_engine.py` uses a deterministic warranty template when `LLM_PROVIDER=none` or an optional provider fails.
- Optional providers: `mistral`, `ollama_remote`, `llamacpp`.
- Customer summary must not depend on a model API being online.

---

## 7. Warranty terms discovery, preflight and scraping

### Core source resolution order

1. Existing matching warranty data in the database.
2. Fresh terms cache (`WarrantyTermsCacheDB`).
3. Manual approved URL, if supplied/configured.
4. Known/verified OEM domains and bounded source discovery.
5. Limited web search when policy allows it.
6. HTML/PDF/text terms parsing.
7. Cached structured result with source metadata.
8. Transparent fallback category rules if no reliable source is found.

### Files

| File | Function |
|---|---|
| `app/services/terms_lookup.py` | Cache-first lookup, official source/refresher and default terms fallback. |
| `app/services/warranty_discovery.py` | Domain source selection, host/domain matching, region/model scoring, preflight/reachability and bounded search construction. |
| `app/services/warranty_parser.py` | Deterministic extraction of duration/terms/exclusions/claim steps from text, HTML/PDF. |
| `app/services/web_search.py` | Search-provider helper and quota-aware search route. |
| `app/services/oem_domains.py` | Loads known OEM/verified domain mappings. |
| `app/services/oem_domain_verify.py` | Checks/suggests candidate brand domains. |
| `app/services/oem_parsers.py` | OEM-specific text/HTML parsing helpers. |
| `app/scrapers/acmeco.py`, `app/scrapers/zenith.py` | Example brand-specific adapters. |

### Mistral NLP enrichment

- `warranty_parser.py` runs deterministic parsing first.
- If parsed confidence is below `TERMS_NLP_MIN_CONFIDENCE` (default 0.45) or important sections are missing, it may call Mistral.
- Mistral must return structured JSON for duration, terms, exclusions and claim steps.
- If Mistral is absent/fails/returns invalid JSON, deterministic parsed data remains in effect.

### Preflight limitations

This is application-level source/routing validation, not a certification that a site is legal, safe, accurate or contractually approved. For broad production coverage, obtain OEM APIs, approved source agreements and individual adapters.

---

## 8. Behaviour, RAG, risk and predictive-care loop

### 8.1 Behaviour and question files

| File | Function |
|---|---|
| `app/services/behaviour.py` | Behaviour profile, product inference, question scoring and profile access. |
| `app/services/behaviour_questions.py` | Simple JSONL-backed deterministic question set and answer history. |
| `app/services/oem_question_service.py` | Targeted OEM question publishing/selection/answer storage. |
| `app/services/ollama_questions.py` | Optional Ollama question generation, deterministic fallback. |
| `app/services/nudge.py`, `app/services/nudges.py`, `app/services/policy.py` | Nudge generation, event logging and A/B variant assignment. |

### 8.2 RAG

| File | Function |
|---|---|
| `app/services/rag.py` | Optional Mistral embedding generation, metadata-filtered document upsert/retrieval/context building and RAG health/smoke support. |

RAG sources can include warranty summaries, behaviour, telemetry, OEM issues, reviews and remote diagnostic results. It is active only when `RAG_ENABLED=1` and a valid `MISTRAL_API_KEY` is present. It is not an unrestricted knowledge base and should be scoped by metadata such as user/warranty/region.

### 8.3 Predictive/risk

| File | Function |
|---|---|
| `app/services/risk.py` | Base rule-based risk score. |
| `app/services/predictive.py` | Feature vector/model or heuristic scoring, behaviour delta, regional policy, peer review/search/OEM issue/RAG context and explainable reasons. |
| `app/services/regional_policy.py` | Region/brand/model/product rules. |
| `app/services/risk_refresh.py` | Recompute/store risk snapshots. |
| `app/services/peer_review.py`, `app/services/search_log.py` | Review and symptom-search context for risk. |
| `app/services/ev_battery.py` | EV-specific score logic. |

The output must remain advisory/triage information, not a sole automated claims, safety, credit or replacement decision.

### 8.4 Recommendations

| File | Function |
|---|---|
| `app/services/recommendation.py` | Rule matching and recommendation event logging. |
| `app/services/product_recommendations.py` | Product recommendations and aggregate product-interest events. |
| `app/services/oem_recommendation_service.py` | JSONL persistence for OEM-published recommendations. |

---

## 9. Notifications, service and diagnostics

### Notifications and service

| File | Function |
|---|---|
| `app/services/notifications.py` | Schema safety, expiry/risk notification creation, customer/OEM lists and one-click read state. |
| `app/services/service.py` | Service ticket draft / symptom-to-parts workflow. |
| `app/services/emailer.py` | Optional email send helpers for welcome/login/product events. |

### Diagnostics

| Path | Files | Actual use |
|---|---|---|
| IoT / connected product | `app/services/diagnostics_capability.py`, `app/services/remote_diagnostics.py`, `app/routes/remote_diagnostics.py` | Session → command request → optional review → connector execution → trace/telemetry/RAG writeback. |
| Non-IoT product | `app/services/guided_diagnostics.py`, `app/routes/guided_diagnostics.py` | Guided questions → evidence → probable issue/confidence → local service-centre recommendation → optional ticket. |

Remote device actions are guarded by connector configuration, allowed command types, review status and role checks. They are not autonomous LLM actions.

---

## 10. OEM intelligence and operations

### OEM components

| File | Function |
|---|---|
| `app/services/oem.py` | OEM page fetch artifact path. |
| `app/services/oem_issue_feeds.py` | Periodic OEM issue-feed ingestion. |
| `app/services/oem_issue_signals.py` | Issue signal recording and summary. |
| `app/services/oem_communication.py` | Eligibility, rate/importance controls and communication traces. |
| `app/services/oem_dispatch.py` | Weekly analysis/dispatch policy workflow. |
| `app/services/oem_domains.py`, `oem_domain_verify.py` | Official/verified domain management. |
| `app/services/oem_question_service.py` | Question Studio persistence/selection. |
| `app/services/oem_recommendation_service.py` | Recommendation Studio persistence/selection. |

### API support

The dashboard has inline/main-app routes for:

- `/oem/questions/*` and `/api/oem/questions/*` aliases.
- `/oem/recommendations/*` and `/api/oem/recommendations/*` aliases.
- `/oem/products`, `/oem/risk-stats`, `/oem/forecast`.
- `/oem/issues`, `/oem/issues/summary`.
- `/oem/notifications`, `/oem/communications/*`, `/oem/domains/*`.
- `/events/product-interest` for recommendation demand signals.

### Architecture finding: route duplication

`app/routes/oem_questions.py` and `app/routes/oem_recommendations.py` define router endpoints, but current `app/main.py` imports/includes only reviews, remote diagnostics and guided diagnostics routers. The active OEM public endpoints are defined directly in `app/main.py`. Do not include the OEM routers later without first resolving duplicate path definitions and auth behavior.

---

## 11. Reviews, governance, scheduler and KPI

### Review system

| File | Function |
|---|---|
| `app/services/review.py` | Approval/rejection review records. |
| `app/services/review_crawler.py` | Product review crawling with robots/domain controls and sentiment/evidence extraction. |
| `app/services/review_sources.py` | Configured review sources. |
| `app/services/sentiment.py` | Lightweight sentiment computation. |
| `app/routes/reviews.py` | Review crawl/stats modular router. |

### Review route registration

The reviews router is the single source of truth for `/reviews/crawl` and `/reviews/stats`. The previously duplicate inline handlers were removed so route matching and generated API documentation are deterministic.

### Scheduler and governance

| File | Function |
|---|---|
| `app/services/scheduler.py` | In-process recurring jobs for OEM refresh/risk/reviews/expiry/KPI/diagnostics depending on configuration. |
| `app/services/data_governance.py` | Retention cleanup. |
| `app/services/audit.py` | Action audit/redaction/alert helpers. |
| `app/services/kpi_scorecard.py` | Statistical KPI helper functions. |
| `app/services/kpi_watchdog.py` | KPI health policy and alert decisioning. |
| `app/services/kpi_remediation.py` | Remediation plan/history. |
| `app/services/kpi_execution.py` | Execution board/tasks/metrics. |

---

## 12. Route inventory by business domain

### Public, SEO and health

- `GET /`, `/robots.txt`, `/sitemap.xml`, `/favicon.ico`.
- `GET /api/health`, `/health/ocr`, `/health/llm`, `/health/predictive`, `/health/rag`, `/health/full`.

### Auth and account

- `POST /auth/signup`, `/auth/signup/form`, `/auth/login`, `/auth/logout`, `/auth/password/change`.
- `GET /auth/login`, `/auth/session`, `/login`.

### Artifacts, warranty and jobs

- `POST /artifacts`, `/artifacts/upload`, `/artifacts/capture`.
- `GET /warranties/list`, `/warranties/{id}`, `/warranties/{id}/summary`, `/warranties/{id}/export`.
- `POST /warranties/from-artifact`, `/warranties/{id}/process`, `/warranties/summary`, `/warranty/terms/refresh`.
- `GET /jobs/{job_id}`.

### Customer intelligence/support

- `GET /behaviour/next-question`; `POST /behaviour/answer`, `/behaviour-events`, `/telemetry`, `/consent`.
- `POST /risk/score`, `/predictive/score`, `/ev/battery/score`.
- `GET /advisories/{id}`, `/recommendations`, `/notifications`.
- `POST /advisories/nudge-event`, `/notifications/{id}/read`, `/service-tickets`, `/diagnostics/request-remote-check`, `/symptom-search/log`.
- `GET /service-tickets/{id}`, `/diagnostics/capability/{id}`, `/predictive/self-test`.

### LLM/connectors

- `GET /llm/status`, `/api/llm/status`; `POST /llm/generate`.
- `GET /connectors`; `POST /connectors`, `/connectors/reload`.

### OEM and admin

- OEM questions and recommendations plus `/api/oem` aliases.
- OEM domain, issue, product, risk, forecast, fetch, behaviour, notification and communication routes.
- Admin OEM dispatch, KPI policy/report/watchdog/remediation/task/execution and RAG smoke endpoints.
- Region rules, peer reviews, review crawling/stats/approve/reject.

### Diagnostics routers

- `/remote-diagnostics/health`, sessions, commands, approve/reject/execute/run-pending.
- `/guided-diagnostics/start`, session state/next question/answer/evidence/finalize.

The exact OpenAPI runtime list is available at `/docs` or `/openapi.json` after starting the app.

---

## 13. Tests, scripts and evaluation assets

### Pytest tests

- `tests/test_invoice_pipeline.py`
- `tests/test_kpi_execution.py`
- `tests/test_kpi_remediation.py`
- `tests/test_kpi_scorecard.py`
- `tests/test_kpi_watchdog.py`
- `tests/test_notifications.py`
- `tests/test_oem_communication.py`
- `tests/test_oem_dispatch.py`
- `tests/test_policy_variant.py`
- `tests/test_rag_health.py`
- `tests/test_warranty_discovery.py`
- `tests/test_warranty_parser.py`
- `tests/test_warranty_status.py`

### Smoke and operations scripts

- Invoice/OCR/terms: `test_upload.ps1`, `verify_pipeline.py`, `verify_scraping.py`, `verify_ocr_extraction.py`, `verify_paddle.py`, `sqlite_migrate.py`, `fix_schema.py`.
- Behaviour/notifications: `smoke_test_behaviour_*.py`, `smoke_test_notifications.py`, `smoke_test_dev_mode_gate.py`.
- OEM/recommendations: `smoke_test_oem_*.py`, `smoke_test_product_*.py`.
- KPI evaluation: `eval_ingestion_ocr.py`, `eval_preflight_scrape.py`, `eval_terms_nlp_phase3.py`, `eval_predictive_phase4.py`, `eval_nip_phase5.py`, `eval_service_phase6.py`, `eval_oem_phase7.py`, `eval_kpi_phase8.py`, `eval_kpi_watchdog_phase9.py`, `eval_kpi_phase10.py`, `eval_kpi_phase12.py`.
- Model/data helpers: `generate_ingestion_ocr_dataset*.py`, `train_predictive*.py`, `test_extraction.py`, `dump_raw_text.py`, `print_routes.py`.

### Synthetic evaluation assets

`test_data/` includes controlled invoice samples, PDFs, labels and phase scenario JSON. `data/` contains resulting evaluation/report artifacts. These are valuable regression fixtures and technical evidence, but must be labelled synthetic/controlled.

---

## 14. KPI evidence and claims boundary

The source documents record the following controlled outcomes:

- Ingestion/OCR 50-case dataset: OCR success 100%; field F1 varies by field.
- Preflight/scraping 50-case dataset: 88% lookup/parse success; 100% official-source rate in the controlled set.
- Terms NLP 50-case dataset: 100% duration exact/section completeness in the controlled set.
- Predictive 50-case dataset: 100% label/delta accuracy in the controlled set.
- Nudge/service/OEM/KPI phase runbooks: scenario-level success/guardrail outcomes recorded.

Allowed statement:

> SWH has implemented and test-validated MVP workflows with synthetic/controlled benchmark evidence. Live business impact, OCR performance on real documents, model calibration and OEM/service outcomes require a monitored pilot.

Not allowed without live evidence:

- “100% accurate in production.”
- “Reduces warranty cost by X%.”
- “Prevents failures at X%.”
- “Works for all OEM websites.”
- “Autonomously controls devices safely.”

---

## 15. Configuration inventory

### Security

`JWT_SECRET`, `JWT_SALT`, `JWT_EXPIRE_HOURS`, `ADMIN_USER`, `ADMIN_PASS`, `ALLOW_INSECURE_DEFAULTS`, `ALLOWED_HOSTS`, `COOKIE_SECURE`.

### OCR/LLM/RAG

`OCR_ENGINE`, `OCR_MIN_TEXT_CHARS`, `OCR_ENGINE_TTL_SEC`, `LLM_PROVIDER`, `MISTRAL_API_KEY`, `MISTRAL_API_URL`, `MISTRAL_MODEL`, `MISTRAL_EMBED_MODEL`, `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_MODEL_PATH`, `RAG_ENABLED`, `PGVECTOR_DDL_ENABLED`.

### Search/terms/OEM

`TERMS_SCRAPE_ENABLED`, `TERMS_SCRAPE_MODE`, `TERMS_SCRAPE_ALLOW_RETAIL`, `TERMS_OFFICIAL_ONLY`, `TERMS_PREFLIGHT_STRICT`, `TERMS_PREFLIGHT_MAX_DOMAINS`, `TERMS_PREFLIGHT_TIMEOUT_SEC`, `TERMS_SEARCH_MAX_QUERIES`, `TERMS_SEARCH_MAX_RESULTS`, `TERMS_SEARCH_TIMEOUT_SEC`, `TERMS_ALLOW_BROAD_FALLBACK`, provider keys/quotas.

### Operations/diagnostics

`SCHEDULER_ENABLED`, `OEM_REFRESH_MINUTES`, `OEM_ISSUE_FEED_REFRESH_MINUTES`, `RISK_REFRESH_MINUTES`, `REVIEW_CRAWL_*`, `EXPIRY_REMINDER_*`, `OEM_CONTACT_*`, `OEM_ANALYSIS_*`, `OEM_AUTO_DISPATCH_*`, `REMOTE_DIAGNOSTICS_*`, `OBJECT_STORE_*`.

---

## 16. Git/repository hygiene findings

1. `.venv`, pycache, database/log/env files are not tracked; this is good.
2. `frontend/node_modules` currently has approximately **2,366 tracked files**. It should be removed from Git index and added to `.gitignore` in a dedicated repository-hygiene task; do not casually delete it from a working development machine.
3. One captured binary is tracked under `data/captures/`; review whether it is an intentional test fixture or an accidental runtime artifact.
4. The repo includes a large controlled test-data/evaluation corpus. Keep it only if it is intentional evidence/fixture material; do not add real customer evidence.
5. Keep documentation and source changes in intentionally scoped commits; inspect `git status -sb` before committing.

---

## 17. Production readiness

### Suitable today

- Local demo.
- Investor/product demonstration.
- Controlled pilot with a small supported product/OEM scope.
- Staging/integration testing with explicit degraded-mode messaging.

### Required before unrestricted production

1. Managed PostgreSQL/object storage, backup and restore procedures.
2. Durable background job queue/worker; stop relying on in-process scheduler for critical work.
3. Strict secrets/host configuration and security testing.
4. Error tracking, metrics, rate limits, tracing and alerts.
5. Real invoice/OCR/parser validation across regions/product types.
6. Formal OEM API/domain/terms relationships; source governance.
7. Consent, retention, privacy, tenant-isolation and legal review.
8. Model monitoring/drift/calibration and human escalation for high-impact decisions.
9. Load/performance testing and incident/rollback runbook.

---

## 18. Agentic extension status

Google ADK is **not installed or active** in the repository.

The code base is prepared for a safe future agent because services already form a controlled tool layer:

- invoice parsing;
- terms cache/discovery/parser;
- filtered RAG retrieval;
- one-question behaviour flow;
- predictive/advisory functions;
- diagnostic capability routing;
- service-ticket draft creation.

Any agent implementation must be optional and feature-flagged, start disabled, call only approved tools, use quotas/token/time limits, preserve source/cost traces and fall back to the current deterministic SWH flow. It must not perform unrestricted web browsing, uncontrolled data access, OEM communication, record mutation or device command execution.

---

## 19. Required reading and handoff sequence

1. `MEMORY.md`.
2. This audit.
3. `docs/PROJECT_REFERENCE.md`.
4. `docs/AI_IDE_HANDOFF_PROMPT.md`.
5. `docs/GOLDEN_PATH_TEST.md`.
6. `docs/HANDOFF.md`.
7. `docs/deployment_config_reference.md`.
8. `docs/kpi_master_scorecard.md`.

Before changing code:

```powershell
git status -sb
git branch -vv
git log -8 --oneline
git diff --check
python -m pytest tests -q
```

---

## 20. Audit conclusion

SWH contains a coherent and substantial MVP architecture: warranty intake, confidence-aware enrichment, optional OCR/LLM/RAG, explainable risk/care flows, OEM intelligence, controlled diagnostics and operational KPI workflows. The primary next risk is not missing feature ideas; it is production hardening, deduplication of route/repository architecture, verified OEM integrations and measured live-pilot evidence.
