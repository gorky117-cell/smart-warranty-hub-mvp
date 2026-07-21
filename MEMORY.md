# Smart Warranty Hub — Engineering Memory and Due-Diligence Brief

**Purpose:** This is the first file a new coding assistant, engineer, Kiro, Antigravity/Gemini, or technical reviewer should read before changing Smart Warranty Hub (SWH). It records the verified architecture, feature wiring, deployment/Git facts, evidence limits and safe next steps.

**Last repository audit / baseline:** 2026-07-20
**Project type:** FastAPI + Jinja templates + SQLAlchemy.
**Product:** AI-assisted warranty intelligence for customers, OEMs/TPAs and administrators.
**Latest verified hardening:** OCR connector aliases are normalized with a Tesseract fallback; review crawl/stat routes have one active handler each. Phase 1 upload safety now uses server-generated upload filenames, bounded file sizes/types, safe response paths, and same-origin camera permission.

---

## 0. Current phased delivery status

### Phase 0 â€” baseline completed on 2026-07-20

- Active branch was clean and synchronized: `master...origin/master` at `7504fe98` before Phase 1 work.
- Local dependencies were restored from `requirements.txt`.
- The full test suite collected 42 tests and passed: **42 passed**.
- Local FastAPI server started successfully on `127.0.0.1:8000`.
- `GET /ui/neo-dashboard`, `/ui/console`, `/ui/oem-dashboard`, `/health/ocr`, `/health/llm`, and `/health/predictive` returned HTTP 200.
- `/health/full` returned `degraded` only because optional LLM/RAG configuration was disabled; OCR and predictive checks were healthy.

### Phase 1 â€” invoice safety slice completed on 2026-07-20

- `POST /artifacts/upload` preserves its existing response fields and pipeline flow, but now stores evidence using a server-generated filename rather than a browser-controlled path.
- Receipt uploads accept only the existing supported evidence types: PDF, common image formats, TXT, and DOCX; default maximum is 10 MB through `UPLOAD_MAX_BYTES`.
- `saved_path` remains backward compatible but now returns a safe relative logical path rather than an absolute server filesystem path.
- `GET /jobs/{job_id}` now verifies access to the job's warranty before returning job information.
- Customer camera capture is permitted for the same origin through `Permissions-Policy: camera=(self)`; geolocation and microphone remain disabled.
- Focused invoice pipeline verification: **5 passed**.

### Phase 2 - optional OpenAI intelligence lane completed on 2026-07-20

- OpenAI is now an optional, feature-flagged intelligence provider through `app/services/openai_intelligence.py`; the SDK is lazy-loaded and no OpenAI call runs unless explicitly enabled.
- Summary generation accepts `LLM_PROVIDER=openai` and falls back through `OPENAI_FALLBACK_PROVIDER` (`mistral`, `ollama_remote`, `llamacpp`, or `template`) if OpenAI is unavailable.
- Invoice parsing can optionally enrich low-confidence extracted fields with strict JSON output by setting `OPENAI_ENABLED=1`, `OPENAI_INVOICE_ENRICHMENT=1`, and `OPENAI_API_KEY`.
- OpenAI enrichment is limited to invoice/product facts (`brand`, `product_name`, `model_code`, `serial_no`, `invoice_no`, `purchase_date`, `product_category`) and does not generate warranty coverage or legal terms.
- Deterministic high-confidence fields are not overwritten by OpenAI output; enrichment provenance is stored under warranty alternatives for traceability.
- No secret values are stored in the repo; only environment variable names are documented here.

Do not commit generated `data/kpi_*.json` files or `.tmp/`; both are local runtime/test artifacts.

---

## 1. Read this before touching code

1. Preserve working routes and UI IDs unless the matching caller is changed in the same patch.
2. Do not treat an optional AI/OCR/search integration as mandatory. SWH must keep working through deterministic fallbacks.
3. Do not claim live production KPI impact from the evaluation artifacts. Most KPI files are synthetic, controlled 50-case runs.
4. Do not commit `.env`, access tokens, cookies, SQLite files, uploads, generated runtime JSONL or virtual environments.
5. Do not replace a safe deterministic workflow with an LLM-only workflow.
6. Do not let an LLM directly execute a remote device command, send OEM communication or use unrestricted web scraping. Existing policy, consent, verified-domain and approval gates remain authoritative.
7. Before fixing a bug, trace route → service → DB model → template/JS, then run the smallest relevant verification.

---

## 2. Current Git and repository facts

### Branches and remote (verified in this audit)

- Working branch: `master`.
- `origin`: `https://github.com/gorky117-cell/smart-warranty-hub-mvp`.
- Baseline `master` commit before the 2026-07-20 Phase 1 safety work: `7504fe98 Docs: refresh handoff and harden OCR review routing`.
- `origin/master` resolved to the same baseline commit before Phase 1 changes.
- `main` is an older/diverged branch (`ahead 2, behind 43` relative to `origin/main` at audit time). Do **not** assume `main` is the release branch; treat `master` as the active project branch unless the owner intentionally merges/restructures branches.

### Current documentation and hardening set

The maintained handoff set is `MEMORY.md`, `docs/HANDOFF.md`, `docs/PROJECT_REFERENCE.md`, `docs/COMPLETE_ARCHITECTURE_AUDIT.md`, `docs/AI_IDE_HANDOFF_PROMPT.md`, `docs/GOLDEN_PATH_TEST.md`, and `docs/DOCS_INDEX.md`.

Latest verified safeguards:

- `app/services/ocr.py` normalizes `paddleocr`/`paddle` aliases, uses Paddle lazily when selected, and falls back to Tesseract when Paddle cannot run.
- Health checks test Paddle package availability without importing/loading its model.
- `/reviews/crawl` and `/reviews/stats` are registered once through `app/routes/reviews.py`, preventing route-order ambiguity.
- `tests/test_ocr_and_review_routes.py` protects those two regressions.

Before every commit, use `git status -sb` and stage only source, tests, and intended documentation. Do not stage caches, logs, database files, credentials, uploads, or local environment files.

### Recent commit progression

Recent active-branch commits show the current product direction:

1. `3e9ae738` — allows Chart.js/font CDNs in CSP so OEM charts load.
2. `6f4c5a5c` — OEM product selector and model-level filtering for a one-product demo.
3. `dd130776`, `71cc1af9` — Railway/custom-domain HTTPS redirect-loop fixes.
4. `31cc1af9` — email auth flows and password-change UI.
5. `6ccac4c9` — role-based dashboard routing and logout.
6. `eea7d822` — complete product/KPI documentation.
7. Earlier commits added diagnostics, RAG health, KPI lifecycle, ingestion/search/NLP/predictive/nudge/OEM evaluation harnesses and UI refinements.

### Railway status: what is and is not confirmed

- The repository includes Railway-ready deployment support: `Dockerfile`, `run_app.py`, `PORT` handling and deployment documentation.
- Historical notes previously stated that a Railway deployment had green health checks. That is **historical evidence**, not a live verification performed during this audit.
- A coding assistant cannot confirm current Railway health from local repository files alone. Verify after every push with the actual Railway deployment URL, Railway logs and `/health/full`.
- The current branch must be the branch Railway watches. Verify this in Railway Settings; do not assume it watches `master` merely because GitHub has that branch.

---

## 3. Product promise and user roles

### Customer

1. Upload a bill/invoice, use camera capture or load a known product/warranty ID.
2. Receive a structured product/warranty record with coverage, exclusions, claim steps, expiry and source/confidence context.
3. Receive care guidance, risk explanation, notifications, behaviour questions and recommendations.
4. Log usage/health information and, when needed, start diagnostics or service support.

### OEM / TPA

1. View product/brand/model/region risk and issue signals.
2. Publish targeted customer questions and recommendations.
3. Review product-interest/demand signals.
4. Run controlled communications and dispatch analysis with policy traces.

### Admin

1. Manage policy, review, dispatch and KPI operations.
2. Inspect scheduler and operational health.
3. Control sensitive role-gated workflows.

---

## 4. Main runtime architecture

```text
Jinja browser dashboards
  ├─ Customer Care: /ui/neo-dashboard
  ├─ OEM:           /ui/oem-dashboard
  ├─ Console:       /ui/console
  ├─ Admin:         /ui/admin-hub
  └─ Scheduler:     /ui/scheduler
          │
          ▼
FastAPI app: app/main.py
  ├─ Auth/RBAC/ownership
  ├─ Artifact upload + invoice job pipeline
  ├─ Warranty + terms + summary
  ├─ Behaviour + risk + predictive + recommendations
  ├─ Notifications + service + diagnostics
  ├─ OEM intelligence + communications + KPI APIs
  └─ UI, health and export routes
          │
          ├─ SQLAlchemy: SQLite locally / PostgreSQL through DATABASE_URL
          ├─ Runtime JSON/JSONL under data/ for selected fallbacks
          ├─ Optional OCR, LLM, RAG, web search, OEM connectors
          └─ Optional in-process scheduler
```

### Primary source files

| File | Responsibility |
|---|---|
| `app/main.py` | Primary FastAPI app, request models, APIs, UI rendering, health routes, security headers and compatibility endpoints. |
| `app/db.py` | SQLAlchemy connection selection: local SQLite by default, PostgreSQL when `DATABASE_URL` is set. |
| `app/db_models.py` | Durable database schema for users, warranties, artifacts, pipeline jobs, parsed fields, summaries, behaviour, telemetry, notifications, OEM/KPI/diagnostic data. |
| `app/deps.py` | Password hashing, JWT cookie/Bearer auth, role guards, ownership helpers, DB startup and admin seed logic. |
| `app/models.py` | Pydantic/domain objects used in core warranty/risk/nudge/service logic. |
| `app/storage.py` | Legacy/in-memory compatibility store and ID helper. |
| `app/services/` | Domain logic. Treat service functions as the reusable tool layer. |
| `app/routes/` | Modular routers for reviews, remote diagnostics, guided diagnostics and OEM studio variants. |
| `app/scrapers/` | Example OEM-specific source adapters. |
| `templates/` | Server-rendered UI only; preserve DOM IDs/hooks used by inline JavaScript. |
| `scripts/` | Local migration, smoke tests, evaluations and operational helpers. |
| `tests/` | Pytest unit/integration coverage. |

---

## 5. Customer Care Dashboard: real flow

**Route:** `GET /ui/neo-dashboard`
**Template:** `templates/neo_dashboard.html`

### Flow

1. Customer signs in through `/login` / `POST /auth/login`; browser receives `access_token` cookie.
2. Customer loads a product/warranty ID using `GET /warranties/{id}`.
3. Customer sees product label, expiry/coverage summary and risk status.
4. **See full summary controls only Step 2 (Details & Care).** Step 3 receipt and Step 4 usage/health must stay outside that toggle.
5. Step 2 shows customer-friendly coverage, exclusions, claim steps and formatted full text. Raw JSON is debug-only.
6. Step 3 supports one receipt entry path with upload/camera/manual methods. It posts uploaded evidence to `/artifacts/upload`.
7. Step 4 supports usage/health information and telemetry/behaviour context.
8. Customer receives recommendations, advisories, behaviour questions, notifications and diagnostics handoff.

### UI safety constraints

- Keep `loadAll`, notification controls, upload handlers and existing element IDs stable.
- Keep bill upload/camera/manual entry as progressive enhancement; explain degradation when OCR is unavailable.
- Product label should be customer-facing (`Product/Brand Model (wty_id)`); raw warranty IDs remain technical suffixes, not the primary label.
- Notification **Mark read** should remove/read the item and update the badge in one interaction.

---

## 6. Invoice → warranty intelligence pipeline

### APIs

- `POST /artifacts/upload` — authenticated multipart evidence upload.
- `POST /artifacts/capture` — capture/evidence path where environment supports it.
- `POST /warranties/{id}/process` — manually rerun processing.
- `GET /jobs/{job_id}` — pipeline job status.
- `GET /warranties/{id}` — canonical warranty data.
- `GET /warranties/{id}/summary` — best available structured summary.
- `POST /warranties/summary` — legacy summary compatibility route.
- `POST /warranty/terms/refresh` — controlled terms refresh.

### Pipeline stages

```text
uploaded
→ extracting_text
→ ocr_if_needed
→ parsed_fields
→ terms_lookup
→ summarized
→ done | failed
```

### Files and responsibilities

| File | Role |
|---|---|
| `app/services/invoice_pipeline.py` | Creates/persists jobs, runs each stage, updates warranty, parsed fields, terms and summary. |
| `app/services/ocr.py` | PDF text first; Paddle and Tesseract engine aliases are normalized, with Tesseract used as a safe fallback if Paddle is unavailable. Paddle remains optional/lazy and uses TTL-style resource handling where configured. |
| `app/services/ingestion.py` | Deterministic invoice extraction: brand, product, category, model, serial/IMEI, invoice number, date and coverage where present. |
| `app/services/canonical.py` | Converts evidence into a normalized warranty structure and computes coverage/expiry fields. |
| `app/services/terms_lookup.py` | Existing-record/cache lookup, source discovery, parsing, regional policy and transparent default fallback. |
| `app/services/warranty_discovery.py` | Bounded source discovery, official/verified domain preference, region/model ranking and preflight before search. |
| `app/services/warranty_parser.py` | Deterministic terms/exclusion/claim-step parsing, optional Mistral JSON enrichment when confidence is low. |
| `app/services/summary_engine.py` | Template fallback plus optional Mistral/Ollama/llama.cpp summaries. |
| `scripts/sqlite_migrate.py` | Idempotent local SQLite schema safety helper. |

### Important business truth

Invoices generally prove a purchase but do not contain the full warranty agreement. They can miss the full terms, exclusions, claim process, region-specific coverage, serial number or model. SWH must present discovered/default terms as guidance with source/confidence context, not as an unqualified OEM guarantee.

---

## 7. OEM lookup, web search, DNS/domain preflight and scraping

### What is already implemented

1. Check existing internal warranty records first.
2. Check the terms cache (`WarrantyTermsCacheDB`) next.
3. Use configured official/verified OEM domains (`app/services/oem_domains.py`, `app/services/oem_domain_verify.py`).
4. Run bounded domain/reachability preflight in `warranty_discovery.py`.
5. Prefer official domains and use model/product/region matching.
6. Run limited provider search only when configuration and preflight policy allow it.
7. Parse warranty pages, HTML, PDFs and saved source text.
8. Cache successful results; use category defaults if no reliable source is available.

### Main controls

- `TERMS_SCRAPE_ENABLED`
- `TERMS_SCRAPE_MODE`
- `TERMS_OFFICIAL_ONLY`
- `TERMS_PREFLIGHT_STRICT`
- `TERMS_PREFLIGHT_MAX_DOMAINS`
- `TERMS_PREFLIGHT_TIMEOUT_SEC`
- `TERMS_SEARCH_MAX_QUERIES`
- `TERMS_SEARCH_MAX_RESULTS`
- `TERMS_ALLOW_BROAD_FALLBACK`
- Provider keys such as `BRAVE_SEARCH_KEY`, `SERPER_API_KEY`, `SERPAPI_KEY`, `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_CX`.

### What “DNS/preflight” means here

It is a lightweight application-level check: known/verified domain matching, reachability checks and official-domain preference before invoking paid search or parsing a source. It is **not** an OEM security certification and does not replace a contractual OEM API integration.

### Scrapers

- `app/scrapers/acmeco.py`
- `app/scrapers/zenith.py`

These are examples/adapters, not universal OEM coverage. Add one approved adapter or official API per OEM/product family during a real rollout.

---

## 8. Behaviour, RAG, predictive care and AI stack

### Behaviour intelligence

| File | Function |
|---|---|
| `app/services/behaviour.py` | Stores/uses customer behaviour events. |
| `app/services/behaviour_questions.py` | Deterministic small customer question bank and answer persistence. |
| `app/services/oem_question_service.py` | OEM-targeted questions filtered by product context; prevents repeats per user/warranty. |
| `app/services/ollama_questions.py` | Optional Ollama question generation with deterministic fallback. |
| `app/services/nudge.py`, `app/services/nudges.py`, `app/services/policy.py` | Care, expiry and risk nudges with policy/variant support. |

Customer questions should be minimal and purposeful: serial/model confirmation, location/use, usage level, voltage, maintenance, environment or symptom context. Do not turn this into a long repetitive form.

### Predictive/risk engine

| File | Function |
|---|---|
| `app/services/risk.py` | Base rules-based risk. |
| `app/services/predictive.py` | Feature vector, trained-model/heuristic scoring, explanations, behaviour delta, regional policy, issue/review/search/RAG context. |
| `app/services/regional_policy.py` | Region/brand/model/product rules. |
| `app/services/risk_refresh.py` | Snapshot/refresh support. |
| `app/services/ev_battery.py` | EV battery-specific score/recommendations. |

Inputs can include warranty age/coverage, telemetry, usage, failures, care/behaviour scores, region/climate/power policy, peer review signals, symptom search activity, OEM issue signals and optional RAG context. Outputs must stay explainable: label, score, base score, behaviour delta and reasons.

### RAG and Mistral

| File | Function |
|---|---|
| `app/services/rag.py` | Optional Mistral embedding retrieval over warranty summaries, behaviour, telemetry, OEM issues, reviews and diagnostic traces; supports metadata filters. |
| `app/services/summary_engine.py` | Template summary by default; optional `mistral`, `ollama_remote` or `llamacpp` provider. |
| `app/services/warranty_parser.py` | Uses Mistral only to enrich low-confidence structured terms parsing. |

RAG is active only when `RAG_ENABLED=1` and `MISTRAL_API_KEY` exists. If disabled/unavailable, it returns no context and the normal deterministic warranty/risk flow continues. Never assume RAG is active merely because the module exists.

### Customer and OEM recommendations

| File | Function |
|---|---|
| `app/services/recommendation.py` | Care recommendation rules. |
| `app/services/product_recommendations.py` | Product suggestions driven by product/risk/region. |
| `app/services/oem_recommendation_service.py` | OEM publish/list/disable recommendation store. |
| `POST /events/product-interest` | Captures interest signals for OEM demand insight. |

---

## 9. IoT and non-IoT diagnostics

### Capability routing

`app/services/diagnostics_capability.py` selects the safe support path.

| Product type | Flow | Main files |
|---|---|---|
| Connected/IoT product | Remote diagnostics with session, command request, review, connector execution and trace. | `app/routes/remote_diagnostics.py`, `app/services/remote_diagnostics.py` |
| Non-IoT product | Guided questions, evidence capture, probable issue, service-centre recommendation and optional ticket. | `app/routes/guided_diagnostics.py`, `app/services/guided_diagnostics.py` |

### Safety boundary

Remote diagnostics needs a real OEM connector configured in `data/connectors.json`/the connection registry, explicit consent, allowed command types and usually human review. It must never be made autonomous solely because an LLM requests a device action.

---

## 10. OEM, communications, scheduler and KPI operations

### OEM dashboard and APIs

**Dashboard:** `/ui/oem-dashboard` → `templates/oem_dashboard.html`

Capabilities:

- product/brand/model/region filters;
- risk distribution, forecast and product-level analytics;
- OEM issue signals;
- Question Studio: generate/publish/list/disable customer questions;
- Recommendation Studio: preview/generate/publish/list/disable recommendations;
- product-interest/demand signals;
- governed communications and trace retrieval;
- domain verification and controlled OEM fetches.

Both `/oem/...` and `/api/oem/...` compatibility paths are present for question/recommendation clients. `app/main.py` is currently the principal active route source; modular `app/routes/oem_questions.py` and `app/routes/oem_recommendations.py` also exist as reusable router implementations. Do not create new duplicate public paths without checking route registration and OpenAPI output.

### Communication and dispatch

| File | Function |
|---|---|
| `app/services/oem_communication.py` | Controls eligibility, importance, frequency and traceability of OEM messages. |
| `app/services/oem_dispatch.py` | Policy-controlled dry-run/live dispatch. |
| `app/services/oem_issue_signals.py`, `app/services/oem_issue_feeds.py` | Issue signal capture and periodic feed ingestion. |
| `app/services/oem_domains.py`, `app/services/oem_domain_verify.py` | OEM official/verified domain store and verification helpers. |

### Scheduler

`app/services/scheduler.py` starts from the application lifespan when `SCHEDULER_ENABLED` permits it. It is appropriate for local/demo/single-instance workflows. Production should migrate recurring tasks to a durable queue/worker system before large-scale use.

### KPI lifecycle

| File | Function |
|---|---|
| `app/services/kpi_scorecard.py` | KPI report/scorecard. |
| `app/services/kpi_watchdog.py` | Alert/healthy assessment. |
| `app/services/kpi_remediation.py` | Remediation plan creation. |
| `app/services/kpi_execution.py` | Task lifecycle/execution metrics. |

---

## 11. Health, tests and evidence

### Health endpoints

- `GET /health/full` — aggregate status; `degraded` is acceptable when optional OCR/LLM/RAG is unavailable.
- `GET /health/ocr` — actual OCR engine readiness.
- `GET /health/llm` — actual LLM provider readiness.
- `GET /health/predictive` — predictive model/service readiness.
- `GET /health/rag` — RAG configuration/data status.

Do not call a deployment healthy just because the HTTP process responds. Check `/health/full` and its component checks.

### Golden path

Read and run `docs/GOLDEN_PATH_TEST.md` before a demo/deploy. It covers:

1. cookie-based login;
2. customer product load;
3. Step 2 only summary toggle;
4. upload/camera/manual receipt flow;
5. Step 4 usage/health visibility;
6. formatted warranty details and debug-only JSON;
7. notifications/mark read;
8. health/API checks and job polling.

### Important tests/scripts

- `tests/test_invoice_pipeline.py` — no-OCR/no-LLM and mocked OCR text pipeline paths.
- `tests/test_warranty_discovery.py`, `tests/test_warranty_parser.py`, `tests/test_warranty_status.py`.
- `tests/test_notifications.py`, `tests/test_oem_communication.py`, `tests/test_oem_dispatch.py`, `tests/test_rag_health.py`.
- `scripts/smoke_test_behaviour_*.py`, `scripts/smoke_test_notifications.py`.
- `scripts/smoke_test_oem_*.py`, `scripts/smoke_test_product_*.py`.
- `scripts/test_upload.ps1` — Windows authenticated upload flow.
- `scripts/sqlite_migrate.py` — idempotent local schema migration/safety step.

### KPI evidence: synthetic benchmark only

The project contains useful evaluation artifacts, mainly 50-case controlled/synthetic datasets under `data/`. They show that implementation paths were tested; they do **not** demonstrate live commercial outcomes.

| Phase | Recorded evaluation result | Evidence boundary |
|---|---|---|
| 1C ingestion/OCR | 50 rows; OCR success 100%; brand F1 0.8889; model F1 0.6667; purchase-date F1 0.8889. | Controlled dataset; real invoice quality can differ. |
| 2 preflight/scraping | Lookup/parse success 88%; official-source rate 100%; strict preflight accuracy 100%. | Controlled sources/scenarios; OEM websites change. |
| 3 terms NLP | Duration exact match and section completeness recorded at 100%. | Synthetic/controlled terms cases; needs real-source evaluation. |
| 4 predictive | Label accuracy/behaviour-delta direction recorded at 100%; P50/P95 4.64/8.93 ms. | Not live risk/outcome validation. |
| 5 nudges | Bundle success/recall recorded at 100%; false positives 0% in dataset. | Not proof of real engagement or prevention impact. |
| 6 service | Ticket creation/evidence flow recorded at 100%. | Workflow correctness, not service resolution KPI. |
| 7 OEM dispatch | Send/rate-limit/dry-run traces pass. | Does not prove real recipient or OEM impact. |
| 8–12 KPI lifecycle | Scorecard/watchdog/remediation/execution artifacts pass their scenario checks. | Operational simulation; live observation still required. |

Use this exact external statement: **“SWH has implemented and test-validated MVP workflows with synthetic/controlled benchmark evidence. Live production business impact and model performance require a monitored pilot.”**

---

## 12. Production and pilot decision

### Appropriate now

- Internal demo.
- Investor technical demonstration.
- Controlled MVP pilot with limited users, supported product categories and clear terms-disclaimer language.
- OEM discovery/connector proof of concept using approved sources.

### Required before unrestricted production

1. Use managed PostgreSQL and object storage; do not rely on local SQLite/JSONL/uploads across multiple instances.
2. Add durable workers/queue for invoice jobs, scheduled tasks and retry/idempotency controls.
3. Set production secrets; disable insecure defaults and seed credentials.
4. Add backups, observability, error tracking, rate limits, retention and incident procedures.
5. Measure OCR/parser/terms/predictive performance on real consented data.
6. Use formal OEM APIs or approved adapters; do not rely on ungoverned scraping.
7. Complete privacy, consent, security and regional legal review.
8. Keep remote diagnostics review-gated until OEM/device validation is complete.
9. Load-test application, uploads, exports, scheduler and database.

---

## 13. Optional Google ADK / agentic extension — not installed or active yet

SWH already has a suitable **tool layer** for an agent. Google ADK should be added only as an optional orchestration layer, not as a replacement for deterministic core services.

### Proposed controlled Warranty Resolution Agent

```text
Upload/customer request
→ read parsed invoice data
→ assess field confidence
→ ask at most one useful question if essential data is missing
→ call verified-domain terms lookup when needed
→ retrieve authorized RAG context
→ produce customer-friendly evidence-aware summary and next action
```

Potential controlled tools already exist:

- read canonical warranty/parsed fields;
- run terms cache/discovery/parser;
- retrieve filtered RAG context;
- get next behaviour/OEM question;
- calculate predictive score/advisories;
- choose diagnostics capability;
- create a draft service workflow.

### Non-negotiable agent rules

- Feature flag default off: e.g. `AGENTIC_WORKFLOW_ENABLED=0`.
- Do not run the agent for every page load or every invoice.
- Call it only for low-confidence/missing warranty resolution, explicit customer AI-help request or an approved scheduled OEM report.
- Use cache, token limits, per-user quotas, maximum tool calls and timeouts.
- Search only approved/verified OEM sources and preserve citations/source URLs.
- Do not write warranty data, contact users or execute remote commands without current validation/policy/approval layers.
- Record agent decision, tool calls, source, cost/tokens, user/warranty scope and final status.
- If Google/Gemini/ADK fails, continue through the normal SWH deterministic path.

### Cost model

Google ADK is a framework; model/search/OCR calls create the variable cost. The lowest-cost approach is: rules/cache/PDF text first → OCR only if needed → agent only for difficult cases → cache the outcome. Weekly OEM summaries should be aggregated by product/region and generated once per period, not once per customer.

---

## 14. Environment/config groups

### Security/auth

- `JWT_SECRET`, `JWT_SALT`, `JWT_EXPIRE_HOURS`
- `ADMIN_USER`, `ADMIN_PASS`
- `ALLOW_INSECURE_DEFAULTS`
- `ALLOWED_HOSTS`
- `COOKIE_SECURE`

### OCR and LLM

- `OCR_ENGINE`, `OCR_MIN_TEXT_CHARS`, `OCR_ENGINE_TTL_SEC`
- `LLM_PROVIDER` (`none`, `mistral`, `openai`, `ollama_remote`, `llamacpp`)
- `OPENAI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SEC`, `OPENAI_MAX_INPUT_CHARS`, `OPENAI_INVOICE_ENRICHMENT`, `OPENAI_FALLBACK_PROVIDER`
- `MISTRAL_API_KEY`, `MISTRAL_API_URL`, `MISTRAL_MODEL`, `MISTRAL_EMBED_MODEL`
- `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_MODEL_PATH`
- `RAG_ENABLED`, `PGVECTOR_DDL_ENABLED`

### Terms/search/OEM

- `TERMS_*` controls listed in section 7.
- Search provider keys and quotas.
- `OEM_CONTACT_*`, `OEM_ANALYSIS_*`, `OEM_AUTO_DISPATCH_*`, `OEM_DISPATCH_POLICY_FILE`.

### Scheduler/operations

- `SCHEDULER_ENABLED`
- `OEM_REFRESH_MINUTES`, `OEM_ISSUE_FEED_REFRESH_MINUTES`, `RISK_REFRESH_MINUTES`
- `REVIEW_CRAWL_*`, `EXPIRY_REMINDER_*`
- retention/alert/object-storage environment variables.

### Diagnostics

- `REMOTE_DIAGNOSTICS_ALLOWED_COMMANDS`
- `REMOTE_DIAGNOSTICS_CONNECTOR`
- `REMOTE_DIAGNOSTICS_TIMEOUT_SEC`
- `REMOTE_DIAGNOSTICS_AUTO_EXECUTE`
- `REMOTE_DIAGNOSTICS_POLL_MINUTES`, `REMOTE_DIAGNOSTICS_BATCH_SIZE`

Never put values/secrets into this file; put names only.

---

## 15. New assistant / Kiro / Antigravity prompt

Copy this into a new assistant:

> You are continuing work on Smart Warranty Hub (SWH), a FastAPI + Jinja + SQLAlchemy warranty intelligence MVP. First read `MEMORY.md`, `docs/PROJECT_REFERENCE.md`, `docs/HANDOFF.md`, and `docs/GOLDEN_PATH_TEST.md`. Active Git branch is `master`; do not use the older diverged `main` branch. Preserve existing endpoints, authentication, UI IDs and fallback behavior. The system is pilot-ready, not unrestricted-production-ready. OCR, Mistral/RAG, web search, OEM scraping and diagnostics integrations are optional and must degrade safely. KPI results are synthetic/controlled benchmark evidence, not live commercial claims. Before editing, trace route → service → database → template. After editing, run focused tests and do not commit secrets, SQLite DBs, uploads, JSONL runtime stores, caches or venv files.

---

## 16. Useful commands

```powershell
# Local start
.\.venv\Scripts\Activate.ps1
python scripts\sqlite_migrate.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Test
python -m pytest tests -q
python -m py_compile app\main.py

# Local health
curl.exe http://127.0.0.1:8000/health/full
curl.exe http://127.0.0.1:8000/health/ocr
curl.exe http://127.0.0.1:8000/health/llm
curl.exe http://127.0.0.1:8000/health/predictive

# Git audit
git status -sb
git log -5 --oneline
git branch -vv
git ls-remote --heads origin
```

---

## 17. Related docs

- `docs/COMPLETE_ARCHITECTURE_AUDIT.md` — verified architecture audit, route/model/service inventory and known maintenance findings.
- `docs/PROJECT_REFERENCE.md` — full architecture/file map/AI and production plan.
- `docs/HANDOFF.md` — concise engineering handoff.
- `docs/GOLDEN_PATH_TEST.md` — executable customer/API test journey.
- `docs/complete_product_specification_and_kpi.md` — stakeholder/KPI product overview.
- `docs/kpi_master_scorecard.md` — synthetic evaluation details.
- `docs/oem_dashboard_and_integration_manual.md` — OEM/IoT/non-IoT integration manual.
- `docs/deployment_config_reference.md` — Railway/env/operations reference.
- `docs/DOCS_INDEX.md` — documentation navigation.

---

## 18. Latest Phase 3A update

- Added the additive warranty evidence trust layer in `app/services/summary_engine.py`.
- Existing summary responses now expose `evidence_status` with labels for `confirmed`, `confirmed_internal`, `cached`, `estimated`, and `not_confirmed`.
- Customer summaries now explicitly say terms are not confirmed when source evidence is invoice-only, missing, or default-rule based.
- Neo dashboard summary metadata displays the evidence label/note without changing routes or existing fields.

---

## 19. Latest Phase 3B update

- Added `app/services/source_trust.py` to classify warranty term sources without changing scraping or summary contracts.
- Evidence now distinguishes known OEM domains from unverified external scraped URLs.
- Unverified scraped warranty terms are labeled not confirmed and require OEM verification; official-domain sources can still be shown as confirmed with source metadata.
- Added focused tests for source trust and evidence status behavior.

---

## 20. Latest Phase 3D update

- Added synthetic approved-source fixtures for testing the warranty evidence/RAG path without pretending they are real OEM proof.
- `data/warranty_sources.json` now includes clearly labeled synthetic Acmeco ZX-100 and Quickfix PROBOOK source records.
- The synthetic source HTML lives under `test_data/` and is ignored by discovery unless `TERMS_ALLOW_LOCAL_DEV_SOURCES=1` is enabled.
- Synthetic source evidence is classified as `synthetic_test_source` and remains customer-facing **not confirmed**; OEM verification is still required.
- Added focused tests so local dev sources stay hidden by default and can be explicitly enabled for test runs.

## 21. Latest Phase 3E telemetry privacy/intelligence update

- Added `app/services/telemetry_intelligence.py` for sanitized telemetry handling and explainable signal classification.
- `/telemetry` now strips direct identifiers such as serial number, IMEI, invoice number and location-like fields before storing payload data or indexing RAG context.
- Telemetry payloads now include `_telemetry_intelligence` with `signal`, `risk_points`, `care_points` and short reasons, keeping downstream risk/OEM logic explainable.
- OEM analytics now includes a privacy-safe telemetry aggregate, and `/oem/telemetry-stats` exposes aggregate-only counts.
- OEM telemetry aggregates are suppressed until the minimum cohort threshold is met (`OEM_TELEMETRY_MIN_COHORT`, default 10).
- Added focused tests for telemetry sanitization/classification and cohort suppression.

## 22. Latest Phase 4A OEM telemetry UI update

- Commit `f2b15c57` (`Phase 4A: show OEM telemetry privacy status`) was pushed to `origin/master`.
- `templates/oem_dashboard.html` now shows a **Privacy-safe telemetry** card using the existing `/oem/risk-stats` telemetry aggregate.
- The OEM UI displays privacy suppression status, cohort size and minimum threshold when the cohort is below `OEM_TELEMETRY_MIN_COHORT`.
- When the threshold is met, the same card shows aggregate-only telemetry signals, event counts, risk points and care points.
- Existing OEM dashboard sections were preserved: risk distribution, reviews, forecast, behaviour snapshot, Question Studio, Recommendation Studio, top issues, EV battery overview and product interest.
- Focused verification after the UI change: `23 passed` across telemetry intelligence, OEM dispatch, invoice/OpenAI pipeline, RAG health, warranty discovery and OCR/review route tests.
- Live Railway checks after Phase 3E confirmed `/health/full` was `ok`, `/oem/telemetry-stats` exists, and unauthenticated access returns `401 Missing token`; logged-in OEM/admin access showed expected suppression for cohort size `1` and minimum cohort `10`.

## 23. Latest Phase 5A behaviour + predictive care update

- Behaviour questions now use `get_next_useful_question` so the app asks at most one question only when useful.
- Useful-question triggers include missing serial number, missing country/region, voltage issue telemetry, high usage, overheating/shutdown signals, missing usage context and missing environment context.
- Existing OEM-published questions remain first in the customer question flow; the deterministic useful-question bank is the fallback.
- Predictive output now explicitly keeps legal warranty status separate from care-risk scoring through `legal_warranty_separate`.
- Predictive responses now include an explainable `risk_reason_breakdown` for base warranty age/expiry, behaviour delta and usage/environment factors.
- Predictive responses now include the disclaimer: `Care signal, not a guaranteed product failure prediction.`
- EV battery logic remains a product-specific extension and was not changed.
- Focused verification: `26 passed` across Phase 5 behaviour/predictive tests plus telemetry, notifications, OEM dispatch, invoice/OpenAI pipeline, RAG health and warranty status tests.

## 24. Latest Phase 6A OEM aggregate intelligence update

- Added `app/services/oem_aggregate.py` as an additive privacy-safe OEM aggregate layer; existing OEM dashboard, risk, question, recommendation, telemetry and dispatch APIs were not removed.
- Added `/oem/aggregate-insights` for product type, brand, model, region and date-range filtered aggregate insight.
- Aggregate output includes registered product count, risk distribution, top care issues, behaviour trends, expiry cohorts, product interest, service demand and recommendation opportunities.
- The endpoint suppresses results below `OEM_AGGREGATE_MIN_COHORT` (default follows `OEM_TELEMETRY_MIN_COHORT`, otherwise 10) and returns only cohort-level metrics.
- OEM Question Studio and Recommendation Studio remain active; this endpoint gives them safer aggregate context rather than exposing individual customer data.
- Focused verification: `23 passed` across Phase 6 aggregate tests plus Phase 5 behaviour/predictive, telemetry, OEM dispatch/communication, invoice/OpenAI pipeline and RAG health tests.

## 25. Latest Phase 6B OEM aggregate dashboard update

- `templates/oem_dashboard.html` now shows an **OEM aggregate insight** card near the top of the dashboard.
- The card calls `/oem/aggregate-insights` with the same product type, brand, model and region filters used by the existing dashboard.
- Below-threshold cohorts show a privacy suppression state with cohort size and minimum cohort.
- Eligible cohorts show registered product count, risk distribution, expiry cohorts, behaviour/care averages, top care issues, service demand and recommendation opportunities.
- Existing OEM UI sections were preserved: risk chart, forecast, behaviour chart, privacy-safe telemetry, Question Studio, Recommendation Studio, top issues, EV overview and product interest.
- Focused verification: `23 passed` across Phase 6 aggregate, Phase 5 behaviour/predictive, telemetry, OEM dispatch/communication, invoice/OpenAI pipeline and RAG health tests.

## 26. Latest Phase 6C OEM question aggregate loop update

- Added aggregate OEM question answer stats without exposing individual customer answers.
- `app/services/oem_question_service.py` now has `aggregate_answers`, which suppresses answer stats below `OEM_QUESTION_MIN_COHORT` (default follows aggregate threshold, otherwise 10).
- Added protected `/oem/questions/answer-stats` endpoint for OEM/admin users.
- `templates/oem_dashboard.html` now shows **Aggregate answers** under Customer Question Studio, with privacy suppression state or aggregate answer counts.
- Existing Question Studio publish/active/disable flow and Recommendation Studio were preserved.
- Focused verification: `25 passed` across Phase 6C question loop, Phase 6 aggregate, Phase 5 behaviour/predictive, telemetry, OEM dispatch/communication, invoice/OpenAI pipeline and RAG health tests.

## 27. Latest Phase 6D OEM recommendation aggregate loop update

- Added aggregate recommendation demand stats without exposing individual customer actions.
- `app/services/product_recommendations.py` now has `aggregate_product_interest_stats` for privacy-gated product-interest action counts.
- `app/services/oem_recommendation_service.py` now has `aggregate_stats`, combining active OEM recommendations with aggregate product-interest demand and recommendation opportunities.
- Added protected `/oem/recommendations/stats` endpoint for OEM/admin users.
- `templates/oem_dashboard.html` now shows **Aggregate demand** under Recommendation Studio, with suppression state or aggregate product demand/action counts.
- Existing customer recommendations, product recommendations, product-interest events, Question Studio and Recommendation Studio generation/publish flows were preserved.
- Focused verification: `28 passed` across Phase 6D recommendation loop, Phase 6C question loop, Phase 6 aggregate, Phase 5 behaviour/predictive, telemetry, OEM dispatch/communication, invoice/OpenAI pipeline and RAG health tests.

## 28. Latest Phase 7A controlled OEM source policy update

- Added `app/services/oem_source_policy.py` as the central policy helper for controlled OEM source verification.
- Discovery now reuses the same approved-host matching logic for configured OEM domains and verified domains.
- Broad fallback web search remains disabled by default and is additionally blocked in production unless `TERMS_ALLOW_PRODUCTION_BROAD_SEARCH=1` is set together with the existing broad-fallback control.
- Production manual URL terms refresh is blocked unless the URL belongs to an approved/verified OEM domain or `TERMS_ALLOW_PRODUCTION_MANUAL_URL=1` is explicitly set.
- Added protected `/oem/source-policy` so OEM/admin users can audit current source policy state for a brand/URL.
- Existing internal warranty lookup, terms cache, official-domain discovery, manual URL support in non-production, scraping adapters, parser/NLP enrichment, RAG, OCR, telemetry, behaviour, OEM question and recommendation features were preserved.
- Focused verification: `19 passed` across warranty discovery, warranty parser, evidence status and source trust tests; edited Python files compile.

## 29. Latest Phase 7B first controlled OEM adapter update

- Added `app/services/oem_adapters.py` with a first controlled Samsung adapter.
- The Samsung adapter only fetches URLs under approved Samsung domains and returns parsed evidence as `approved_oem_adapter`.
- `fetch_oem_page` now uses the adapter registry when a brand adapter exists; non-adapter brands still go through the Phase 7A source policy before fetching.
- Added protected `/oem/adapters` so OEM/admin users can audit currently enabled controlled adapters.
- Existing OEM fetch review queue, scheduler path, OEM parsers, terms lookup, discovery, cache, RAG, OCR, telemetry, behaviour, Question Studio and Recommendation Studio were preserved.
- Focused verification: `22 passed` across Phase 7 adapter, warranty discovery, warranty parser, source trust and evidence status tests; edited Python files compile.

## 30. Latest Phase 7C approved-source cache/evidence update

- Added shared terms-source classification through `terms_lookup.classify_terms_source_url`.
- Invoice pipeline and manual terms refresh now use the same source classifier instead of duplicating source-type rules.
- Successful terms lookups from approved OEM domains are labeled `approved_oem_source` for evidence/audit clarity; unapproved HTTP sources remain `scraped`.
- Source trust now gives approved OEM source evidence a distinct label while still requiring OEM verification for claim certainty unless the domain is explicitly verified.
- Existing terms cache behavior, internal warranty lookup, default fallbacks, scraping/adapters, OCR, OpenAI/LLM, RAG, telemetry, behaviour and OEM dashboard features were preserved.
- Focused verification: `31 passed` across source trust, evidence status, warranty parser/discovery, invoice pipeline and Phase 7 adapter tests; edited Python files compile.

## 31. Latest Phase 7D OEM fetch preflight update

- Added `preflight_oem_fetch` to enforce approved-source checks before OEM fetch work is queued, reviewed or executed.
- `/oem/fetch` now rejects arbitrary URLs at the API boundary instead of placing them into the OEM fetch queue.
- Admin review approval for `oem_fetch` repeats the same preflight check before execution.
- Controlled brand adapters remain the preferred path; Samsung adapter URLs must stay under approved Samsung domains.
- Non-adapter brands still use the Phase 7A source policy, with production arbitrary URL fetches blocked by default.
- Existing OEM review queue, scheduler, adapter registry, terms cache, discovery/parser, OCR, OpenAI/LLM, RAG, telemetry, behaviour, Question Studio and Recommendation Studio were preserved.
- Live smoke after Phase 7C deploy: `/health/full` returned `ok`; `/oem/source-policy` and `/oem/adapters` returned expected unauthenticated `401 Missing token`.
- Focused verification: `27 passed` across Phase 7D preflight, adapter, discovery, parser, source trust and evidence tests; edited Python files compile.

## 32. Latest Phase 7E OEM source verification UI update

- `templates/oem_dashboard.html` now includes a **Controlled source verification** card.
- The card calls protected `/oem/source-policy` and `/oem/adapters` using the selected brand filter.
- OEM/admin users can see production/preflight/official-only/broad-search/local-fixture policy status and the enabled controlled adapter domains.
- Existing OEM dashboard sections were preserved: risk distribution, aggregate insight, forecast, behaviour chart, telemetry, Question Studio, Recommendation Studio, top issues, EV overview and product interest.
- Focused verification: `28 passed` across Phase 7E UI, Phase 7D preflight, Phase 7 adapter, discovery, parser, source trust and evidence tests; edited Python files compile.

## 33. Latest Phase 8A controlled Warranty Resolution Agent update

- Added `app/services/warranty_resolution_agent.py` as a deterministic, controlled agent service.
- Added protected `POST /agent/warranty-resolution`; it checks warranty ownership before running.
- The agent is feature-flagged off by default with `AGENTIC_WORKFLOW_ENABLED=0`.
- Allowed tools are explicitly limited to reading warranty record, invoice evidence, terms source, risk/care context and creating a draft claim checklist.
- Not allowed actions are explicitly listed and not implemented: send OEM emails, change warranty status, submit claims, browse arbitrary websites, execute remote diagnostics or access another customer's data.
- When enabled, the agent returns draft explanation/checklist output only, including evidence status, warranty status, risk/care context, missing/uncertain fields and a tool-call trace.
- Existing invoice pipeline, terms lookup/cache, Phase 7 controlled OEM source policy, OCR, OpenAI/LLM, RAG, telemetry, behaviour, diagnostics gates, Question Studio and Recommendation Studio were preserved.
- Focused verification: `19 passed` across Phase 8 agent, warranty status, Phase 5 behaviour/predictive, source trust and evidence tests; edited Python files compile.

## 34. Latest Phase 8B Neo dashboard agent checklist UI update

- `templates/neo_dashboard.html` now includes a collapsed **Resolution checklist** panel under Step 4 usage/health.
- The panel calls protected `POST /agent/warranty-resolution` after a product is loaded.
- The panel shows draft-only checklist output, missing/uncertain fields and the agent safety note; if the feature flag is off, it shows the disabled state instead.
- Existing Step 2 summary control, bill upload/camera/manual flow, telemetry, diagnostics, behaviour questions, recommendations, EV battery card and notifications were preserved.
- Focused verification: `18 passed` across Phase 8B UI, Phase 8 agent, warranty status, Phase 5 behaviour/predictive and invoice pipeline tests; edited Python files compile.

## 35. Latest Phase 8C agent audit trace update

- Warranty Resolution Agent runs now record a JSONL audit trace under `AGENTIC_TRACE_FILE` (default `data/agentic_traces.jsonl`).
- Disabled, not-found and draft runs all return a `trace_id`.
- Trace records include agent name, user/warranty scope, status, whether a question was present, allowed tools, blocked actions and allowed tool-call metadata.
- The trace intentionally avoids storing secrets, raw invoice text, full prompt content or any mutation/action side effects.
- Existing feature-flag behavior, draft-only output, ownership checks, Neo dashboard checklist, OCR, OpenAI/LLM, RAG, telemetry, diagnostics gates and Phase 7 source policy were preserved.
- Focused verification: `13 passed` across Phase 8 agent trace/UI, warranty status and Phase 5 behaviour/predictive tests; edited Python files compile.

## 36. Latest Phase 8D agent trace viewer update

- Added `warranty_resolution_agent.list_traces` for read-only JSONL audit trace retrieval.
- Added protected `GET /agent/warranty-resolution/traces` for OEM/admin users.
- Trace viewer supports `user_id`, `warranty_id`, `status` and `limit` filters, returning newest traces first.
- The endpoint only reads audit records; it cannot run the agent, mutate warranty data, submit claims, contact OEMs, browse websites or execute diagnostics.
- Existing Phase 8 feature flag, draft-only agent output, Neo dashboard checklist, trace recording, OCR, OpenAI/LLM, RAG, telemetry, diagnostics gates and Phase 7 source policy were preserved.
- Focused verification: `14 passed` across Phase 8 agent trace/viewer/UI, warranty status and Phase 5 behaviour/predictive tests; edited Python files compile.

## 37. Latest Phase 9A runtime safety defaults update

- Added `app/services/runtime_safety.py` for shared production/runtime checks.
- Insecure JWT/admin seed defaults are now allowed by default only outside production; production requires explicit `ALLOW_INSECURE_DEFAULTS=1` to keep compatibility behavior.
- If `JWT_SECRET`/`JWT_SALT` are missing and insecure defaults are not allowed, the runtime uses generated/derived values instead of fixed public defaults.
- Admin seeding now skips default `admin/admin123` when insecure defaults are not allowed; set `ADMIN_USER` and `ADMIN_PASS` for production admin bootstrap.
- The optional in-process scheduler is still available for local/demo/single-instance workflows, but defaults off in detected multi-instance runtimes unless `SCHEDULER_ENABLED=1` is explicitly set.
- Existing OCR, OpenAI/LLM, RAG, OEM source policy/adapters, telemetry, behaviour, predictive care, diagnostics gates, Question Studio, Recommendation Studio and controlled agent features were preserved.

## 38. Latest Phase 9B rate-limit safety update

- Added `app/services/rate_limiter.py` as a lightweight in-process pilot limiter.
- Rate limiting is enabled by default and can be disabled only with `RATE_LIMIT_ENABLED=0` for controlled local runs.
- Protected high-risk/high-cost boundaries now include login, artifact upload, direct LLM generation, warranty summary generation, OEM question/recommendation generation and the draft warranty-resolution agent.
- Limits are environment-configurable per scope: `RATE_LIMIT_LOGIN_*`, `RATE_LIMIT_UPLOAD_*`, `RATE_LIMIT_AI_*` and `RATE_LIMIT_AGENT_*`.
- The limiter keys authenticated routes by user and unauthenticated login attempts by client IP / forwarded IP.
- Added focused tests for threshold blocking, authenticated-user separation, forwarded-IP login limiting and the local off switch.

## 39. Latest Phase 9C CSRF protection update

- Added `app/services/csrf.py` for double-submit CSRF token generation and validation.
- Login now issues a readable `csrf_token` cookie alongside the HTTP-only `access_token` cookie.
- Unsafe cookie-authenticated requests (`POST`, `PUT`, `PATCH`, `DELETE`) now require a matching `X-CSRF-Token` header; Bearer-token API calls remain compatible.
- Logout clears both the auth cookie and CSRF cookie.
- Neo, OEM, admin, console, React, simple upload and warranty-tab UI helpers now attach the CSRF token for browser write actions.
- Scheduler form posts include the CSRF token in the form action for the existing non-JavaScript form path.
- Added focused tests for CSRF cookie issuance, rejection without token, acceptance with token and Bearer-token compatibility.

## 40. Latest Phase 9D request tracing/logging update

- Added `app/services/request_context.py` for request ID generation and structured request log records.
- Every HTTP response now includes `X-Request-ID`, reusing a valid caller-supplied value when present.
- Request logging records method, path, status code, elapsed milliseconds, client IP and safe user context without storing request bodies, cookies, tokens, invoice content or authorization headers.
- CSRF failures and unhandled exceptions use the same request ID path so Railway logs can be correlated with browser/API responses.
- Unhandled exceptions return a generic JSON 500 response rather than leaking internal exception details.
- Added focused tests for generated request IDs, supplied request ID reuse, CSRF rejection headers and sensitive-header redaction.

## 41. Latest Phase 9E per-user AI quota update

- Added `app/services/ai_quota.py` as a lightweight per-user daily AI usage quota store.
- AI quota enforcement is enabled by default and configurable through `AI_QUOTA_ENABLED`, `AI_DAILY_QUOTA_PER_USER` and `AI_QUOTA_FILE`.
- Quota gates now protect direct LLM generation, warranty summary generation, OEM question generation, OEM recommendation generation and the draft warranty-resolution agent.
- Added protected `GET /ai/usage` so a signed-in user can inspect their current daily AI quota usage.
- Quota records are aggregate counts by user/day/feature and do not store prompts, invoices, tokens, model responses or raw customer payloads.
- Added focused tests for consumption, blocking, disable switch, route-level enforcement and usage reporting.

## 42. Latest Phase 9F direct OEM consent update

- Added `app/services/oem_consent.py` for explicit direct-OEM sharing consent separate from aggregate analytics consent.
- Direct OEM communication now requires `consent_oem_direct_sharing=true` by default through `REQUIRE_OEM_DIRECT_CONSENT=1`.
- Existing aggregate OEM telemetry/insight endpoints are unchanged; they continue to use cohort suppression and do not require direct-sharing consent.
- `/consent` can now update direct OEM sharing consent, and `GET /consent` returns both analytics and direct-OEM sharing consent state.
- OEM communication traces now record `oem_direct_consent_required` when a direct message is blocked for missing direct-sharing consent.
- Added focused tests for default-off direct consent, consent endpoint update/access control and OEM communication blocking.

## 43. Latest Phase 9G pilot security hardening update

- Added shared request-user and warranty-existence helpers for legacy API hardening.
- Behaviour events, risk scoring, advisories, nudge events, service tickets, telemetry, predictive scoring and terms refresh now enforce authenticated user ownership before acting on a warranty.
- Normal users can no longer pass another user's `user_id`; OEM/TPA/admin roles keep operator access where the existing role model already allowed it.
- The warranty detail UI now resolves the current signed-in user by default and preserves demo-public behavior only when that feature is enabled.
- The partial database admin fallback now uses the shared Phase 9 runtime safety rule instead of defaulting insecure in production.
- `pytest.ini` now limits discovery to `tests` and sets `pythonpath = .`, so plain `pytest` works from the repo root.
- Added focused regression tests for cross-user payload rejection, warranty ownership enforcement, owner success path and production admin fallback safety.
- Verification: `python -m compileall -q app` passed; `pytest -q` passed with `122 passed` and the existing three scikit-learn model-version warnings.

## 44. Hackathon readiness audit - 2026-07-22

- Final read-only audit completed with the active branch clean and synchronized: `master...origin/master` at `803e8b38` (`Harden pilot ownership checks`).
- Verification repeated successfully: `pytest -q` passed with `122 passed`; `python -m compileall -q app` passed.
- The public production site responded successfully over HTTPS and has the expected security headers. Its protected `/consent` route returned `401 Missing token`, confirming an authenticated Phase 9-era deployment surface.
- Hackathon assessment: ready for a controlled demo. The product has protected upload/OCR, warranty intelligence, optional OpenAI capability, predictive care, telemetry privacy, OEM workflows, controlled agent outputs and Phase 9 pilot safeguards.
- Do not present the synthetic 50-case KPI evaluations as live customer outcomes. Describe them as controlled test evidence.
- Remaining non-blocking hackathon risks: GitHub's default branch is still the older `main` while active work is on `master` (112 commits ahead); no GitHub Actions or branch protection; rate limiting, AI quota and direct-consent persistence are local/process-bound for the pilot; the local environment reports dependency conflicts and three scikit-learn model-version warnings.
- Recommended immediate presentation action: set GitHub's default branch to `master` before judges review the repository. Production hardening is intentionally out of scope for the hackathon.
- Judge-facing presentation script: `docs/HACKATHON_DEMO_GUIDE.md`.
