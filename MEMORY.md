# Smart Warranty Hub — Engineering Memory and Due-Diligence Brief

**Purpose:** This is the first file a new coding assistant, engineer, Kiro, Antigravity/Gemini, or technical reviewer should read before changing Smart Warranty Hub (SWH). It records the verified architecture, feature wiring, deployment/Git facts, evidence limits and safe next steps.

**Last repository audit / baseline:** 2026-07-20 (structured sections 1–19)
**Last wiring re-verification:** 2026-08-12 at commit `5fb93f96`
**Project type:** FastAPI + Jinja templates + SQLAlchemy.
**Product:** AI-assisted warranty intelligence for customers, OEMs/TPAs and administrators.

> **How to read this file.** Sections 1–19 are the structured reference and were written around
> commit `7504fe98`. The numbered entry log at the end (currently through entry 87) is
> append-only and is the **authoritative record of current behavior**. Where the two disagree,
> trust the entry log and the code. A wiring re-verification on 2026-08-12 corrected the
> predictive/risk input claim in section 8 and refreshed the Git facts in section 2; other
> structured sections may still lag the entry log.

**Latest verified hardening:** Newly onboarded products no longer receive false risk claims — a
no-evidence floor keeps the label LOW and only device-specific evidence can unlock HIGH; one risk
notification stays unread per warranty (entry 87). AI-proposed warranty facts are accepted only
when grounded in scraped/OCR source text (entry 80). OEM terms are region-validated before reuse
(entries 79, 84). OCR connector aliases are normalized with a Tesseract fallback; review crawl/stat
routes have one active handler each.

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

Verified at 2026-08-12. `master` is at `5fb93f96`, synchronized with `origin/master`, 209 commits
total. Current product direction:

1. `5fb93f96` — stop false risk claims on newly onboarded products (entry 87).
2. `6ad8ee54` — product-specific OEM diagnostic question wording.
3. `c631e7be` — customer-friendly warranty summary bullets.
4. `1174d677`, `cc0efab3` — invoice region drives OEM terms lookup; wait for pipeline job before load.
5. `3ee4ee3d` — source-grounded AI warranty extraction guard (entry 80).
6. `41029bd9`, `bafe83b6` — OEM terms region validation and regional source preference.
7. Phases 1–9 before that added upload safety, an optional OpenAI lane, evidence/source-trust
   labels, OEM aggregate insights, controlled OEM source policy and adapters, the warranty
   resolution agent, and the runtime-safety/rate-limit/CSRF/AI-quota/OEM-consent layer.
8. Earlier commits added diagnostics, RAG health, KPI lifecycle, ingestion/search/NLP/predictive/nudge/OEM evaluation harnesses and UI refinements.

The prior baseline commits (`3e9ae738`, `6f4c5a5c`, `dd130776`, `eea7d822`) are roughly 100 commits
behind current `master` and are retained only as historical context.

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
| `app/services/predictive.py` | Feature vector, trained-model/heuristic scoring, explanations, behaviour delta, regional policy, OEM issue/RAG context. |
| `app/services/regional_policy.py` | Region/brand/model/product rules. |
| `app/services/risk_refresh.py` | Snapshot/refresh support. |
| `app/services/ev_battery.py` | EV battery-specific score/recommendations. |

**Verified risk composition.** `score_warranty()` combines exactly five lanes: (1) the trained model over a 12-feature vector, (2) a telemetry behaviour delta clamped to `±0.25`, (3) `RegionalPolicyDB` deltas, (4) `OemIssueSignalDB` aggregate severity up to `+0.2`, and (5) an optional RAG delta when `RAG_ENABLED=1`. Score is clamped 0–1 after each lane, then the entry-87 guards apply (no-evidence floor `0.32`, medium cap `0.66`), then thresholds `>0.66` HIGH / `>=0.33` MEDIUM / else LOW. The 12 features are `product_type, age_months, usage_hours_per_day, error_count, failure_count, maintenance_count, behaviour_score, care_score, responsiveness_score, region_code, climate_band, power_quality_band`; behaviour answers reach features 7–9 via `behaviour._apply_scoring()`.

Outputs must stay explainable: label, score, base score, behaviour delta, reasons and context gaps.

**Not scored into risk (correction).** `predictive.py` defines `_peer_review_features()`, `_search_features()` and `_nudge_features()`. All three are implemented and **called by nothing** — the risk-side wiring was never completed. Earlier revisions of this file listed peer review signals and symptom search activity as risk inputs; that was inaccurate. That data is collected and used for OEM aggregate intelligence (`/peer-reviews/update`, `/symptom-search/log`, OEM dashboard insight routes, `review_crawler` → `record_peer_signal`), but it never reaches the customer risk score. If wired later it must be a post-model delta like lanes 3–5, because the trained model does not carry those features.

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

## 42. Latest global invoice product extraction correction

- Fixed invoice parsing to prefer scored line-item product/OEM rows over seller/header text.
- Seller/retailer text is retained in extraction alternatives instead of being treated as the OEM brand.
- Added generic known-OEM and product-term scoring for messy OCR invoices; the regression case is an image-only printer invoice where OCR reads `Epson L 3250 Printer`.
- Fixed category inference so substring matches like `delivery` no longer trigger EV classification.
- New invoice-only warranties no longer get invented generic coverage/exclusion terms; they keep claim-prep steps and require official OEM terms verification.
- Added Epson to the approved OEM domain/source library with the official India L3250 product warranty page, so controlled terms lookup can initialize from product evidence before relying on broad web search.
- Fixed the invoice pipeline source-classification import so successful terms lookup is persisted instead of failing the job after product extraction.
- Fixed terms lookup so generic invoice claim-prep steps alone do not count as reusable internal warranty terms; this prevents incomplete first-pass records from blocking official OEM lookup.
- Terms cache reuse now requires a real non-internal source URL, preventing stale/default cache rows from masking official OEM discovery.
- Evidence summaries now treat `approved_oem_source` URLs as confirmed source evidence instead of falling through to missing-evidence messaging.
- Controlled terms discovery can now bootstrap official-looking OEM domains when a detected invoice brand is missing from the approved domain catalog, then uses site-scoped warranty search from that live brand-matching domain.
- Stress testing found and fixed numeric-leading model codes such as `55UQ7500`; 100 synthetic invoice parse cases across printer/mobile/HP printer/TV patterns completed with zero parser failures.
- Existing OCR, OpenAI/LLM enrichment, RAG, controlled OEM source policy/search, telemetry, behaviour, predictive care, recommendations, diagnostics and agent features were preserved.

## 43. Latest auth form route resilience update

- Added `GET /auth/signup/form` as a safe redirect back to `/login`.
- This prevents browser refresh/direct-open of the POST-only signup form action from showing a Railway 405/application-failed page.
- Existing POST signup behavior, login flow, cookie auth, CSRF behavior and dashboard routes were preserved.

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
- Hackathon-specific presentation artifacts were later removed from the repo and kept only as local backups because the project direction changed to investor/MVP readiness.

## 45. Hackathon artifact cleanup - 2026-07-22

- The earlier hackathon-specific demo files were removed from the repo after the project direction changed away from the OpenAI hackathon.
- Local backup copies are preserved outside the repo at `D:\smart-warranty-hub-mvp-main\local_download_backups\hackathon_docs`.
- Removed repo artifacts: `docs/HACKATHON_DEMO.html`, `docs/HACKATHON_DEMO_GUIDE.md` and `docs/Smart_Warranty_Hub_Hackathon_Demo_Guide.docx`.
- Investor/MVP readiness docs remain in the repo, especially `docs/INVESTOR_DEMO_KPI_BASELINE.md` and `docs/partner_kpi_phase10a_runbook.md`.

## 46. Investor/demo synthetic KPI retest - 2026-07-22

- Direction changed from hackathon submission to investor/demo repository sharing.
- Pulled `origin/master`; repo was already up to date.
- Full regression passed: `122 passed`, with one local Paddle `ccache` warning.
- Refreshed the synthetic KPI evaluators for ingestion/OCR PDF, preflight scraping, terms NLP, predictive risk, NIP advisories, service ticketing, OEM dispatch, KPI automation, watchdog, remediation and execution tracking.
- Current synthetic baseline is documented at `docs/INVESTOR_DEMO_KPI_BASELINE.md`.
- Key strong points: 100.0% OCR success on 50 PDF samples, 100.0% pass on the 10 instrumented Phase 8 KPIs, 100.0% decision accuracy for watchdog/remediation, and 100.0% execution success for Phase 12 lifecycle tracking.
- Current refinement targets at that point: OCR serial-number F1 is 0.925, preflight lookup/parse success is 88.0%, and TPA claim TAT / retailer escalations / supplier stockout KPIs were not yet instrumented before Phase 10A.
- Investor-safe claim boundary remains: these are controlled synthetic test results, not live production customer outcomes.

## 47. Phase 10A partner KPI synthetic coverage - 2026-07-22

- Added `scripts/eval_partner_kpi_phase10a.py` for controlled synthetic partner KPI coverage.
- Added `docs/partner_kpi_phase10a_runbook.md`.
- Generated `data/partner_kpi_phase10a_eval_50.json` and `test_data/partner_kpi_phase10a_cases_50.json`.
- Phase 10A covers TPA claim turnaround time, retailer escalations per 1,000 units, supplier stockout rate and supplier excess inventory.
- Current synthetic 50-case result: 4/4 partner KPIs passing.
- Current synthetic values: TPA claim TAT improvement 39.29%, retailer escalation reduction 26.04%, supplier stockout rate 2.6%, supplier excess inventory reduction 20.4%.
- This preserves the claim boundary: partner KPI coverage is synthetic test evidence only until real pilot partner feeds exist.

## 48. GitHub investor-readiness cleanup - 2026-07-22

- Changed the GitHub repository default branch from `main` to `master` using `gh repo edit`.
- Verified GitHub now reports `defaultBranchRef.name` as `master`.
- Rewrote `README.md` for investor/MVP first impression.
- README now surfaces the investor KPI baseline, docs index, project reference, golden path, Phase 10A partner KPI runbook, current evidence snapshot, validation commands and pilot limits.
- The README explicitly states that synthetic KPI numbers are controlled evaluation results, not live production outcomes.

## 49. Phase 10B user journey synthetic coverage - 2026-07-22

- Added `scripts/eval_user_journey_phase10b.py` for controlled synthetic user-journey coverage.
- Added `docs/user_journey_phase10b_runbook.md`.
- Generated `data/user_journey_phase10b_eval_50.json` and `test_data/user_journey_phase10b_cases_50.json`.
- Phase 10B covers seven personas: new customer, missing fields, near expiry, expired warranty, claim needed, consent denied and mobile-first.
- Current synthetic 50-case result: 8/8 user journey checks passing.
- Covered checks: upload success, warranty summary success, predictive flow success, notification expectation coverage, cross-user access blocking, direct OEM consent blocking, draft-only agent boundary and mobile-first journey inclusion.
- This preserves the claim boundary: user journey coverage is synthetic test evidence only until real product analytics and user cohorts exist.

## 50. Controlled multi-source OEM evidence merge - 2026-07-23

- Fixed Smart Warranty Hub's terms lookup to go deeper after invoice OCR/product extraction instead of stopping at the first official product page.
- `lookup_terms` now parses and merges up to `TERMS_AUTO_MAX_SOURCES` controlled discovered sources, default `4`, covering product pages, warranty pages, support pages, manuals and claim pages when discovery returns them.
- The merge keeps the strongest duration, combines unique terms, exclusions and claim steps, and preserves multiple official source URLs in `TermsResult.source_urls`.
- Invoice pipeline and manual terms refresh now persist `terms_source_urls` in warranty alternatives while keeping the existing primary `terms_source_url` for compatibility.
- Evidence summaries now expose every stored terms source link, so the UI/API can show product/warranty/support/manual evidence instead of one collapsed link.
- This is a global pipeline fix, not an Epson-only or single-invoice patch. It applies to any invoice where OCR/extraction identifies enough brand/model/product context and controlled discovery finds approved/verified OEM sources.
- The safety boundary remains: no arbitrary web browsing by the agent, no marketplace/social sources as authority, and missing official evidence must remain "not confirmed" instead of invented warranty terms.
- Verification passed: `python -m py_compile app\models.py app\services\terms_lookup.py app\services\invoice_pipeline.py app\main.py app\services\summary_engine.py`; focused OEM evidence tests passed with `29 passed`; full `python -m pytest -q` passed with `130 passed` and the existing three scikit-learn model-version warnings.

## 51. Upload failure visibility patch - 2026-07-23

- Kept this fix narrow after a production dashboard showed `Upload failed:` without a reason.
- The upload endpoint now catches unexpected OCR/ingestion exceptions and returns a JSON `500` with `Upload processing failed: ...` instead of letting the server return a blank/non-JSON failure.
- The Neo dashboard upload handler now reads the raw response body before JSON parsing, so backend text/HTML/empty failures show a useful reason or HTTP status instead of a blank message.
- No warranty/OEM/RAG behavior was changed in this patch.
- Verification passed: `python -m py_compile app\main.py`; local upload of `C:\Users\lenovo\Desktop\printer invoice .pdf` returned `200` with a warranty/job id; focused upload/CSRF tests passed with `2 passed` and the existing three scikit-learn model-version warnings.

## 52. Global official warranty detail extraction - 2026-07-23

- Fixed the warranty parser pipeline, not a single Epson record, so official OEM pages can contribute richer details for any invoice/product.
- Added generic extraction for usage-limit warranty language such as pages, prints, cycles, hours, kilometres/miles and `whichever comes first`.
- Added generic extraction for covered component terms such as printhead, motor, compressor, panel, battery, charger, drum and lamp without hard-coding one invoice.
- Added generic extraction of claim/service route lines such as product registration, warranty check, service request, repair status and service center/contact support.
- Prevented component-specific long warranties from incorrectly replacing the base product warranty duration when a normal product duration is also present.
- Live official Epson India L3250 page verification parsed: `12` months, `30,000 prints`, `whichever comes first`, printhead coverage and service/warranty support steps from the official Epson page.
- The safety boundary remains unchanged: only already-approved/controlled sources can confirm warranty terms, and missing exclusions/claim details must stay explicit rather than invented.
- Verification passed: `python -m py_compile app\services\warranty_parser.py app\services\terms_lookup.py app\services\invoice_pipeline.py app\services\summary_engine.py`; focused parser/pipeline/discovery/evidence tests passed with `32 passed`; full `python -m pytest -q` passed with `132 passed` and the existing three scikit-learn model-version warnings.

## 53. New upload terms cache refresh fix - 2026-07-23

- Root cause of the post-parser deployment screen: new invoice jobs were allowed to reuse the existing 30-day `WarrantyTermsCacheDB` row for the same brand/category/region.
- That meant a newly uploaded Epson invoice could still show the old cached term `Standard coverage for 12 months from purchase date` even after the global parser learned to extract `30,000 prints`, `whichever comes first`, printhead coverage and service steps.
- Fixed `invoice_pipeline.run_job` so fresh invoice uploads call `lookup_terms(..., force_refresh=True)` and re-parse controlled official sources instead of using stale cached terms.
- Added a regression test proving new upload pipeline calls terms lookup with `force_refresh=True`.
- Verification passed: `python -m py_compile app\services\invoice_pipeline.py`; focused cache/parser/pipeline test slice passed with `3 passed`; focused parser/pipeline/evidence/discovery suite passed with `33 passed` and the existing three scikit-learn model-version warnings.

## 54. Global warranty interpretation and care intelligence - 2026-07-25

- Fixed Smart Warranty Hub's official-terms interpretation globally, not just for one Epson invoice.
- The parser now separates base warranty duration from optional extended/service-plan language such as CoverPlus, extended warranty, service plan and protection plan.
- Optional plans are still preserved as labelled terms, but they no longer drive the base warranty expiry. This prevents an upsell like "up to 5 years" from turning a 12-month base warranty into a false 60-month warranty.
- Live controlled Epson L3250 source verification now parses `12` months, `30,000 prints`, `whichever comes first`, printhead coverage and support actions while keeping optional extended plans separate.
- Claim/support extraction now filters obvious marketing/navigation noise such as Brighter Futures, home/about links, promotions and generic "dedicated customer service" copy.
- Product suggestions are now category-aware general care, not generic product ads: printers get ink/nozzle/periodic-printing care; phones get battery/screen/charger care; fridges get gasket/coils/temperature care; TVs get surge/panel/ventilation care; appliances get voltage/installation/service care; unknown products get safe general guidance.
- Recommendation text is intentionally framed as general care advice and not as OEM warranty coverage, claim eligibility or free-repair confirmation.
- Existing upload, OCR, OpenAI/Mistral/RAG, controlled OEM lookup, telemetry, predictive-risk, OEM aggregate and agent wiring were preserved.
- Verification passed: focused parser/OEM/upload/recommendation suite passed with `35 passed`; full `python -m pytest -q` passed with `137 passed` and the existing three scikit-learn model-version warnings.

## 55. Broader product-aware care categories - 2026-07-25

- Expanded the shared product-care recommendation layer beyond the first buckets, without changing warranty fact confirmation or OEM evidence rules.
- Added safe category detection and care advice for heaters, geysers/water heaters, fans, AC units, washing machines, microwaves, cameras, routers, smartwatches/wearables, speakers/audio, purifiers, kitchen appliances, air coolers and inverter/UPS products.
- Kitchen appliance coverage includes mixers, grinders, blenders, food processors, juicers, choppers, toasters and kettles.
- Heater/cooling/power coverage includes oil heaters, room heaters, water heaters/geysers, air coolers and inverter/UPS products.
- Advice remains general care only; it does not claim OEM coverage, claim eligibility or free repair unless official warranty terms prove those facts elsewhere in the pipeline.
- Fixed a category bug where raw `ac` matched inside words like `machine`; AC detection now requires AC-specific phrases such as air conditioner, split AC or window AC.
- Added regression coverage for the new category mapping so these products do not fall back to generic backup/sync-style suggestions.
- Verification passed: focused recommendation/parser/upload suite passed with `29 passed`; full `python -m pytest -q` passed with `138 passed` and the existing three scikit-learn model-version warnings.

## 56. Next production test and intelligence-layer direction - 2026-07-25

- Next step is user-side production testing with real invoices across different categories before adding another feature layer.
- Test invoices should cover printer, phone/laptop, heater/geyser/fan/AC, fridge/TV/appliance and unknown products.
- For each invoice, verify product/brand/model extraction, controlled OEM source discovery, base warranty duration, optional extended-plan separation, evidence status, product-aware care suggestions and absence of fake claim/free-repair promises.
- After those basics are verified, the next global layer should be product-aware behavior questions plus predictive risk updates and OEM aggregate insight.
- Behavior questions should be selected from product category, brand/model, region/location, warranty status, invoice/OCR gaps, user notes, telemetry/events and OEM question-studio signals.
- User answers should feed explainable predictive care signals while remaining separate from legal warranty status.
- OEM value should remain privacy-safe aggregation by product/model/region/date range, with minimum cohort suppression and no individual customer exposure unless explicit direct-sharing consent exists.

## 57. Global product-aware behavior questions - 2026-07-25

- Upgraded the shared `behaviour_questions` service used by `/behaviour/next-question`; this is a global Smart Warranty Hub behavior pipeline fix, not an Epson/printer UI patch.
- Reused the shared product-category inference layer so behavior questions align with printer, phone, laptop, fridge, TV, heater, geyser/water heater, fan, AC, washing machine, microwave, camera, router, wearable, audio, purifier, kitchen appliance, cooler, inverter and appliance categories.
- Added product-specific next questions such as printer dry-ink/nozzle/printhead-cleaning, geyser leak/tripping/hard-water, AC filter/cooling/leakage, fridge unstable cooling/gasket, washer vibration/drain, router restarts and inverter backup/load.
- Question priority is now: missing serial first, real telemetry/risk signals such as voltage or overheating next, product-specific behavior context next, then missing region, usage and environment context.
- Unknown products still fall back to safe generic context; no warranty coverage, claim eligibility or free-repair facts are invented by behavior questions.
- Added regression tests proving printer and geyser receive product-specific questions before generic region context, voltage signals still take priority and unknown products do not get forced into fake categories.
- Verification passed: focused behavior/recommendation/upload suite passed with `26 passed`; full `python -m pytest -q` passed with `141 passed` and the existing three scikit-learn model-version warnings.

## 58. Hybrid OEM-first behavior question refinement - 2026-07-25

- Added a hybrid behavior-question layer in the shared `behaviour_questions` service: confirmed official OEM terms are checked first for concrete care/limit/support signals, then the category fallback is used only when OEM-derived context is unavailable.
- This reuses stored parsed warranty evidence on the warranty record; it does not let the behavior layer browse arbitrary websites.
- OEM-derived question triggers include usage/print limits, printhead/nozzle terms, filter/cartridge care, power/voltage/surge terms, water/leak/moisture terms, cooling/temperature/compressor terms, motor/drum/vibration terms, battery/charging terms and official support-route terms.
- OEM-derived questions are only used when the stored terms source is confirmed as approved/synthetic official evidence or has an HTTP source URL; default/internal/unconfirmed terms fall back to product-category questions.
- Built-in category questions remain the safety fallback for products or OEM pages that do not expose useful care guidance.
- The warranty fact boundary remains unchanged: behavior questions can guide care/risk context, but they do not confirm coverage, claim eligibility or free repair.
- Added regression tests proving official OEM print-limit evidence creates an OEM-derived question and unconfirmed terms do not.
- Verification passed: focused behavior/recommendation/upload suite passed with `25 passed`; full `python -m pytest -q` passed with `143 passed` and the existing three scikit-learn model-version warnings.

## 59. OEM product knowledge cache for RAG reuse - 2026-07-25

- Added `app/services/oem_product_knowledge.py` to create reusable OEM product knowledge cards from confirmed public OEM/synthetic-approved warranty evidence.
- Cards are keyed by brand, model/product and region, for example `oem_product_knowledge:epson:l3250:in`.
- Cards include source URLs, source type, base warranty duration, terms, exclusions and claim/support steps, plus an explicit boundary that no customer invoice or behavior data is included.
- `terms_lookup` now upserts these cards into the RAG document store after controlled manual/auto OEM terms are parsed and cached.
- The product knowledge cache only accepts `approved_oem_source` or `synthetic_approved` source types; default/internal/unconfirmed/scraped records are not promoted into reusable OEM knowledge.
- This gives later users a reusable product-level knowledge asset when RAG is enabled, while the existing terms cache remains the non-vector fallback.
- Added focused tests for card content, rejection of default/unconfirmed terms and RAG upsert metadata without `user_id` or `warranty_id`.
- Verification passed: focused OEM knowledge/behavior/parser/upload suite passed with `35 passed`; full `python -m pytest -q` passed with `146 passed` and the existing three scikit-learn model-version warnings.

## 60. Global OEM extended-plan noise filtering - 2026-07-25

- Fixed the underlying warranty parser so OEM page headings, navigation and marketing snippets do not flood warranty terms as repeated optional extended-plan bullets.
- The parser now keeps base warranty, usage-limit and covered-component facts while rejecting generic service-plan menu text such as activation links, warranty/service plan headings and marketing copy.
- This is global parser behavior for any OEM page, not an Epson-only UI cleanup.
- Live Epson L3250 verification after the fix returns clean terms: `12` months base coverage, `30,000 prints` / `whichever comes first` and printhead coverage, without repeated CoverPlus/service-plan noise.
- Added regression coverage for noisy extended-plan navigation text so future parsers do not reintroduce this problem.
- Verification passed: focused parser/upload/OEM-knowledge suite passed with `27 passed`; full `python -m pytest -q` passed with `147 passed` and the existing three scikit-learn model-version warnings.

## 61. Base warranty summaries exclude optional plan marketing everywhere - 2026-07-26

- Production testing showed fresh Epson L3250 uploads still displayed CoverPlus/service-plan marketing inside `Full warranty text` and `Easy summary`, even though base duration stayed correct at 12 months.
- Fixed the shared parser contract globally: optional extended/service/protection plan text is no longer emitted as base warranty `terms` at all.
- Added `sanitize_base_terms()` and applied it across parsing, terms lookup/cache reuse, fresh invoice pipeline persistence, refresh endpoint persistence, summary prompts, structured summaries, layman summaries and summary API response fields.
- This handles both new uploads and old saved warranties/cache rows created before the cleanup, without deleting user records or stripping OCR, OpenAI/Mistral/RAG, OEM lookup, telemetry, predictive risk, behavior questions or agent wiring.
- Base warranty facts still remain: duration, usage limits such as `30,000 prints`, `whichever comes first`, covered components such as printhead and claim/support steps.
- Optional paid extension marketing such as CoverPlus no longer appears as a current warranty benefit or pro in customer-facing summaries.
- Added regression coverage proving optional-plan-only text does not create warranty terms and stale saved optional-plan terms are filtered from layman summaries.
- Verification passed: focused parser tests passed with `12 passed`; focused invoice/behavior tests passed with `11 passed`; full `pytest -q` passed with `148 passed` and the existing three scikit-learn model-version warnings.

## 62. OEM navigation/menu labels filtered from warranty terms - 2026-07-26

- Production testing after the optional-plan cleanup showed a second noise class: OEM brand/navigation labels such as `About Epson`, `Our Purpose`, `Exceptional People`, `Engineered Precision`, `Environmental Pursuit` and `Enduring Partnerships` appeared under customer-facing warranty terms.
- Root cause: the generic fallback section parser could capture nearby short menu labels after a warranty heading when the OEM page mixed content and navigation text.
- Added a global navigation/marketing term filter inside `warranty_parser.sanitize_base_terms()` so these labels are removed from parser output, cache reuse, saved warranty responses, summaries and layman summaries.
- This is not an Epson-only fix: the filter targets generic OEM site navigation/marketing labels and preserves real warranty facts such as duration, usage limits, covered components, support, claim and repair terms.
- Added regression coverage using the exact noisy label pattern while proving `30,000 prints` and `printhead` terms remain intact.
- Verification passed: focused parser tests passed with `13 passed`; full `pytest -q` passed with `149 passed` and the existing three scikit-learn model-version warnings.

## 63. Global invoice identity hardening - 2026-07-27

- Production testing with a second invoice showed the invoice parser could treat boilerplate/header/spec text as product identity, for example `Original For Recipient` as brand and `IP54` or quantity fragments as model.
- Fixed the shared invoice identity layer globally, not as a one-off for one PDF: boilerplate labels, recipient/buyer/seller headers, OCR/file-error notes, invoice metadata and spec-only fragments are rejected before brand/model/product fields reach warranty lookup.
- Pipe-heavy or table-like invoice item lines are split and scored so the strongest product-bearing segment is preferred while standalone specs such as IP ratings, quantities and rates are not promoted to model codes.
- Product names are cleaned without deleting useful product facts such as `6000 mAh Battery`; unknown brand/model are left missing rather than invented, so OEM lookup stays bounded and unconfirmed terms remain labeled as estimated/default.
- Added the same sanitizer after optional OpenAI invoice enrichment so AI output cannot reintroduce bad identity fields after deterministic parsing.
- Preserved the earlier Epson L3250 pipeline: seller/header handling, Epson brand/model extraction, serial extraction, OEM source lookup, terms/RAG/care behavior and summary flow still pass.
- Added regression coverage for recipient/header/spec misclassification, OCR-note file paths and bad AI enrichment identity fields.
- Verification passed: focused invoice pipeline tests passed with `16 passed`; full `pytest -q` passed with `152 passed` and the existing three scikit-learn model-version warnings.

## 64. Samsung pipe-spec invoice regression - 2026-07-27

- Production testing with an Amazon-style Samsung mobile invoice showed a second global invoice-shape issue: pipe-separated item specs such as `120 Hz`, `6000 mAh`, `IP54`, quantity and `HSN:85171300` can sit on the same line as the real product.
- Fixed the shared invoice parser globally so dotted invoice/order dates such as `01.05.2026` are parsed, `HSN` is not mistaken for `SN`/serial, and Samsung Galaxy model names can produce a real model code such as `M17E` instead of spec fragments.
- The expected parse for the tested shape is now brand `Samsung`, product `Samsung Galaxy M17e 5G Mobile (Vibe Violet, 6GB RAM, 128GB Storage)`, model `M17E`, purchase date `2026-05-01`, invoice number `DEL5-53804`, with no fake serial from HSN.
- This is an invoice-pipeline hardening fix, not a one-invoice database patch. Existing unconfirmed warranty behavior remains unchanged: if no approved OEM source is found, terms stay estimated/not confirmed.
- Verification passed: focused invoice pipeline tests passed with `17 passed`; full `pytest -q` passed with `153 passed` and the existing three scikit-learn model-version warnings.

## 65. Wrapped invoice line-item reconstruction - 2026-07-27

- Production testing showed the Samsung Amazon-style invoice still fell back to generic `Product` / `N/A` after deployment because the real PDF/OCR text wrapped the item description across multiple lines, while the previous regression covered only the easier one-line pipe-separated item row.
- Fixed the shared invoice parser globally by reconstructing logical invoice item rows before identity scoring, joining continuation lines containing model/spec/product fragments while stopping at invoice/order date, shipping, total and tax boundaries.
- The fix is not Samsung-only and does not write forced data into Smart Warranty Hub. It improves the input identity pipeline so any wrapped invoice row can preserve product context before warranty lookup starts.
- Seller extraction now rejects order-number metadata and pure spec fragments so continuation lines such as RAM/storage details are not misclassified as seller names.
- The wrapped Samsung test case now extracts brand `Samsung`, product `Samsung Galaxy M17e 5G Mobile (Vibe Violet, 6GB RAM, 128GB Storage)`, model `M17E`, category `mobile`, purchase date `2026-05-01`, invoice number `DEL5-53804`, and no fake serial from `HSN:85171300`.
- Warranty fact boundaries remain unchanged: better product extraction can trigger controlled OEM lookup, but if an approved official source is not found the app must still show estimated/not confirmed terms.
- Verification passed: focused invoice pipeline tests passed with `18 passed`; full `pytest -q` passed with `154 passed` and the existing three scikit-learn model-version warnings.

## 66. Samsung OEM lookup and saved warranty identity labels - 2026-07-28

- Added a controlled Samsung India official warranty support source to the approved source library so Samsung mobile invoices can trigger OEM lookup from extracted brand/model/product instead of falling straight to default rules.
- Kept `oem_verified.json` empty: Samsung remains approved through OEM domain policy, but it is not elevated to admin-verified trust without explicit admin verification.
- Added category-aware Samsung mobile normalization in `terms_lookup`: Samsung's official warranty page can mix product categories, so mobile/phone lookups now keep one-year mobile warranty facts and reject unrelated 60-month, 5-year and optional-plan terms from other categories.
- This is global Samsung mobile warranty lookup behavior, not tied to one invoice ID. If another Samsung phone invoice extracts brand/category/model, it uses the same controlled source path and same mixed-category guard.
- Added invoice-aware saved warranty labels to `/warranties/list` and the Neo dashboard dropdown: product, invoice number, purchase date, uploaded date/time and expiry are shown when available.
- Dropdown rendering now uses DOM option text instead of string-built HTML, preserving behavior while avoiding label injection issues.
- Added regression tests for Samsung mixed-category official page normalization and saved warranty display labels.
- Verification passed: focused invoice/terms suite passed with `20 passed`; full `pytest -q` passed with `156 passed` and the existing three scikit-learn model-version warnings.

## 67. Controlled OEM deep discovery - 2026-07-28

- Expanded the shared OEM discovery pipeline globally so extracted brand/model/product can search deeper inside approved official domains before falling back to default estimated terms.
- Official-domain search now looks for warranty terms, support/warranty pages, manuals/PDFs, repair/service/claim pages and care/maintenance pages using bounded `site:{domain}` queries.
- Broad web fallback remains controlled by the existing production safety flags; this does not let an agent browse arbitrary websites.
- Candidate source ranking now rewards approved/verified hosts plus model-code, product-token, warranty, support, service, claim, manual/PDF and region signals.
- This is not an Epson-only or Samsung-only patch. Samsung is used in regression tests because it exposed the issue, but the code path is the shared discovery service for any brand with approved domains.
- If the official source is not found or parsing cannot confirm terms, the customer-facing result must still say estimated/not confirmed and must not invent OEM coverage, claim eligibility or free repair.
- Verification passed: focused discovery tests passed with `9 passed`; focused invoice pipeline tests passed with `20 passed` and the existing three scikit-learn model-version warnings.

## 68. Global invoice identity, dropdown and upload fallback hardening - 2026-07-28

- Fixed shared invoice line reconstruction for standalone row numbers followed by wrapped product descriptions, so Amazon/Samsung-style table rows can preserve the real product before HSN, ASIN and spec noise are removed.
- Kept saved warranty selection readable and newest-first: placeholder warranty names now prefer the latest parsed product name when available, while labels continue to show invoice number, bought date, uploaded date/time and expiry.
- Preserved the global controlled OEM lookup gate: when brand plus model/product exists, approved-domain lookup can run even if default coverage exists; without official evidence the UI stays estimated/not confirmed.
- Added a summary fallback so OpenAI/Mistral/template provider errors cannot turn an otherwise successful extraction/upload into an upstream failure.
- This is global pipeline hardening, not a Samsung-only or invoice-only patch; Epson/OEM lookup, RAG, behavior questions, predictive risk, telemetry and agent surfaces remain intact.
- Verification passed: focused invoice pipeline tests passed with `24 passed`; full `pytest -q` passed with `162 passed` and the existing three scikit-learn model-version warnings.

## 69. Address-heavy invoice identity rejection - 2026-07-28

- Production testing showed another global invoice-shape bug: seller/billing/shipping/address blocks could be scored before the real product row, so records could show address text such as `Sattva Horizon, Survey No...` as the product name.
- Fixed the shared invoice parser so address/location/legal/supply blocks are rejected before product identity scoring, even when they contain product-like words elsewhere in the OCR text.
- Added a table-header stripper for OCR-merged rows such as `Description Unit Price ... Samsung Galaxy ...`, so the actual item can still be extracted when invoice table headers and item descriptions are collapsed into one line.
- Preserved wrapped ecommerce invoice extraction and the existing Epson and Samsung OEM lookup paths. This fix improves global invoice identity extraction; it does not hard-code one invoice ID or force Samsung/Epson data into the database.
- Controlled OEM lookup behavior remains bounded: once brand/model/product are extracted, approved official-source lookup can run; if official evidence is not found, the UI must stay estimated/not confirmed.
- Verification passed: focused invoice pipeline tests passed with `26 passed`; full `pytest -q` passed with `164 passed` and the existing three scikit-learn model-version warnings.

## 70. Boundary-aware invoice product signal matching - 2026-07-29

- Continued the shared invoice identity fix after production/context handoff showed one remaining failure class: short product tokens such as `ac`, `tv` and short OEM tokens could still be treated too loosely in product-signal scoring.
- Replaced raw product-term substring checks in the shared ingestion parser with boundary-aware token/phrase matching, so address/seller/header words do not become product candidates merely because they contain product-like letters.
- Applied the safer matching to product-signal detection, line-item scoring and warranty-context detection before OEM lookup starts.
- Added regressions proving address-only text with short-token-looking substrings does not create fake brand/model/product fields, while a real short-token product line such as `LG TV OLED55C4` still extracts brand, model and product correctly.
- Existing controlled OEM lookup behavior remains unchanged: cleaner identity can trigger approved-domain lookup, but warranty facts still require official evidence and must stay estimated/not confirmed when not proven.
- Verification passed: focused invoice pipeline tests passed with `28 passed`; full `pytest -q` passed with `166 passed` and the existing three scikit-learn model-version warnings.

## 71. Login and upload email latency guard - 2026-07-29

- Production testing after deploy showed the login page could appear to take indefinitely after submitting credentials.
- The backend login route had a synchronous sign-in alert email call before returning the redirect; if SMTP is slow or misconfigured, the user-facing login can wait even though credentials are already processed.
- Added a shared `_send_email_later()` helper and moved login alert, signup welcome and product-registered emails to FastAPI background tasks when a background task runner is available.
- This preserves email behavior but removes SMTP from the critical path for login, signup, artifact upload, manual warranty creation and camera capture responses.
- Auth, cookies, CSRF, role routing, upload processing and invoice/OEM extraction behavior are unchanged.
- Verification passed: focused auth/CSRF tests passed with `5 passed`; focused invoice pipeline tests passed with `28 passed`; full `pytest -q` passed with `166 passed` and the existing three scikit-learn model-version warnings.

## 72. Regional OEM source ranking and evidence UI refresh - 2026-07-29

- Production Samsung invoice testing showed two demo-breaking issues: the dashboard could show `Approved OEM source` in the summary header while the full warranty section still showed stale `Not confirmed`, and Samsung India invoices could retain a Samsung US warranty source.
- Fixed the Neo dashboard so the friendly full-warranty view re-renders after the summary/evidence response arrives, keeping top evidence and full-text evidence labels consistent.
- Added regional source scoring in shared OEM discovery: URLs with a different country path such as `/us/` are penalized when the warranty region is `IN`, while `/in/` receives the existing region boost.
- Added regression coverage proving Samsung India warranty pages rank above Samsung US warranty pages for an `IN` invoice.
- Existing source safety remains unchanged: discovery still stays inside approved OEM domains and warranty facts still require official evidence; wrong-region official pages are only deprioritized, not treated as user invoice facts.
- Verification passed: focused discovery/source-trust tests passed with `15 passed`; focused invoice pipeline tests passed with `28 passed`; full `pytest -q` passed with `167 passed` and the existing three scikit-learn model-version warnings.

## 73. OEM support/menu noise cleanup - 2026-07-30

- Production Samsung warranty view still showed OEM webpage navigation/support-menu labels inside exclusions and claim steps, such as `Show More`, `Key links`, `See our latest products`, `Samsung Care+`, `Screen Replacement Price`, product category tabs and FAQ labels.
- Added shared `sanitize_support_items()` in the warranty parser so exclusions and claim steps receive cleanup comparable to base warranty terms.
- Preserved real support routes such as warranty checker, service center, repair status, product registration, contact support and chat support while filtering page chrome/menu noise.
- Applied the sanitizer in both parser finalization and terms-result merge/normalization so single-source and multi-source OEM lookup paths cannot reintroduce the same noise.
- Added regression coverage using the Samsung menu-noise pattern seen in production screenshots.
- Verification passed: focused parser tests passed with `14 passed`; focused invoice/OEM knowledge tests passed with `31 passed`; full `pytest -q` passed with `168 passed` and the existing three scikit-learn model-version warnings.

## 74. Product-aware OEM behavior questions - 2026-07-30

- Production Samsung phone testing showed an OEM-derived behavior prompt asking about filter/cartridge care because the official Samsung warranty text mentioned consumable parts such as filters and lamps.
- Fixed the shared behavior-question engine so OEM-derived prompts are gated by inferred product category before they are shown to the user.
- Printer, purifier, AC, washer and appliance products can still receive filter/cartridge questions when official OEM text supports it, but smartphones now fall back to phone-relevant prompts such as overheating/charging instead of showing printer/purifier maintenance questions.
- Preserved the OEM-first behavior: official source terms can still drive useful questions, but only when the question is relevant to the extracted product category.
- Added regressions proving Samsung phone filter text does not create an OEM filter question, while a purifier with official filter/cartridge guidance still does.
- Verification passed: focused behavior tests passed with `11 passed`; full `pytest -q` passed with `170 passed` and the existing three scikit-learn model-version warnings.

## 75. Dashboard summary/warranty data merge - 2026-07-30

- Production Samsung testing showed a UI mismatch: the top card could show approved OEM source while the `What is covered?` popup and full warranty text still displayed stale `N/A` coverage/expiry and `Not confirmed` evidence from the base warranty payload.
- Added purchase date, expiry date and coverage months to the protected warranty summary response so the frontend can use the same normalized summary fields that drive layman/OEM evidence output.
- Updated the Neo dashboard to merge summary terms, exclusions, claim steps, evidence, source metadata, coverage and status fields back into the displayed warranty object before rendering coverage badges, modals and full warranty text.
- This is a UI/data-consistency fix only; it does not change OEM lookup, invoice extraction, source trust rules or care-question logic.
- Verification passed: full `pytest -q` passed with `170 passed` and the existing three scikit-learn model-version warnings.

## 76. Risk context gaps separated from true issue signals - 2026-07-30

- Production Samsung testing showed `High risk` could be explained with weak context gaps such as new device, light usage and no maintenance recorded, which reads like an unsupported failure claim.
- Updated predictive scoring so missing context/no maintenance/new-device notes are returned as `context_gaps` instead of risk causes.
- If the model score is high but there are no real issue signals such as errors, failures, recalls, expiry pressure, voltage/temperature problems, heavy use or behaviour-risk delta, the displayed risk is capped at medium until stronger evidence appears.
- The Neo dashboard now shows context gaps under `Need more info` while keeping actual risk reasons separate.
- OEM/user questions still help by collecting missing usage, maintenance and support-readiness context, but they no longer imply the product is already high risk.
- Added regressions proving missing context alone does not create high risk, while real error signals can still remain high risk.
- Verification passed: focused predictive tests passed with `13 passed`; full `pytest -q` passed with `172 passed` and the existing three scikit-learn model-version warnings.

## 77. Care suggestion risk wording cleanup - 2026-07-30

- Production Samsung testing showed product care cards still displayed `Risk: HIGH` and copied weak/generic context into care advice, even though the cards are general product-category care suggestions rather than OEM warranty facts.
- Updated product recommendation building so weak context gaps such as new device, light usage and no maintenance recorded are not echoed as risk causes in card descriptions.
- When only context gaps exist, care cards now say more usage context can improve advice instead of implying a proven product issue.
- Updated Neo dashboard card wording from `Risk` to `Care priority`, keeping the suggestions useful without presenting them as a failure diagnosis or OEM coverage claim.
- This preserves OEM warranty facts separately in the coverage/terms panels; care cards remain product-category guidance unless an explicit OEM recommendation source is wired in.
- Verification passed: focused product recommendation tests passed with `4 passed`; full `pytest -q` passed with `173 passed` and the existing three scikit-learn model-version warnings.

## 78. Source-aware OEM-derived care suggestions - 2026-07-30

- Added an OEM-derived care layer ahead of fallback product-category care recommendations.
- Product recommendations now inspect already-extracted warranty `terms`, `exclusions` and `claim_steps` to create safe, source-labeled care cards such as `OEM claim step`, `OEM warranty exclusion`, `OEM warranty term` and `OEM-derived care`.
- Samsung phone examples now turn OEM claim routes into document-readiness care and screen/accidental-damage exclusions into source-labeled protection care, while still keeping generic phone battery/charger tips labeled as general product care.
- Epson printer examples now turn OEM printhead/nozzle/print-count terms into source-labeled printhead/usage-limit care, while preserving existing printer care defaults.
- Recommendation service and Neo dashboard now pass and display `source_label` so users can distinguish OEM-derived guidance from general care.
- This uses only facts already extracted from approved/saved OEM sources; it does not alter OEM scraping, warranty extraction, source trust, risk scoring or invoice parsing.
- Verification passed: focused product recommendation tests passed with `6 passed`; full `pytest -q` passed with `175 passed` and the existing three scikit-learn model-version warnings.

## 79. Unified OEM region validation and care fact pass-through - 2026-07-31

- Production testing showed the right architectural issue: AI/scraping can extract facts from different OEM pages, but deterministic validation must decide whether those facts match the invoice product, region and category before saving/displaying.
- Added global terms-lookup region guards so saved warranty reuse respects `region_code`, preventing one region's prior warranty row from supplying terms for another region.
- Added source URL country-path conflict detection for auto-discovered OEM sources, so a known-region lookup such as `IN` skips conflicting country paths such as `/uk/` before parsing/caching terms.
- Kept the existing Samsung mobile context normalization and expanded it to reject conflicting 24-month/2-year broad terms when the validated mobile context says one-year coverage.
- Fixed the recommendation service pass-through so saved warranty `terms`, `exclusions`, `claim_steps`, `alternatives` and source URL are actually sent into the care recommendation engine; this allows the already-built OEM-derived care layer to show in production.
- Preserved previous invoice extraction, OEM discovery, source trust, risk/context separation, Epson printer handling and Samsung menu-noise cleanup.
- Verification passed: focused OEM/care regressions passed with `9 passed`; full `pytest -q` passed with `177 passed` and the existing three scikit-learn model-version warnings.

## 80. Source-grounded AI warranty extraction guard - 2026-07-31

- Added the first global validation layer for AI/NLP warranty extraction candidates in `warranty_parser`.
- Mistral/AI can still help when OEM page text is messy or the deterministic parser has low confidence, but AI-proposed `duration_months`, `terms`, `exclusions` and `claim_steps` are now merged only when the same fact is grounded in the scraped/OCR source text.
- Unsupported AI facts such as invented coverage months, exclusions or claim steps are rejected before they can be cached, saved to a warranty row, shown as OEM evidence, or reused by care suggestions.
- Supported AI facts still pass through when source text contains matching warranty duration, terms, exclusions or support route language.
- This is global for any invoice/product/OEM source that flows through `parse_terms_from_url`; it is not Samsung-only or Epson-only.
- Preserved previous invoice extraction, approved-domain discovery, region guards, Samsung mobile normalization, Epson printer lookup, source labels, risk/context separation and OEM-derived care behavior.
- Verification passed: focused warranty parser tests passed with `15 passed`; focused invoice pipeline tests passed with `32 passed`; full `pytest -q` passed with `180 passed` and the existing three scikit-learn model-version warnings.

## 81. Upload fallback when initial canonicalization fails - 2026-08-10

- Production testing showed bill upload could fail immediately with `Upload failed: upstream error` before the background invoice/OEM pipeline had a chance to process the artifact.
- Added a narrow upload-route fallback: if synchronous initial canonicalization/persistence fails, the route now creates a minimal placeholder warranty linked to the uploaded artifact and records the failure in `alternatives`.
- The background invoice pipeline still receives the artifact/job and can perform the normal extraction, OEM lookup, source validation, summary and care refresh.
- This preserves existing OCR, invoice identity extraction, OEM source validation, AI grounding, region guards, ownership linking and notification behavior; it only prevents the HTTP upload response from dying on a transient upstream parser/persistence error.
- Added a regression test that forces `canonicalize_artifact` to raise `RuntimeError("upstream error")` and verifies `/artifacts/upload` still returns `200` with a `warranty_id` and `job_id`.
- Verification passed: focused invoice pipeline tests passed with `33 passed`; full `pytest -q` passed with `181 passed` and the existing three scikit-learn model-version warnings.

## 82. Remove conflicting duration bullets after OEM merge - 2026-08-11

- Production Samsung testing showed the canonical coverage field could correctly show `24 months` and expiry `2028-05-01`, while the displayed OEM terms list still included stale/conflicting `12 months` or `one year` bullets from merged scraped text.
- Added duration-aware filtering after terms-result merge so once a final canonical `duration_months` is selected, base coverage bullets that mention a different duration are removed from displayed terms.
- Preserved non-duration OEM facts such as screen-protector exclusions, liquid/moisture exclusions and service/claim routes; this is a display consistency guard, not a change to OEM discovery or upload flow.
- Added a regression test proving a merged 24-month Samsung result does not display 12-month or one-year coverage bullets underneath.
- Verification passed: focused invoice/OEM merge tests passed with `3 passed`; full `pytest -q` passed with `182 passed` and the existing three scikit-learn model-version warnings.

## 83. Wait for invoice pipeline before loading uploaded warranty - 2026-08-11

- Production retesting of the same Samsung/Amazon invoice showed a newly uploaded warranty row could briefly display `Terms: unknown` and `Evidence: Not confirmed` because the Neo dashboard loaded the warranty after a fixed two-second delay while the background invoice/OEM pipeline was still running.
- Updated the Neo dashboard upload flow to poll `GET /jobs/{job_id}` and show step-specific progress such as reading invoice, extracting product details and checking OEM warranty source.
- The dashboard now loads/reloads the warranty only after the job reaches `done` or reports a clear failure, reducing false confusion between a safe placeholder state and the final OEM-enriched result.
- This is a UI timing fix only; it preserves upload fallback, OCR, AI invoice enrichment, OEM lookup, source validation, grounding guards, duration conflict filtering, care suggestions and risk logic.
- Verification passed: full `pytest -q` passed with `182 passed` and the existing three scikit-learn model-version warnings.

## 84. Use invoice region before OEM terms lookup - 2026-08-11

- Production Samsung/Amazon India retesting showed an India phone invoice could still accept a Samsung UK/global phone-support URL whose parsed text contained `60 months` and `Mobile Connected PC` wording.
- Added deterministic India invoice-region inference from GST/tax invoice markers, HSN, CGST/SGST/IGST, place-of-supply, INR, Amazon India and Indian PIN-code clues.
- The invoice pipeline now persists extracted `region_code` onto the warranty before OEM lookup, so existing region guards can reject conflicting country paths such as `/uk/` for an `IN` invoice before parsing, caching or publishing terms.
- Added a Samsung mobile product-context guard so pages/text that clearly refer to `Mobile Connected PC`, notebook PC or note-warranty contexts are skipped for phone warranties even if the region signal is missing or messy.
- Preserved upload fallback, job polling, AI grounding, approved-OEM source validation, saved-cache reuse rules, duration conflict filtering, OEM-derived care suggestions and risk/context wording.
- Verification passed: focused invoice/OEM regressions passed with `4 passed`; full `pytest -q` passed with `184 passed` and the existing three scikit-learn model-version warnings.

## 85. Customer-friendly warranty summary bullets - 2026-08-11

- Production review showed the approved OEM evidence was being preserved correctly, but the easy summary could still display raw scraped OEM fragments such as partial Samsung claim menu text.
- Updated the layman summary layer to transform saved OEM facts into short customer-facing bullets for coverage, manufacturing defects, liquid/moisture exclusions, wear/consumables, unauthorized repair, screen/accidental damage, warranty checker, authorized service route and invoice/model/photo readiness.
- Kept full warranty text and source URL as the evidence layer; only the customer summary wording changed.
- Preserved useful OEM facts such as Epson printhead coverage/limits while avoiding optional plan noise and raw navigation fragments.
- Verification passed: focused summary/recommendation tests passed with `22 passed`; full `pytest -q` passed with `185 passed` and the existing three scikit-learn model-version warnings.

## 86. Product-specific OEM diagnostic question wording - 2026-08-11

- Production review showed OEM diagnostic questions must be globally useful for the customer, not raw OEM wording and not one-off Samsung phone text.
- Added centralized category-aware OEM question templates for usage limits, printhead/nozzle, filter/cartridge, power, water/moisture, cooling, motor/drum, battery/charging and service-route signals.
- Kept deterministic category allow-lists so irrelevant OEM prompts remain blocked, such as filter/cartridge maintenance for smartphones.
- Phone service-route questions now ask for invoice, IMEI/serial, photos and a short issue note; printer usage-limit questions ask about heavy printer use; other categories get product-specific language.
- Verification passed: focused behavior-question tests passed with `15 passed`; full `pytest -q` passed with `187 passed` and the existing three scikit-learn model-version warnings.

## 87. No false risk claims for newly onboarded products - 2026-08-12

- Production testing showed a brand-new Samsung Galaxy M17e (expiry `2027-05-01`, just onboarded, zero usage history) received a customer notification reading `High risk detected - This device shows a high risk of issues. Consider backup or service.`, alongside contradictory `Risk Medium detected` alerts for the same warranty and an 88-item unread badge.
- Root cause was four separate defects, not one:
  1. `score_warranty` always returned LOW/MEDIUM/HIGH. For a newly onboarded product the feature vector is effectively empty (usage 0, errors 0, failures 0, maintenance 0, behaviour defaults 0.5), yet the trained model still emitted a label that was converted directly into a customer failure warning.
  2. The entry #76 medium cap was bypassable. `has_real_risk_signal` matched the bare substring `issue`, so the generic aggregate reasons `OEM issue signals present (avg severity ...)` and `RAG signals show recent issues ...` unlocked HIGH even though neither is evidence about that device. `behaviour_delta > 0.0` also counted, and ordinary moderate usage returns `+0.03`.
  3. `create_notification` dedupes on notification `type`, and `risk_high`/`risk_medium` are different types, so contradictory risk levels accumulated unread for one warranty.
  4. `POST /predictive/score` created a risk notification on every call. The Neo dashboard scores on every load, which is the direct cause of the notification flood.
- Fixes applied:
  - Added `_has_device_evidence()` and a `NO_EVIDENCE_MAX_SCORE = 0.32` floor in `predictive.py`. With no telemetry, usage hours, maintenance, errors/failures or behaviour reasons, the label stays LOW and `Not enough usage history yet to assess risk.` is inserted as the leading `context_gaps` entry.
  - Added `_reason_is_real_risk_signal()` using word-boundary regex matching and an aggregate-reason exclusion list, so cross-product OEM/RAG context can no longer unlock a HIGH claim. Raised the behaviour gate to `BEHAVIOUR_DELTA_RISK_THRESHOLD = 0.10` so normal usage does not defeat the cap while heavy use and usage-with-errors still do.
  - Added `_supersede_stale_risk_notifications()` in `notifications.py` so writing a new `risk_*` level marks prior `risk_*` notifications for that warranty read. Non-risk types such as expiry and onboarding are untouched.
  - Added `_risk_label_changed()` in `main.py` so `/predictive/score` only notifies when the level differs from the latest `RiskSnapshotDB`, and records the new snapshot.
- Deliberately did **not** introduce a new `risk_label` enum value. A new product under full warranty with no reported problems genuinely is low risk, and the existing `context_gaps` field already renders as `Need more info` in the Neo dashboard. No route, response-shape, template or UI-ID change was required.
- Updated the entry #76 test to assert the corrected no-evidence behavior (LOW instead of MEDIUM) and added coverage for the moderate-usage MEDIUM cap, aggregate-reason rejection, risk supersede and non-risk-type preservation.
- Preserved invoice extraction, OEM discovery/region guards, AI grounding, source trust labels, duration conflict filtering, OEM-derived care suggestions, expiry notifications and diagnostics behavior.
- Verification passed: focused predictive tests passed with `17 passed`; focused notification tests passed with `6 passed`; full `pytest -q` passed with `191 passed`.

## 88. Risk uses the shared product category taxonomy - 2026-08-13

- Scope was deliberately limited to the risk lane. OCR, scraping/OEM discovery, AI grounding, terms
  lookup, summary generation, invoice ingestion, canonicalization and care/recommendation logic were
  **not** modified. Verified with `git diff --name-only` against those paths returning empty.
- Live data check first established why region contributed nothing: `regional_policies` had **0 rows**
  and `oem_issue_signals` had **1 row** (whose `product_type` was `NULL`). Of the five documented risk
  lanes, only the model base and telemetry behaviour delta were actually affecting scores.
- Root causes found in the risk lane:
  1. `predictive._product_type_code()` used bare substring matching over a 2-value vocabulary. `"ac" in name`
     matched `"Washing M-ac-hine"`, `"Black"` and `"Compact"`; `"air" in name` matched `"Air Purifier"`.
     A washing machine was therefore encoded as an air conditioner in the model's first feature.
  2. `score_warranty()` passed the raw `product_name` (for example
     `"Samsung Galaxy M17e 5G Mobile (Vibe Violet, 6GB RAM, 128GB Storage)"`) as `product_type` into
     both `evaluate_region_policy()` and `summarize_issue_signals()`. Those rows are keyed by product
     *category*, so a category-scoped rule could never match. Region-by-product risk was impossible.
  3. `regional_policy._match_rule()` failed **open**: `if rule.product_type and product_type and ...`
     skipped the constraint when the warranty's value was missing, so a washing-machine rule would
     apply to any product with an unknown category.
- Fixes applied:
  - Added `predictive.resolve_product_category()` delegating to the existing shared 24-category
    resolver `product_recommendations.infer_product_category()` — the same one already used by care
    suggestions and behaviour questions. No new taxonomy was created and
    `product_recommendations.py` was not modified.
  - `_product_type_code()` now resolves the category first and then narrows to the model's encoding.
    **The trained model was trained with `product_type` in {0, 1, 2} only** (verified in
    `scripts/train_predictive.py` fallback rows), so the vocabulary is deliberately preserved:
    `fridge -> 1.0`, `air_conditioner -> 2.0`, everything else `-> 0.0`. The numeric-passthrough
    branch for already-coded callers is retained. Widening this encoding would feed the model
    out-of-distribution input and requires retraining.
  - Regional policy and OEM issue lookups now receive the resolved category instead of the raw name.
    This is currently behaviour-neutral because `regional_policies` is empty and the single
    `oem_issue_signals` row has a `NULL` product_type, but it makes the region-by-category lane
    usable for the first time.
  - `_match_rule()` now fails closed on brand, model and category. A rule with no narrowing still
    applies region-wide as intended.
- Behavioural effect: washing machines, air purifiers, water purifiers and laptops are no longer
  encoded as air conditioners in the model feature vector. Genuine fridge and AC products still
  encode as before. No route, response shape, template or UI ID changed.
- Added `tests/test_regional_policy_matching.py` (8 tests) covering fail-closed matching, and three
  predictive tests asserting the model vocabulary stays within `{0.0, 1.0, 2.0}`, that substring
  misreads are fixed, and that risk uses the shared taxonomy.
- Verification passed: focused predictive plus regional policy tests passed with `27 passed`; full
  `pytest -q` passed with `201 passed` (was 191; +10 new tests).
- Not done in this task, still open: seeding the region-stressor by category-sensitivity profiles so
  the region lane produces real deltas, and deciding whether RAG should remain a scoring lane at all
  (its current contribution is a keyword scan that cannot distinguish "no failures reported" from
  "multiple failures reported"). The three dead helpers `_peer_review_features()`,
  `_search_features()` and `_nudge_features()` remain uncalled.

## 89. Read-only extraction/discovery audit — measured baseline, no code changed - 2026-08-18

**This entry records measurements only. No application file was modified.** Two throwaway audit
scripts were used and deleted; `git status --short` was empty before and after. Every number below
came from executing the real code paths on this machine, not from reading code.

### 89.1 PaddleOCR has never run — silent fallback, dishonest health check

- `.env` sets `OCR_ENGINE=paddle`. `ocr.health()` reports `(True, 'PaddleOCR available (lazy)')`.
  That report is **wrong**, because `health()` only calls `find_spec("paddleocr")` and never
  initializes the engine.
- Running `extract_text_with_meta()` over the 50 labeled samples in
  `test_data/ingestion_ocr_50_labeled.csv`: method usage was `tesseract_fallback: 40`, `paddle: 10`,
  and **all 10 paddle attempts were failures**. Paddle succeeded zero times.
- Cause is a dependency conflict, not the code: `protobuf 5.29.6` with `paddlepaddle 2.6.2` raises
  `PaddleOCR init failed: Descriptors cannot be created directly`. The Tesseract fallback added by
  the entry noted in section 2 works and is masking this completely.
- The 10 samples that produced **no text at all** were all `case_type=hard_ocr` — skewed/low-quality
  scans. Tesseract also returns nothing for those. So real-world phone photos of crumpled invoices
  are the exact class that currently fails.
- Before pinning protobuf down, check the rest of the venv. A blind downgrade can break other
  packages. Dropping Paddle and standardizing on Tesseract plus a document-AI tier is the other
  valid option.

### 89.2 Measured invoice field accuracy — three fields are at 0%

Real `extract_text_with_meta()` + `extract_product_fields()` over the same 50 samples, exact match
against the CSV ground truth (30 samples carry labels):

| Field | Correct | Wrong | Missing |
|---|---|---|---|
| `brand` | 26/30 (86.7%) | 0 | 4 |
| `product_category` | 26/30 (86.7%) | 0 | 4 |
| `purchase_date` | 24/30 (80.0%) | 6 | 0 |
| `coverage_months` | 16/30 (53.3%) | 14 | 0 |
| `model_code` | **0/30 (0.0%)** | 1 | 29 |
| `serial_no` | **0/30 (0.0%)** | 15 | 15 |
| `invoice_no` | **0/30 (0.0%)** | 0 | 30 |

- `serial_no` is worse than absent: 15 samples wrote the literal value `takinvoice` into the record.
  A confidently wrong serial is more damaging than a blank, because `_update_warranty()` only writes
  truthy values and **never clears a field**, so re-processing cannot remove it.
- Note the contrast with the section 11 KPI table, which records "OCR success 100%, model F1 0.6667"
  for phase 1C. That table does not match what the code does today on the same dataset. Trust these
  numbers; the phase 1C row is stale.

### 89.3 The 27-brand ceiling is the real "any OEM" blocker

- `ingestion._KNOWN_OEMS` contains **27** brands and `_PRODUCT_TERMS` contains **25** words, while
  `data` domain registry loads **197** brands via `load_oem_domains()`.
- `_canonical_oem()` only matches those 27. For any other brand — Havells, IFB, boAt, Ather,
  Crompton, all present in the 197 — `item_brand` is `None`, so brand falls through to the
  "scan the first 5 lines" heuristic and picks up **the retailer or the seller's legal name**.
- That wrong brand then becomes the lookup key for OEM discovery, so the whole downstream chain
  queries the wrong company. Fixing extraction without fixing this does not deliver "any OEM".

### 89.4 Web search is configured but dead; verified-domain registry is empty

- Live check: `_provider_configured()` returned `False` for all five providers (serper, serpapi,
  brave, google, bing). `search_web("samsung galaxy warranty terms")` returned **0 results**.
- Consequence measured through `discover_sources(region="IN")`:
  `Samsung SM-S921B -> 1 source` (curated file only), `LG OLED55C4 -> 0`, `Whirlpool WM8KG -> 0`.
  Zero sources means `DEFAULT_RULES`, i.e. a flat category default presented as coverage.
- `data/warranty_sources.json` holds only **4** entries, and two are `test_data/` synthetic files
  that are correctly skipped because `TERMS_ALLOW_LOCAL_DEV_SOURCES` defaults to false. Effective
  real curated coverage is one Samsung page and one Epson page.
- `load_verified_domains()` returns **0 brands**. The discovery scorer awards `+15` for verified, so
  the strongest trust signal in ranking is switched off. Populating this via `oem_domain_verify` is
  cheap and improves source selection immediately.

### 89.5 `max(durations)` picks the wrong number, and the Samsung hardcode proves it

- Live scrape of the curated `https://www.samsung.com/in/support/warranty/` returned
  `duration_months: 60` with `confidence: 1.0` for what is a mobile-phone warranty page.
- `_merge_terms_results()` uses `max(durations)`, so the longest number on the page wins — usually an
  extended plan or an appliance compressor term, not the product.
- `terms_lookup._normalize_result_for_context()` compensates by hardcoding "if brand starts with
  samsung and category is mobile, force 12 months and drop terms containing `24 months`, `2 years`,
  `coverplus`". `_source_conflicts_product_context()` is the same pattern. These are per-brand
  band-aids over the `max()` defect and should be deleted once duration selection is
  product-scoped (require the duration sentence to sit near the model/category mention).

### 89.6 No LLM is reachable anywhere in the system

- `OPENAI_ENABLED` is unset (defaults to `"0"`), `OPENAI_INVOICE_ENRICHMENT` unset, no
  `OPENAI_API_KEY`, **and the `openai` package is not installed** (`find_spec` returned `None`).
  So the phase 2 lane described in section 0 cannot run even if the flags are flipped.
- `LLM_PROVIDER` defaults to `ollama`, no connector is registered, and `http://localhost:11434`
  refuses the connection. `playwright` is also missing, so `warranty_parser._fetch_headless()` is
  dead and JS-heavy OEM pages cannot be read.
- Net effect: invoice parsing is 100% regex today, and `summarize_warranty` always lands on
  `template_fallback`. The `.env` in this workspace contains only `OCR_ENGINE`,
  `OEM_REFRESH_MINUTES`, `OEM_REVIEW_REQUIRED` and `DISABLE_MODEL_SOURCE_CHECK`.

### 89.7 Duplicate extraction pass

`upload_artifact()` runs `canonicalize_artifact()` → `extract_product_fields()`, which creates the
warranty row. Then `invoice_pipeline.run_job()` runs `extract_product_fields()` **again** on the same
text. OCR runs once (the job only re-OCRs when `len(text) < 200`). The DB row is therefore born from
the pass that has no enrichment applied.

### 89.8 Agreed direction — LLM extracts, regex validates

The root cause across 89.2, 89.3 and 89.5 is one decision: regex is doing the *extracting*. It
cannot generalize over layouts, so every new invoice shape means another pattern in the ~700-line
`ingestion.py` and another brand in a hardcoded tuple. Agreed fix order, honouring rule 5 in
section 1 (deterministic fallbacks stay):

1. Fix OCR (protobuf decision) and make `health()` initialize the engine instead of calling
   `find_spec`. Nothing downstream can work on invoices that yield no text.
2. Install `openai`, set the flags/key, and **add span grounding**: the model must return the exact
   source substring for every field, and any value that does not appear verbatim in the OCR text is
   dropped. This is what kills the `takinvoice` class of error. Make the LLM primary for
   `model_code`/`serial_no`/`invoice_no` (regex scores 0%), keep regex as a validator for format,
   range and plausibility. This is consistent with the entry 80 source-grounding rule.
3. Add one search provider key and populate `verified_domains`.
4. Replace `_KNOWN_OEMS` with a resolver over the 197-brand registry plus an LLM call whose only job
   is brand-vs-seller disambiguation.
5. Replace `max(durations)` with product-scoped, quote-backed duration selection, then delete the
   Samsung hardcodes.
6. Wire `test_data/ingestion_ocr_50_labeled.csv` into CI with a per-field floor. The file already
   exists but nothing enforces it, which is how three fields sat at 0% unnoticed.

Also outstanding: let `_update_warranty()` clear a field when a higher-confidence pass says it is
absent; add per-domain rate limiting and a contact User-Agent before broad OEM fetching (current UA
is `SmartWarrantyHub/1.0` with no contact).

### 89.9 Statement boundary

Nothing in this entry validates business outcomes. It measures extraction and discovery correctness
on a synthetic 50-sample set plus two live OEM fetches. The section 11 external statement still
applies unchanged, and the phase 1C row in that table should be treated as stale until re-measured.

## 90. Work plan — consolidated fix run (started 2026-10-03)

Source: user-approved consolidated work plan, 2026-10-03. Rules for this run: local commits only (no
push), one commit per step, full `pytest -q` after every step, MEMORY.md ticked and committed with
each step, measured numbers only, synthetic results labelled synthetic, no Samsung- or
printer/Epson-specific logic removed. Resume from the first unchecked box.

- [x] Step 0 — Checklist entry, corrected Paddle diagnosis, `.kiro` skill updated.
- [x] Step 1 — Repo hygiene (cookies.txt tracking report, unpushed commits, .gitignore, untrack).
- [x] Step 2 — Regression tests that lock in today's Samsung and printer/Epson outputs.
- [x] Step 3 — Extraction safety (serial fallback, field clearing, duplicate first pass).
- [x] Step 4 — OCR honesty (real health check, logged Paddle errors, engine in metadata, real-image test).
- [x] Step 5 — Truthful docs.
- [x] Step 6 — Honest 50-sample baseline and CI floors.
- [x] Step 7 — Brand registry and domain preflight.
- [x] Step 8 — Product-scoped warranty duration.
- [x] Step 9 — Prepare (not activate) grounded AI extraction.

### 90.0 Corrected Paddle diagnosis (supersedes 89.1 cause)

Re-measured 2026-10-02. The venv no longer matches entry 89.1: installed versions are now
`protobuf 6.33.2`, `paddlepaddle 3.2.2`, `paddleocr 2.8.0`.

- `ocr.get_paddle()` **now initializes successfully** — the protobuf `Descriptors cannot be created
  directly` error is gone.
- Every `run_paddle_ocr()` call fails at inference with
  `NotFoundError: OneDnnContext does not have the input Filter ... [operator < fused_conv2d > error]`.
  Cause: the paddleocr 2.x model files are run on the paddle 3.x CPU/oneDNN runtime — a
  framework/model version mismatch, **not** protobuf.
- `_run_image_ocr()` then falls back to Tesseract and discards the Paddle error, so the failure is
  still silent. `ocr.health()` still reports `(True, 'PaddleOCR available (lazy)')` from `find_spec`.
- Reproduced on `S001.png` and `S002.png`: method `tesseract_fallback`.
- Do not pin protobuf as a fix. Options remain: PaddleOCR 3.x (paddleocr 3 + matching models) in an
  isolated environment, or Tesseract plus a document-AI tier. Decision is the user's.

### 90.y Step log

A commit cannot contain its own hash, so each step's hash is written here by the next step's commit.

| Step | Commit | Tests | Notes |
|---|---|---|---|
| 0 | `d1be48c0` | 201 passed | Entry 90 added; the uncommitted entry 89 audit text was committed with it. |
| 1 | `d24d1f00` | 201 passed | See 90.1. |

### 90.1 Step 1 — repo hygiene (2026-10-03)

- `cookies.txt` is **not tracked** and appears in **no commit on any ref** (`git log --all -- cookies.txt`
  is empty after `git fetch origin`). It was already in `.gitignore`. The file was not opened.
- Unpushed commits after `git fetch origin`: `origin/main..HEAD` = **168 commits** (origin/main is the
  GitHub default branch and is far behind). `origin/master..HEAD` = **1 commit** (Step 0 only); local
  `master` otherwise matches `origin/master`. Nothing was pushed.
- `.gitignore` gained `frontend/node_modules/`, `pytest-cache-files-*/`, `tmp_*.py`, `.env*`
  (`*.log`, `cookies.txt`, `.env` were already present).
- Untracked with `git rm --cached` (local files kept): `frontend/node_modules/` (2,366 files),
  `tmp_fix.py`, `vite-dev.log`. The `pytest-cache-files-*` folders and `cookies.txt` were never tracked.
- Deploy check: the `Dockerfile` does not build the frontend and `frontend/dist` is not tracked, so
  untracking `node_modules` does not affect the image. A fresh clone needs `npm install` in `frontend/`
  to run Vite.
| 2 | `c251e6e0` | 216 passed (+15) | See 90.2. No behaviour change. |

### 90.2 Step 2 — Samsung and printer/Epson logic inventory and lock (2026-10-03)

Inventory of brand- or printer-specific logic (none removed or changed):

| File:line | What it corrects |
|---|---|
| `terms_lookup.py:195` `_looks_like_samsung_mobile_context()` | Detects a samsung.com page in a Samsung + mobile context. |
| `terms_lookup.py:223` `_source_conflicts_product_context()` | Rejects Samsung notebook/PC warranty pages for a mobile product (auto and manual URL paths). |
| `terms_lookup.py:254` `_normalize_result_for_context()` | Forces Samsung mobile to 12 months, drops 24m/2y/60m/5y/CoverPlus/extended/service-plan terms, drops news/alerts/community claim steps, inserts default Samsung claim steps when none remain. Patches the `max(durations)` defect. |
| `warranty_parser.py:38-100` `_EXTENDED_PLAN_*` / `_NAV_MARKETING_REJECT_MARKERS` | CoverPlus, "verify your Epson", "about Epson", "Samsung Care" and similar marketing/extended-plan noise kept out of base terms and duration. |
| `warranty_parser.py:166, 343-352` | Printhead/print head treated as a covered component, not a base duration. |
| `ingestion.py:262, 327-329, 443-445, 653` | Galaxy/printer product-line keywords, Galaxy → mobile, printer category, Galaxy model code (e.g. `M17E`). |
| `oem_adapters.py:58` | Samsung-only approved adapter (`samsung.com`, `samsungmobile.com`). |
| `oem_parsers.py:29, 65` | Samsung compressor/panel/digital-inverter cues and CSS selectors. |
| `product_recommendations.py:53-57, 185, 197, 279-282` | Printer care items, printer/phone category detection (`ecotank`, `galaxy`, `sm-`), OEM printhead/filter care. |
| `behaviour_questions.py:28-31, 139-141, 200-206, 244-245` | Printer questions; printhead/filter prompts gated by category (filter blocked for phones). |
| `summary_engine.py:343` | Printhead coverage bullet. |
| `recommendation.py:80` | Galaxy/`sm-` → phone. |
| `data/warranty_sources.json` | The only two real curated sources: Samsung India warranty page, Epson L3250 India product page. |

- Live capture 2026-10-02 (`parse_terms_from_url`, one fetch each): Samsung India page → **60 months,
  confidence 1.0**, 7 terms, 5 exclusions, 6 claim steps. Epson L3250 page → **12 months, confidence
  0.8**, 3 terms, 0 exclusions, 5 claim steps. Stored without raw_text as
  `tests/fixtures/oem_terms_captured_2026-10-02.json`.
- New `tests/test_regression_samsung_epson_lock.py` (15 tests) runs `lookup_terms()` end to end with
  network mocked and locks: Samsung IN → 12 months, exact terms/exclusions/claim steps, source
  `approved_oem_source`; US Samsung source skipped for region IN; Samsung notebook page rejected
  (auto → `internal://default_rules`, manual → `internal://manual_url_product_context_conflict`);
  normalisation only for Samsung + mobile + samsung.com; Epson L3250 → 12 months, printhead and
  30,000-prints terms, exact claim steps, `approved_oem_source`; CoverPlus never sets duration;
  summary wording; Samsung adapter domains; category normalisation.
- Already covered before this step (left as is): Samsung Galaxy M17e invoice parsing
  (`test_invoice_pipeline.py:286-350`), Epson L3250 invoice parsing (`:233`), printer/phone question
  gating (`test_phase5_behaviour_predictive.py:95-221`), printer care (`test_product_recommendations.py`).
| 3 | `5f8686d2` | 243 passed (+27) | See 90.3. |

### 90.3 Step 3 — extraction safety (2026-10-03)

- `ingestion._serial_from_lines()` now returns `(serial, confidence)`:
  - Labelled: value on the same line as `serial`/`s/n`/`sn`/`imei` (optionally `no`/`number`/`#`), or on
    the next non-empty line when the label stands alone → confidence 0.7. OCR label variants
    (`seri` + up to 3 chars, e.g. `seriat`, `seria:`, `seri`; `series` excluded) → confidence 0.5.
  - Value must be 6-24 chars, contain a letter **and** a digit, must not be a date, and must not
    contain invoice-header fragments (`INVOIC`, `NVOICE`, `RECEIPT`, `BILL`, `CUSTOMER`, `ORIGINAL`,
    `DUPLICATE`, `TOTAL`). Otherwise blank.
  - **Deviation from the plan wording, needs a decision:** a strict "label only" rule would blank the real
    Epson L3250 invoice serial `XAHT699208` (unlabelled, on the line directly under the item row), which
    the existing entry 63 production regression test locks. Kept a narrowed unlabelled fallback: only the
    single line directly under a numbered line-item row, letters+digits, 8-18 chars, header fragments
    rejected, confidence 0.5. Previously it scanned 3 lines after any chosen "product line" (which was
    the retailer header on S001) and accepted letters-only tokens.
- Measured on S001-S012 Tesseract OCR text (synthetic images; fixture `tests/fixtures/ocr_text_S001_S012.json`):
  `TAKINVOICE` written as serial **8/12 before → 0/12 after**. All 12 now take the value from the
  `seriat`/`seria:`/`seri` label line with confidence 0.5. Exact serial match is still **0/12**, because
  Tesseract reads `0` as `O` (e.g. `SNO01X1001` vs truth `SN001X1001`). Paddle did not run (still fails, 90.0).
- `invoice_pipeline._update_warranty(db, id, fields, confidence=None, alternatives=None, absent_confidence=0.8)`:
  when the pass confidence is supplied (the pipeline always supplies it now), a stored `brand`/`model_code`/
  `serial_no` that the pass did not find is cleared if its stored confidence is < 0.8 (regex guesses are
  0.4-0.85; user overrides via `/warranties/from-artifact` are 0.9 and are never cleared). Pass confidences
  are written to `warranty.confidence`, extraction alternatives are merged into `warranty.alternatives`,
  and cleared fields are listed in `alternatives["cleared_on_reprocess"]`. Legacy calls without
  confidence never clear. Note: brand found by the line-item OEM match (0.85) is not cleared by absence.
- Duplicate first pass removed: `/artifacts/upload` and `/artifacts/capture` no longer call
  `canonicalize_artifact()`. They create a placeholder row (`_placeholder_upload_warranty`, product name
  `Product`, `terms_source_type=invoice_only`) and the pipeline job is the only extraction. The old
  `_minimal_upload_warranty` error fallback is gone because there is no first pass left to fail.
  `/warranties/from-artifact` (manual create with overrides, no pipeline job) still uses `canonicalize_artifact`.
- `run_initial_analysis_and_notifications` now runs **after** the job (as a second background task, or
  synchronously after `run_job` when no task runner) so onboarding/risk/expiry notifications see the
  extracted fields rather than the placeholder. `/artifacts/capture` now also runs the job synchronously
  when no background runner exists (it previously skipped it).
- Tests: new `tests/test_extraction_safety.py` (26 tests: 12 OCR samples, label/blank cases, Epson
  fallback, clear-on-reprocess, override kept). `test_upload_returns_warranty_when_initial_canonicalization_fails`
  was rewritten as `test_upload_runs_extraction_once_in_pipeline` (asserts exactly one extraction call,
  job `done`, brand `Epson`).
| 4 | `c12105b5` | 249 passed (+6) | See 90.4. OCR engine unchanged. |

### 90.4 Step 4 — OCR honesty (2026-10-03)

- `ocr.health_report()` (new) and `ocr.health()` now **run real OCR** on the bundled 2.5 KB image
  `app/assets/ocr_health_check.png` ("OCR 2468") and require the token `2468` in the output. Paddle is
  probed when it is the configured engine, Tesseract always. `ok` is True only when the **configured**
  engine reads the image; `active_engine` says what will actually be used. Result cached
  `OCR_HEALTH_TTL_SEC` (default 600 s). `/health/ocr` now returns the full report
  (`ok`, `detail`, `configured_engine`, `active_engine`, `engines`); `/health/full` keeps `{ok, detail}`.
- Measured on this machine: `ok=False`, `active_engine=tesseract`, detail
  `PaddleOCR failed: NotFoundError: OneDnnContext does not have the input Filter. [operator < fused_conv2d > error]; Tesseract fallback read the test image`.
  Latency: cold 6.8 s (Paddle init), forced warm 0.3 s, cached ~0 ms. Before this step the same
  endpoint reported `ok=True, "PaddleOCR available (lazy)"`.
- `_run_image_ocr_with_meta()` (new; `_run_image_ocr()` kept as a wrapper) logs the Paddle error at WARNING
  (`app.services.ocr`) and returns `{"method", "engine", "paddle_error"}`; `_short_error()` reduces the
  Paddle traceback to its decisive line. `extract_text_with_meta()` meta now always carries `engine`
  (`pdf`, `paddle`, `tesseract`, `text`, `docx`, or None when nothing produced text) plus `paddle_error`
  when Paddle failed. PDF page OCR reports its engine too.
- Engine travels with the upload: `Artifact.ocr_meta` (in memory only, `{method, engine, paddle_failed}`;
  the raw Paddle error is not exposed in API responses) is set by `ingest_artifact()`, and the pipeline
  writes it to `warranty.alternatives["ocr"]` (or its own re-OCR meta when it re-OCRs short text).
- Tests: new `tests/test_ocr_integration.py` (6). `test_real_image_ocr_pipeline_extracts_fields` runs
  **real OCR on `S001.png`** (synthetic image) through `ingest_artifact` → placeholder → `run_job` and
  asserts brand `Apple`, purchase date `2025-01-06`, serial not `TAKINVOICE` and in
  {blank, `SN001X1001`, `SNO01X1001`}, and the recorded engine. Only OEM terms lookup and domain
  verification are mocked (network). Skips if Tesseract is not installed. On S001 today the pipeline also
  stores product name `�Apple Authorized Store` (retailer header — wrong), coverage `38` (truth 36,
  OCR digit error), no model code, no invoice number; not asserted, measured in Step 6.
| 5 | `8d788085` | 249 passed | See 90.5. Docs only. |

### 90.5 Step 5 — truthful docs (2026-10-03)

- Partner KPI values (39.29% / 26.04% / 2.6% / 20.4%) and "4/4 partner KPIs passing" removed from
  `README.md` and `docs/INVESTOR_DEMO_KPI_BASELINE.md`; both now say partner KPIs are **not yet measured**
  and why (`eval_partner_kpi_phase10a.py` draws baseline and "with SWH" values from `random.Random(101)`
  multipliers and imports no `app` code). `data/partner_kpi_phase10a_eval_50.json` and the script are
  unchanged.
- "100% OCR success" / F1 claims relabelled "selectable-text PDFs only; image OCR not yet measured" in
  `README.md`, `INVESTOR_DEMO_KPI_BASELINE.md` (OCR serial 0.925 row dropped, refinement item 1 rewritten),
  `kpi_master_scorecard.md`, `complete_product_specification_and_kpi.md`, `ingestion_ocr_kpi_runbook.md`,
  `COMPLETE_ARCHITECTURE_AUDIT.md`.
- Predictive accuracy marked "unverified after scoring changes in MEMORY.md entries 87-88" in the same
  files plus `predictive_phase4_runbook.md`.
- README test count `122` → `249 passed` (2026-10-03).
- Top-of-file disclaimer "Synthetic/controlled results - not production evidence." added to
  `kpi_master_scorecard.md` and `complete_product_specification_and_kpi.md`.
- Not changed (outside the listed scope): the 100% rows of other phase runbooks (nip/service/oem/kpi
  phases), which already carry a synthetic note; the MEMORY.md section 11 table and entries ~914/925
  (historical log — superseded by this entry).
| 6 | `851d734b` | 251 passed (+2) | See 90.6. |

### 90.6 Step 6 — honest image-OCR baseline and CI floors (2026-10-03)

Measured with `scripts/measure_invoice_fields.py` (new): real `extract_text_with_meta()` on each image of
`test_data/ingestion_ocr_50_labeled.csv` → `extract_product_fields()` (includes identity sanitisation;
AI enrichment off). Exact match after case/whitespace normalisation, dates to ISO. **All samples are
synthetic images.** Runtime 33 s.

- Engines: configured Paddle produced text on **0/50** images. 40 → `tesseract_fallback`; 10 (`hard_ocr`)
  → no text from either engine.
- `normal` case, 30 labelled images (correct / wrong / missing):

| Field | Correct | Wrong | Missing |
|---|---|---|---|
| `brand` | 26 (86.7%) | 0 | 4 |
| `product_category` | 26 (86.7%) | 0 | 4 |
| `purchase_date` | 24 (80.0%) | 6 | 0 |
| `coverage_months` | 16 (53.3%) | 14 | 0 |
| `model_code` | 0 (0.0%) | 1 | 29 |
| `serial_no` | 0 (0.0%) | 30 | 0 |
| `invoice_no` | 0 (0.0%) | 0 | 30 |

- `hard_ocr` case, 10 labelled images: every field missing (no OCR text).
- `non_warranty` case, 10 bills: 0 fields extracted (no false positives).
- Same as entry 89.2 for every field except `serial_no`. Scoring the same cached OCR text with the
  pre-Step-3 code (`c251e6e0`, temporary worktree, removed): serial was 15 wrong (all `TAKINVOICE`) +
  15 missing; now 0 `TAKINVOICE` but **30 wrong** — the 15 previously blank samples now store the
  OCR-garbled value from the `seriat` label line (e.g. `SNO01X1001` for `SN001X1001`) at confidence 0.5.
  Per the plan's rule ("allow OCR variants like seriat") these are accepted; see open questions.
- CI floors: `tests/test_invoice_field_floors.py` — fails if any `normal` field's correct count drops
  below the table, any wrong count rises above it, `TAKINVOICE` reappears, or a non-warranty bill yields
  a field. Runs on the captured OCR text (`tests/fixtures/ocr_text_50.json`, deterministic) and again
  with real OCR when Tesseract is installed (~30 s; Docker image has `tesseract-ocr`).
| 7 | `210da634` | 271 passed (+20) | See 90.7. |

### 90.7 Step 7 — brand registry and domain preflight (2026-10-03)

**How a domain becomes "verified" today.**
- `warranty_discovery._preflight_domains(brand)` takes verified domains + registry domains for the brand
  (max `TERMS_PREFLIGHT_MAX_DOMAINS`=4) and keeps those `_domain_alive()`: DNS resolves and an HTTPS (then
  HTTP) GET returns status < 500 within `TERMS_PREFLIGHT_TIMEOUT_SEC`=4 s. Alive is **not** verified; it
  only gates `site:` searches.
- `oem_domain_verify._verify_domain(brand, domain)` = GET `https://<domain>` with UA `SmartWarrantyHub/1.0`,
  status < 400, then the **first 6,000 characters** of HTML must contain the brand name (case-insensitive
  substring) and one of `warranty|support|service|manual|register|terms`. Pass → `verify_or_suggest()`
  appends it to `data/oem_verified.json` (the only writer). With no domain given it searches the web
  (`search_web`, no provider configured → no candidates) — this is what the pipeline calls on every
  upload (`OEM_AUTO_VERIFY` default true), which is why the list is still `{}`.

**Read-only preflight of the registry** (`scripts/preflight_oem_registry.py`, report
`data/oem_domain_preflight_2026-10-03.json`, 265 s, 4 parallel, ≤3 requests/domain, 0.5 s pauses;
`data/oem_verified.json` checksum unchanged):
- 197 brands / 227 domains. Alive: **204/227 domains, 183/197 brands**. Would pass `_verify_domain`:
  **33 domains, 32 brands**.
- Domain reasons: `verified` 33, `keywords_not_found` 86, `brand_not_found` 50, `unreachable` (alive but
  homepage status ≥ 400 or fetch error, mostly bot-blocking of the bare UA: lg.com, sony.com, dell.com,
  panasonic.com, whirlpool.com, godrej.com, atherenergy.com...) 35, `not_alive` 23.
- The verifier is structurally weak: samsung.com, apple.com, lenovo.com, oneplus.com... fail because the
  first 6 KB of modern homepages is `<head>`/script, not visible text. Changing the verifier is not in the plan.
- Brands with no alive domain (14): Acer (+India), Prestige, Sansui (+India), Glen, Khaitan, Khaitan Fans,
  Polar, Kelvinator, Hisense India, JBL (+India), Harman Kardon. Registry data bug: Kia lists
  `kia.com/in` (a path) as a domain.
- India signals: **30 brands with a `.in` domain** (Amaron, BPL, Bajaj Finserv, Cello, Crompton(+Greaves),
  Daikin, Epson, Fastrack, Havells Lloyd, Hyundai(+India), Kenstar, Kent, Kia(+India), Lloyd, MG(+Motor
  India), Morphy Richards, Pigeon, Preethi, Surya, Syska, Titan, V-Guard, Vidiem, iBall(+India), pTron);
  **45 more brands with only an India path** (`https://<domain>/in/` < 400 and stays on /in): 29 domains —
  apple, asus, belkin, byd, fitbit, haier, hitachiaircon, honor, hp, hplindia, hyundai, inalsaappliances,
  iqoo, kenmore, kia, lenovo, mi, oneplus, oppo, philips, realme, samsung, store.google, symphonylimited,
  tatamotors, tcl, tecnomobile, vivo, xiaomi.

**`_KNOWN_OEMS` replaced** by `app/services/brand_registry.py` over `data/oem_domains.json`:
- `" India"` duplicates and case duplicates collapse; longest multi-word name wins; tiny alias map
  (`mi`→Xiaomi, `one plus`, `i phone`); ordinary-word / 2-letter names (`AMBIGUOUS`: Nothing, Carrier,
  Sharp, Hero, HP, LG, Tata...) match only in Title Case/ALL CAPS and not as a field label (`Carrier:`);
  `RETAILERS` (Croma) never resolve as manufacturer from a seller line.
- Seller-vs-brand in `ingestion.py`: shop/seller lines (store, retail, mall, dealer, Pvt/Ltd/LLP, traders,
  digital...) are no longer product-line candidates; the "first 5 lines" brand fallback skips them; a
  registry brand named only in a shop line ("LG Authorized Store") is used at confidence 0.7; a labelled
  `Brand:` wins if it resolves to the registry, otherwise the shop-line registry brand beats an
  unresolved (OCR-garbled) label.
- Registry gained the three tuple brands it lacked: **Brother** (`brother.com`; `brother.in` not alive),
  **Canon** (`canon.co.in`, `canon.com`), **Dyson** (`dyson.in`, `dyson.com`) → 200 brands.
- Behaviour change worth knowing: `Mi` now resolves to `Xiaomi`; `OnePlus` keeps registry casing (was
  `Oneplus`); S001's product name is no longer the retailer header `Apple Authorized Store`.

**Measured change:**
- 50-sample real-OCR re-run (synthetic images, same engines: 40 tesseract_fallback, 10 no text):
  identical to 90.6 except **model_code 0 → 2 correct** (27 missing, 1 wrong). Brand stays 26/30 — the 4
  misses are OCR reading `LG` as `Lc`; all brands in this set except Ather/Tata were already in the tuple,
  so this set cannot show the registry gain. Floor raised to model_code ≥ 2.
- 8 synthetic invoices for brands outside the old tuple, each headed by a retailer
  (`tests/test_brand_registry.py`): brand correct **2/8 before → 8/8 after**; seller name stored as brand
  **4/8 → 0/8** (Sri Lakshmi Electronics, Poorvika Mobiles, Ather Space Koramangala, Sangeetha Mobiles);
  no brand 2/8 → 0/8. New tests: 20.
| 8 | `060fc91e` | 283 passed (+12) | See 90.8. All Step 2 locks pass unchanged. |

### 90.8 Step 8 — product-scoped warranty duration (2026-10-03)

- `max(durations)` removed from `terms_lookup._merge_terms_results()`. New
  `app/services/duration_selection.py::select_duration(results, DurationContext)` picks the duration
  from a **sentence**, not a page number. A sentence qualifies only if it: has base-warranty wording
  (warranty/guarantee/coverage, or a "<product> - N months" row naming the product); is not an
  extended/optional/additional/Care+/paid plan (those go to `TermsResult.optional_plan_terms`); is not an
  installation/demo/exchange period; is not a component/part-only warranty; does not name a different
  product family than the lookup (watches/buds/TV/accessory rows for a phone); does not name another
  country than the lookup region; and its source mentions the product family, model or category
  (waived for a manual URL the user chose). Ranking: names the exact model (+5) > names the product
  family (+3), strong base wording (+2), then the value most qualifying sentences agree on, then the
  higher-ranked source. The evidence sentence + URL is returned as `TermsResult.duration_evidence`.
  No qualifying sentence → duration left blank (and the parser's echo line "Standard coverage for N
  months" is dropped), except a source with no duration sentences at all falls back to its parser value.
  Callers without context (legacy) get the highest-ranked source's value, not the maximum.
- Parser: `ParsedTerms.duration_candidates` (every duration sentence on the page, full text, not the 4 KB
  `raw_text`) via new `warranty_parser.duration_candidates()`, which reads 3-digit months and number
  words. The legacy `ParsedTerms.duration_months` (page maximum) is unchanged and only used as the
  no-evidence fallback.
- Measured on the live Samsung India page (saved HTML from 2026-10-03, phone context
  `SM-M175E / Samsung Galaxy M17e 5G Mobile / IN`): legacy page max **60**; 34 duration candidates;
  selected **12** from "The limited warranty period of 1 year will apply, regardless of the warranty
  period of the country where the product was first sold."; 1 optional-plan sentence separated
  ("3 Year Warranty (1 Year Standard + 2 Year additional ... TV Models)"). The same generic sentence
  also wins for TV, refrigerator and watch contexts (12) — it is page-level evidence, not
  product-specific; the page has no phone-specific duration row.
- Defects found in the legacy parser (not changed; only bypassed by the selector):
  `_YEAR_RE`/`_MONTH_RE` capture 1-2 digits, so "120 months" → 20 and "240 months" → 40; `_sentences()`
  strips leading digits as bullet numbers, so "60 months (only Part warranty)" loses its number. On the
  live page the old 60 came from "...60 months (Only part warranty)" via the `�`-prefixed rows.
- **Samsung patch redundancy** (not removed). Ran the Step 2 locks and invoice-pipeline Samsung tests with
  both patches disabled:
  - `_normalize_result_for_context()` — the **duration force to 12 is now redundant**: duration stays 12
    on the fixture and on the live page without it. Its term filter (drops 24m/2y/60m/5y/CoverPlus/
    extended lines and e.g. "In case of defect arising out of installation ...") and its default Samsung
    claim steps / news-alerts-community claim filter are **not** redundant (the exact-terms lock fails
    without them).
  - `_looks_like_samsung_mobile_context()` — only gates the function above; still needed while that is.
  - `_source_conflicts_product_context()` (notebook/PC page for a mobile) — duration side is redundant
    (the notebook "24 months" sentence is rejected as another product family → no wrong 24), but it is
    **not** redundant overall: without it the notebook page's terms/exclusions/claim steps are merged,
    the source becomes the PC page instead of default rules, and duration is blank instead of 12.
- Tests: new `tests/test_duration_selection.py` (12, synthetic multi-product page). All 15 Step 2
  Samsung/Epson locks and the existing merge/lookup tests pass unchanged.
| 9 | commit titled "Step 9: ..." (cannot self-reference; next entry records it) | 299 passed (+16) | See 90.9. Flag off; no key or provider enabled. |

### 90.9 Step 9 — grounded AI extraction, prepared and OFF (2026-10-03)

- New `app/services/grounded_extraction.py`, flag `GROUNDED_AI_EXTRACTION` (default `0`). When on, the
  provider (default: the existing optional OpenAI lane, which still needs `OPENAI_ENABLED=1` +
  `OPENAI_API_KEY`; neither is set, `openai` package still not installed) returns
  `{value, source_line, confidence}` for `model_code`, `serial_no`, `invoice_no`.
- Validation (`validate_ai_fields`) keeps a value only if the source line is verbatim in the text sent,
  the value is in that line and in the original OCR text, confidence ≥ `GROUNDED_AI_MIN_CONFIDENCE`
  (0.5), and plausibility passes: serial = letters+digits (`_plausible_serial`) or a Luhn-valid 15-digit
  IMEI; invoice number has a digit and is not a date, HSN/SAC code, GSTIN or phone number; model code has
  a digit and is not a date, HSN/SAC or spec fragment. Accepted values overlay the regex values (capped
  at 0.9 confidence); rejected/absent → regex value or blank. Accepted/rejected reasons and redaction
  counts go to `alternatives["grounded_ai"]`.
- Redaction (`redact_invoice_text`) before anything leaves the machine: `Bill to / Ship to / Buyer /
  Customer / Name / Address` blocks (label line + up to 4 following lines, stopping at invoice/product
  lines), any address-like line (`ingestion._looks_like_address_text`), Indian mobile/landline numbers,
  e-mail addresses, PIN codes on PIN/postal lines. Also applied to the **existing**
  `openai_intelligence.enrich_invoice_fields()` prompt (still off by default) — it previously sent raw
  invoice text. Trade-off: all address-like lines are redacted, including the seller's; on merged-column
  PDF text a seller-address line can carry the invoice number and date (e.g. the Epson "SHOP NO-1 ...
  TPM/4313/25-26 1-Jul-25" line), which the AI then cannot see.
- Wired into `invoice_pipeline.run_job` after identity sanitisation; a no-op while the flag is off
  (pipeline test asserts the provider is never called with the flag unset).
- Tests: new `tests/test_grounded_extraction.py` (16, all AI responses mocked, synthetic invoice with
  fictitious customer): flag default off; redaction removes name/address/phone/e-mail and keeps
  invoice no/model/IMEI/HSN; provider sees only redacted text; grounded values accepted;
  **hallucination**: invoice without a serial + AI-invented serial (invented source line, or real line
  without the value) → serial blank; AI-reported absence stays blank; date/HSN/bad-IMEI/header/low
  confidence/GSTIN rejected; pipeline uses AI values only with the flag on; existing enrichment prompt
  redacted.
- Side finding: `brand_registry` matches "MG Road" (address) as brand `MG` (ambiguous name in capitals).
  Harmless in ingestion today because address detection runs first; noted.

### 90.10 Final state of this run (2026-10-03)

All nine steps done; nothing pushed. Test suite 201 → **299 passed** (1 Paddle ccache warning).
Awaiting user decisions: OCR engine (PaddleOCR 3.x isolated env vs Tesseract + document AI), AI
provider and key, pushing to GitHub, merging the two risk scorers, removing redundant Samsung patches,
and the open questions below.

### 90.x Open questions

- `.kiro/skills/swh-extraction-audit/SKILL.md` is untracked. It was updated in Step 0 but left
  untracked, because adding `.kiro/` to the repo was not explicitly requested.
- Live Epson parse contains U+FFFD (`Epson�s warranty includes ...`): the page is decoded with the
  wrong charset somewhere in `parse_terms_from_url`. Not locked as an exact string; fix not in plan.
- `oem_parsers.parse_oem_text()` Samsung/LG/Bosch/Whirlpool part-warranty regexes use `\s*:?(\d+)`, so
  `"Compressor warranty: 10 years"` (space after colon) is not matched. Not in plan; not changed.
- `terms_lookup._normalize_category()` checks `"ev"` before `"device"`, so any category containing
  `device` (e.g. "electronic device") normalises to `ev` → 36-month default. Not in plan; not changed.
- `_normalize_category("printer")` returns `general`, not `electronics`; the curated Epson source is
  stored as `electronics`. Behaviour today is 12 months either way.
- Step 3 deviation: keep or drop the narrowed unlabelled serial fallback (see 90.3)? Dropping it blanks
  the Epson L3250 production invoice serial and requires changing the entry 63 test.
- Serial values read next to an OCR-variant label (`seriat`, confidence 0.5) are garbled on all 30
  synthetic `normal` images (30 wrong, 0 correct). Should values from OCR-variant labels be left blank
  (giving 0 wrong / 30 missing) until OCR improves? Kept per plan wording for now.
- `_verify_domain` only reads 6 KB of homepage HTML and uses a bare UA, so 165/197 brands cannot verify
  even with a search provider. Fix the verifier (visible text, warranty page probe, contact UA) before
  populating `oem_verified.json`? Not in plan; nothing written.
- Registry entry `Kia: kia.com/in` is a path, not a domain.
- Legacy parser defects (90.8): `_YEAR_RE`/`_MONTH_RE` 1-2 digit capture, `_sentences()` stripping leading
  digits. The selector bypasses them for lookup duration; other users of `ParsedTerms.duration_months`
  and of `_sentences()` still see them. Fix in a later step?
- Remove the now-redundant Samsung duration force (user decision, per plan).
- Grounded AI redaction removes seller address lines too; acceptable, or limit to customer blocks?
- `brand_registry`: "MG Road" → brand `MG`. Add road/street context to the ambiguity rule?

## 91. Full fix run (started 2026-10-03)

Rules: one local commit per step, full `pytest -q` after each, MEMORY updated each step, measured
numbers only, never print/log/commit secret values, do not change Railway settings, **do not push**
until the user approves at the end. Resume from the first unchecked box.

- [x] A  Production check (this section).
- [x] B1 Redaction before any text/image reaches any AI provider (buyer details only, token masking).
- [x] B2 OCR: skip failed Paddle for OCR_ENGINE_TTL_SEC; Tesseract eng in build; Playwright decision.
- [x] B3 RAG out of the risk score; fix "no failures" vs "multiple failures" bug.
- [x] B4 Insecure-settings warning on the admin health page.
- [x] B5 Serial from misread labels → unconfirmed suggestion confirmed in UI (keep Epson exception).
- [x] B6 Bugs: MG Road→MG, device→EV 36m, 120 months→20, Epson broken chars, kia.com/in.
- [x] B7 Remove only the redundant Samsung 12-month forcing.
- [x] B8 New domain verification; write passing domains to verified list.
- [x] B9 One risk scorer (ML; heuristic fallback inside; nudge features).
- [x] B10 AI vision tier for low-text images (redacted image, quoted lines, needs confirmation).
- [x] B11 Expiry recalculation never triggers notifications/emails; count affected records.
- [x] C  Real measurement — SKIPPED: no API keys in local `.env` or shell (checked names only:
       `.env` has OCR_ENGINE, OEM_REFRESH_MINUTES, OEM_REVIEW_REQUIRED, DISABLE_MODEL_SOURCE_CHECK).
- [x] D  Production-like local run of full journeys, then stop and ask before pushing.

### 91.A Production check (names only; values unknown and not requested)

**Deploy files.** Railway builds the `Dockerfile` (no railway.json/nixpacks/Procfile in repo):
`python:3.11-slim-bookworm`, apt installs `tesseract-ocr` (Debian package depends on
`tesseract-ocr-eng`), `poppler-utils`, `libgl1`; `pip install -r requirements.txt`; start command
`python run_app.py` → single uvicorn process on `$PORT`.
- Tesseract: **installed**. Paddle: `paddleocr==2.8.0` + **unpinned** `paddlepaddle` → a fresh build pulls
  paddle 3.x, the same framework/model mismatch measured locally (90.0), so Paddle almost certainly fails
  at inference in production and falls back to Tesseract. Playwright: **not installed** (`HEADLESS_SCRAPE`
  path dead). `openai>=1,<2` **is** installed in production (unlike the local venv).
- Live site branch (evidence, not Railway settings): commit `3598c910 Trigger Railway redeploy` exists only
  on `origin/master`; `origin/main` is 167 commits behind (last 2026-02-09). Production most likely
  deploys from **master** at `bf7e1ee1` — i.e. none of entry 90/91 is live.

**Variable map** (production name → code reader, default when unset):
- Auth/admin: `ADMIN_USER`/`ADMIN_PASS` deps.py:159-160, main.py:1295 (None → insecure defaults only if
  allowed); `JWT_SECRET` deps.py:22, `JWT_SALT` deps.py:31 (None); `ALLOW_INSECURE_DEFAULTS`
  runtime_safety.py:23 (None); `ALLOWED_HOSTS` main.py:415 ('').
- Cookies: `COOKIE_SECURE` main.py:1437 (None), `COOKIE_SAMESITE` main.py:1446 ('lax'), `COOKIE_DOMAIN`
  main.py:1449, `COOKIE_PATH` main.py:1450 (None).
- DB: `DATABASE_URL` db.py:7 (sqlite data/app.db).
- Email: `EMAIL_ENABLED` emailer.py:26 (True), `APP_BASE_URL` :20, `SMTP_HOST/PORT/USER/PASS` :30-33,
  `MAIL_FROM` :34, `SMTP_STARTTLS` :35 (True), `SMTP_SSL` :36 (False).
- LLM: `LLM_PROVIDER` llm.py:9 ('ollama') and summary_engine.py:14 ('none'); `MISTRAL_API_KEY` llm.py:11,
  rag.py:14, summary_engine.py:21, warranty_parser.py; `MISTRAL_MODEL` ('mistral-small-latest');
  `OPENAI_ENABLED` ('0'), `OPENAI_INVOICE_ENRICHMENT` ('0'), `OPENAI_API_KEY`, `OPENAI_MODEL`
  ('gpt-4.1-mini'), `OPENAI_TIMEOUT_SEC` ('20'), `OPENAI_MAX_INPUT_CHARS` ('6000') openai_intelligence.py:8-28;
  `OPENAI_FALLBACK_PROVIDER` summary_engine.py:22 ('template'); `RAG_ENABLED` rag.py:16, summary_engine.py:23 ('0').
- OCR: `OCR_ENGINE` ocr.py:25 ('tesseract'), `OCR_ENGINE_TTL_SEC` ocr.py:27 ('900').
- Schedulers: `SCHEDULER_ENABLED` runtime_safety.py:40, `OEM_REFRESH_MINUTES` main.py:401 ('120'),
  `RISK_REFRESH_MINUTES` scheduler.py:38 ('120'), `REVIEW_CRAWL_ENABLED` scheduler.py:40 ('true').
- Search: `TERMS_SEARCH_PROVIDER` web_search.py:302 ('auto'), `TERMS_SEARCH_AUTO_ORDER` :313 (''),
  `SERPER_API_KEY` :191 (also `SERPER_KEY`), `SERPAPI_KEY` :255, `GOOGLE_CSE_API_KEY`/`GOOGLE_CSE_CX` :223-224;
  `SEARCH_{DAILY,MONTHLY}_LIMIT_{GOOGLE,SERPAPI,SERPER}` read dynamically at web_search.py:101-102
  (fallback `SEARCH_DAILY_LIMIT`/`SEARCH_MONTHLY_LIMIT`, 0 = unlimited);
  `TERMS_SEARCH_MAX_QUERIES` ('2'), `TERMS_SEARCH_MAX_RESULTS` ('5'), `TERMS_SEARCH_TIMEOUT_SEC` ('6'),
  `TERMS_OFFICIAL_ONLY`, `TERMS_PREFLIGHT_STRICT`, `TERMS_ALLOW_BROAD_FALLBACK` warranty_discovery.py:38-44 and
  oem_source_policy.py:107-128 (note: two modules, different defaults: OFFICIAL_ONLY '0'/'false',
  PREFLIGHT_STRICT '1'/'true', BROAD_FALLBACK '0'/'false').
- **Set in production but read by no code:** `FORCE_HTTPS_REDIRECT`, `MISTRAL_EMBED_MODE` (code reads
  `MISTRAL_EMBED_MODEL`). They have no effect.
- **Read by code, not set in production (defaults apply), notable ones:** `APP_ENV`/`ENVIRONMENT`/
  `FASTAPI_ENV` (production detection falls back to Railway's own `RAILWAY_ENVIRONMENT`), `OEM_AUTO_VERIFY`
  (true: every upload calls domain verification), `TERMS_NLP_ENRICH_ENABLED` (**1**: with `MISTRAL_API_KEY`
  set, low-confidence OEM pages are sent to Mistral), `HEADLESS_SCRAPE` (0), `GROUNDED_AI_*` (off),
  `RATE_LIMIT_ENABLED` (1), `AI_QUOTA_ENABLED`/`AI_DAILY_QUOTA_PER_USER` (unset), `PUBLIC_SIGNUP_ENABLED` (1),
  `REQUIRE_OEM_DIRECT_CONSENT`, `REQUIRE_USER_CONSENT` (false), `EXPIRY_REMINDER_ENABLED` (true),
  `OEM_AUTO_DISPATCH_ENABLED` (true), `KPI_WATCHDOG/REMEDIATION/EXECUTION_ENABLED` (true),
  `REMOTE_DIAGNOSTICS_AUTO_EXECUTE` (true), `REVIEW_CRAWL_ON_UPLOAD` (false), `JWT_EXPIRE_HOURS` (8),
  `UPLOAD_MAX_BYTES` (10 MB), `MISTRAL_EMBED_MODEL` ('mistral-embed'), object-store and Ollama settings.
  Full list (140 names) from an AST scan of `app/` and `run_app.py`.

**Does production AI send unredacted text?** Production runs `bf7e1ee1` (no Step 9 redaction). Values of
the flags are unknown, so conditionally:
- If `OPENAI_ENABLED` and `OPENAI_INVOICE_ENRICHMENT` are truthy and the key is valid: **yes** —
  `enrich_invoice_fields()` sends the first 6,000 chars of raw OCR invoice text (buyer name, address,
  phone, e-mail, GSTIN included) to OpenAI.
- If `RAG_ENABLED` is truthy with `MISTRAL_API_KEY`: **yes, personal identifiers** — telemetry and behaviour
  documents are embedded via Mistral with content `user=<username> warranty=<id> ... payload=<raw payload>`
  (storage.py:135, behaviour.py:131); usernames can be e-mail addresses. Warranty summaries are embedded too
  (product data only).
- Summaries (`LLM_PROVIDER` mistral/openai) send brand/model/expiry/terms only — no buyer fields.
- Mistral terms enrichment (`TERMS_NLP_ENRICH_ENABLED` default 1) sends OEM page text, not invoices.
- `/llm/generate` (main.py:2355) forwards a user-typed prompt as is.

### 91.B1 Redaction at every AI boundary (2026-10-03)

- New `app/services/privacy.py`: `redact_text()` / `ai_safe()`. Unconditional (no flag). Masks **tokens**,
  keeps labels: buyer block (Bill/Ship/Sold/Deliver to, Buyer, Consignee, Recipient, Customer — not
  "customer care", Billing/Shipping/Delivery address, Name) + up to 5 following lines; buyer phone,
  e-mail, GSTIN; phones/e-mails elsewhere unless on a seller/support line or in the seller header above
  the buyer label; `user=`/`user_id=`/`username=` values. Seller name/address/GSTIN/phone kept.
- Applied at every outbound AI call: `openai_intelligence.summarize_warranty` and `enrich_invoice_fields`;
  `llm.generate_with_mistral` and `generate_with_ollama` (`/llm/generate` and LLM routes; the logged
  prompt is the redacted one); `summary_engine.summarize_warranty` before any provider (mistral, openai,
  ollama_remote, llamacpp); `warranty_parser._mistral_enrich_terms`; `rag._embed` (all RAG documents:
  summaries, telemetry, behaviour, reviews, OEM knowledge); `grounded_extraction` (its own redaction
  replaced by the shared one). `ollama_questions.generate_questions` sends a fixed prompt with no data.
- Replaces Step 9's redaction, which masked whole address-like lines including the seller's.
- Tests: new `tests/test_privacy_redaction.py` (9): buyer masked/seller kept; unlabelled phone/e-mail;
  user ids; Mistral chat + Ollama; Mistral terms; RAG embeddings; summary for 4 providers; OpenAI summary
  and enrichment with flags on. Grounded test updated for the new counts.

### 91.B2 OCR: Paddle back-off, Tesseract in build, Playwright decision (2026-10-03)

- `ocr.run_paddle_ocr()`: any Paddle failure (init **or** inference) sets a back-off of
  `OCR_ENGINE_TTL_SEC` (default 900 s); while it runs Paddle is skipped without re-init and Tesseract is
  used directly; one WARNING per failure, not per upload; the engine is dropped so a fresh init is tried
  after the back-off. `paddle_backoff_remaining()` added; `/health/ocr` reports `paddle_backoff_sec`; the
  health probe always really tries Paddle.
- Measured (50 synthetic images, real OCR): accuracy identical to 90.6/90.7 (brand 26, model 2,
  date 24, coverage 16, category 26, serial 0, invoice 0); engines 40 tesseract_fallback / 10 no text.
  Runtime 35.5 s vs 33 s in Step 6 — **no measurable local speed-up**: locally Paddle loads once and
  then fails fast. The gain is no repeated Paddle attempts/log noise per upload for 15 minutes.
- `Dockerfile`: `tesseract-ocr-eng` now listed explicitly (the Debian `tesseract-ocr` package already
  depends on it). Image not built here — **Docker is not installed on this machine**.
- Playwright **not added**: wheel 48.2 MB (PyPI metadata, playwright 1.63.0 manylinux x86_64) plus a
  Chromium download and its system libraries that cannot be measured without Docker; the image already
  carries `paddlepaddle` (latest 3.3.1, 195 MB wheel, unpinned). `HEADLESS_SCRAPE` stays dead in production.
- Tests: new `tests/test_ocr_paddle_backoff.py` (4).

### 91.B3 RAG out of the risk score; negation/count bug fixed (2026-10-03)

- Bug (predictive.py RAG block): `any(k in ctx_low for k in ["failure","error","issue","recall"])` added
  +0.05 for "no failures reported" exactly as for "multiple failures reported"; "maintenance/care/clean"
  likewise matched "No maintenance recorded".
- New `app/services/rag_signals.py::parse_rag_signals()` classifies each retrieved sentence: issue report
  (with count: digits or several/multiple/many/repeated...), no-issue statement (no/zero/none/without/
  not/never/free of within 3 words), care report (negation-aware).
- `score_warranty()` now returns `rag_context` (`issue_reports`, `no_issue_statements`, `care_reports`,
  `evidence`) and **never changes the score from RAG** unless `RAG_RISK_SCORING=1` (default off; not set in
  production). With the flag, only real issue reports add +0.05 and only user-scoped care reports −0.03.
- Tests: new `tests/test_rag_risk_signals.py` (10): 7 parse cases, care negation, default no score effect
  (identical score for none / "no failures" / "multiple failures"), with flag "no failures" = baseline
  and "multiple failures" = baseline + 0.05.

### 91.B4 Insecure-settings warning on the admin hub (2026-10-03)

- New `app/services/security_status.py::security_report()` and admin-only `GET /admin/security-status`
  (401/403 for others; `/health/full` stays public and unchanged so weaknesses are not advertised).
  Reports by **name and kind only, never values**: ALLOW_INSECURE_DEFAULTS on (critical); insecure
  defaults allowed because production is not detected; JWT_SECRET missing/short(<32)/common; JWT_SALT
  missing; ADMIN_USER/ADMIN_PASS missing or ADMIN_PASS short(<12)/common; an admin account that still
  accepts the built-in default password (critical, checked against the DB hash); COOKIE_SECURE off
  (critical in production); COOKIE_SAMESITE invalid or `none`; FORCE_HTTPS_REDIRECT off in production;
  ALLOWED_HOSTS empty in production; RATE_LIMIT_ENABLED off; SMTP without SSL/STARTTLS. Never raises.
- `templates/admin_hub.html`: red "Security settings need attention" banner listing the messages; hidden
  when there are none. Nothing is changed automatically; the app does not crash on any value.
- `FORCE_HTTPS_REDIRECT` (set in production, previously read by **no** code) is now implemented as a
  middleware: 308 to `https://<host><path>` only when the proxy sends `X-Forwarded-Proto: http`; requests
  without the header (internal health checks) are never redirected. **Behaviour change on deploy** if the
  production value is truthy.
- Tests: new `tests/test_security_status.py` (5).

### 91.B5 Serial from misread labels → user-confirmed suggestion (2026-10-03)

- `ingestion._serial_candidate()` returns the kind of evidence. `labelled` (serial/S/N/SN/IMEI) → stored,
  0.7. `under_line_item` (the narrow Epson L3250 exception) → stored, 0.5 (kept as asked).
  `misread_label` (`seriat`, `seria:`, `seri`...) → **not stored**; written to
  `alternatives.serial_suggestion = {value, source_line, status: "pending", reason}`.
- `invoice_pipeline._update_warranty`: a confirmed/dismissed suggestion is never overwritten by
  re-processing; a stale pending suggestion is dropped when the new pass has none or finds a properly
  labelled serial.
- New `POST /warranties/{id}/serial-suggestion` `{action: confirm|dismiss, value?}` (owner/admin access):
  confirm stores the (optionally corrected) value, upper-cased, letters/digits/-/ only, ≤40 chars, with
  confidence 0.95 (≥ 0.9 → never cleared on re-processing); dismiss records the decision.
- Neo dashboard ("What is covered?"): yellow "Please check the serial number" box with the value, the source
  line, an editable field, **Confirm** / **Not right**; coverage details now show `Serial: … / Not confirmed`.
- Measured, 30 labelled synthetic images (cached OCR text): serial **0 correct / 0 wrong / 30 missing**
  (was 0 / 30 / 0 after 90.6) with **30 pending suggestions, all needing an edit** (0 exact — OCR reads
  `0` as `O`). Floor `serial_no` max wrong tightened 30 → 0. Non-warranty bills: 0 fields.
  `scripts/measure_invoice_fields.py` now counts `suggestion_exact` / `suggestion_needs_edit`.
- Tests: new `tests/test_serial_suggestion.py` (4); S001 test rewritten for the suggestion.

### 91.B6 Bug fixes (2026-10-03)

- **"MG Road" → brand MG**: `brand_registry.find_brands()` skips a brand name followed within 2 tokens by
  an address word (road, rd, street, marg, nagar, lane, layout, colony, sector, cross, avenue, chowk,
  circle, park, complex, plaza, enclave, vihar, bagh, gali, bazar, market, junction, flyover, estate).
  "tower", "main", "block" deliberately excluded ("Bajaj Tower Fan").
- **"device" → 36-month EV default**: `terms_lookup._normalize_category()` now matches whole words
  ("electronic device" → electronics → 12 months). The same substring bug existed in 3 more places and was
  fixed too: `product_recommendations.infer_product_category` (`"ev" in name` matched "device", "Clever",
  "Level"), `main.py` OEM aggregate `_infer_product_type` (`"ac"` matched "Black", `"ev"` "device") and the
  OEM EV payload check.
- **"120 months" → 20**: `warranty_parser._YEAR_RE`/`_MONTH_RE` are word-bounded, months read up to 3
  digits. `_clean_item()` no longer strips a leading quantity as a bullet ("60 months (only part warranty)"
  kept its number only after this fix); part-only rows ("part warranty", "parts warranty", "only part") count
  as component rows in the legacy maximum, so it does not jump to 120/240 on parts tables.
- **Epson broken characters — correction of 90.x**: re-checked live: the Epson server sends
  `text/html;charset=UTF-8`, the apostrophe as `&rsquo;`; the app's parsed term contains U+2019 (correct)
  and **no U+FFFD**; the fixture bytes are correct UTF-8. The `�` was only my Windows console display in
  Step 2 — not an app defect. Hardening added anyway: `warranty_parser.response_text()` decodes bodies with
  no declared charset as UTF-8 first (requests would assume ISO-8859-1), used by `parse_terms_from_url`,
  `oem_adapters` and `oem.fetch_oem_page`.
- **kia.com/in**: removed from `data/oem_domains.json` (`kia.com` already listed); `load_oem_domains()`
  now normalises every entry to a bare lower-case host (scheme/path/port/`www.` dropped, deduped).
- Tests: new `tests/test_bug_fixes_b6.py` (19). Field floors (cached + real OCR) unchanged and passing.

### 91.B7 Samsung: only the redundant 12-month forcing removed (2026-10-03)

- `terms_lookup._normalize_result_for_context()`: removed `result.duration_months = 12` and the two
  inserted duration lines ("Standard coverage for 12 months from purchase date.", "Limited international
  one year warranty."). Kept: the Samsung/mobile/samsung.com gate, the blocked-term filter
  (24m/2y/60m/5y/CoverPlus/extended/service plan), preferred-term filter, news/alerts/community/additional
  support claim-step filter and the default Samsung claim steps. `_source_conflicts_product_context()` kept.
- All 15 Step 2 Samsung/Epson end-to-end locks pass unchanged (12 months, exact terms/claim steps, source
  status). Live saved Samsung India page: still **12 months**, same 6 terms, evidence "The limited warranty
  period of 1 year will apply ...". The one unit test that asserted the forcing itself was rewritten to
  lock the new contract (duration left as parsed, 60; filtered terms `["Limited International One Year
  Warranty"]`).

### 91.B9 One risk scorer (2026-10-03; committed before B8 because B8's network run was still going)

- New `predictive.unified_risk(user_id, warranty_id) -> RiskScore`: the ML scorer `score_warranty()` is the
  single source; `risk.compute_risk()` (behaviour-event heuristic) is used **only** when the ML scorer
  raises or returns no LOW/MEDIUM/HIGH label (`source="heuristic_fallback"`). `RiskScore` gained `source`
  and `reasons`.
- `/risk/score`, `/advisories/{id}` and the warranty bundle endpoint now call `unified_risk`; the Neo
  dashboard already used `/predictive/score` → `score_warranty`, so all four now agree (test asserts equal
  value and band). `risk.compute_risk` is no longer imported by `main.py`.
- Nudge features connected: new `predictive._engagement_signals()` uses `_nudge_features()` (DB
  NudgeEvents: shown/acted/ignored — previously never called) plus in-memory behaviour events
  (`nudge_dismissed`, `task_completed`, `issue_reported`): +0.03 per dismissed/ignored reminder (max 0.09),
  −0.03 per completed care step (max 0.09), +0.1 per user-reported issue (max 0.3). Ignored reminders are
  not device evidence (cannot unlock HIGH); a user-reported issue is (new real-signal pattern
  "reported an issue/problem/fault"). Returned as `engagement` in the score output.
- Still not connected (unchanged, noted): `_peer_review_features`, `_search_features`.
- Tests: new `tests/test_unified_risk.py` (3).

### 91.B8 Domain verification replaced; verified list written (2026-10-03; committed after B9)

- `oem_domain_verify.verify_domain_detail()` replaces the 6,000-character homepage check. A domain passes
  only if: (1) it is mapped to the brand in `data/oem_domains.json` (or the brand name is in the host);
  (2) DNS resolves; (3) HTTPS answers (< 400; 401/403/429 bot-blocking goes to step 5); (4) every redirect
  stays on a same-brand host (the domain, another registry domain of the brand, or the brand name in the
  host); (5) the brand appears in `<title>` or brand meta tags (og:site_name, og:title, application-name,
  description, author, copyright...) — **never the page body** — or a same-brand support/warranty page is
  reachable (`/support`, `/warranty`, `/support/warranty`, `/in/support`, `/in/support/warranty`,
  `/service`, `/in/service`). UA `SmartWarrantyHub/1.0 (warranty source verification)`. `_verify_domain()`
  kept as a wrapper, so `verify_or_suggest()` (upload pipeline) uses the new rules.
- `scripts/preflight_oem_registry.py` rewritten to use it, `--write-verified` merges passing domains into
  `data/oem_verified.json` (existing entries kept). Report: `data/oem_domain_verification_2026-10-03.json`.
- **Measured** (200 brands / 231 domains, 312 s, 4 parallel, 0.5 s pauses): **169 domains / 153 brands
  verified** (old check: 33 domains / 32 brands). Evidence: title/metadata 159,
  support page 10. Failures: https_failed 25,
  no_brand_evidence 22 (all 403 bot-blocks: LG, Sony, Dell, Panasonic, Whirlpool...),
  dns_failed 11, redirect_to_other_brand 3 (mylloyd.com, fitbit.com → Google),
  https_status_402 1 (candesworld.com). India: 33 brands with a `.in` domain,
  45 with an India path only.
- **Written to `data/oem_verified.json` (169 domains):** Amaron: amaron.in; Amazfit: amazfit.com; Ambrane: ambraneindia.com; Anker: anker.com; AO Smith: aosmithindia.com, aosmith.com; Apple: apple.com; Apple India: apple.com; Asus: asus.com; Asus India: asus.com; Bajaj: bajaj.com, bajajauto.com; Bajaj Auto: bajajauto.com; Bajaj Electricals: bajajelectricals.com; Bajaj Finserv: bajajfinserv.in; Belkin: belkin.com; Blue Star: bluestarindia.com; boAt: boat-lifestyle.com; boAt India: boat-lifestyle.com; Borosil: borosil.com; Bosch: bosch.com; Bosch India: bosch.com; Bose: bose.com; Bose India: bose.com; Boult: boultaudio.com; BPL: bpl.in; Brother: brother.com; Butterfly: butterflyindia.com; BYD: byd.com; Canon: canon.co.in; Carrier: carrier.com, carrierindia.com; Cello: cello.in; Crompton: crompton.co.in; Crompton Greaves: crompton.co.in; Daikin: daikinindia.com; Denon: denon.com; Denon India: denon.com; Dyson: dyson.in, dyson.com; Epson: epson.co.in, epson.com; Exide: exideindustries.com; Garmin: garmin.com; Google: google.com, store.google.com; Google India: store.google.com, google.com; Haier: haier.com; Haier India: haier.com; Havells: havells.com; Hero: heromotocorp.com; Hero MotoCorp: heromotocorp.com; Hindware: hindware.com; Hindware Appliances: hindware.com; Hisense: hisense.com; Hisense India: hisense.com; Hitachi: hitachiaircon.com; Honda: honda.com, hondacarindia.com; Honor: honor.com; HP: hp.com; HP India: hp.com; HPL: hplindia.com; Hyundai: hyundai.com, hyundai.co.in; Hyundai India: hyundai.co.in; iBall: iball.co.in; iBall India: iball.co.in; iBELL: ibellstore.com; IFB: ifbappliances.com; IFB Appliances: ifbappliances.com; Inalsa: inalsaappliances.com; Infinix: infinixmobility.com; Infinix India: infinixmobility.com; iQOO: iqoo.com; iQOO India: iqoo.com; Jaquar: jaquar.com; Kenmore: kenmore.com; Kenstar: kenstar.in; Kent: kent.co.in; Kia: kia.com, kia.co.in; Kia India: kia.co.in; Lenovo: lenovo.com; Lenovo India: lenovo.com; Lloyd: lloydindia.in; Luminous: luminousindia.com; Mahindra: mahindra.com; Marshall: marshall.com; Marshall India: marshall.com; Maruti Suzuki: marutisuzuki.com; MG: mgmotor.co.in; MG Motor India: mgmotor.co.in; Microsoft: microsoft.com; Morphy Richards: morphyrichards.co.in; Motorola: motorola.com; Motorola India: motorola.com; Noise: noise.com; Noise India: noise.com; Nokia: nokia.com; Nokia India: nokia.com; Nothing: nothing.tech; Nothing India: nothing.tech; Ola Electric: olaelectric.com; OnePlus: oneplus.com; OnePlus India: oneplus.com; Onida: onida.com; Onida India: onida.com; Oppo: oppo.com; Oppo India: oppo.com; Orient: orientbell.com; Orient Electric: orientelectric.com; Philips: philips.com; Philips India: philips.com; Pioneer: pioneerelectronics.com; Pioneer India: pioneerelectronics.com; Portronics: portronics.com; Portronics India: portronics.com; Preethi: preethi.in; pTron: ptron.in; Racold: racold.com; Razer: razer.com; Realme: realme.com; Realme India: realme.com; Redmi: mi.com, xiaomi.com; Redmi India: mi.com, xiaomi.com; Samsung: samsung.com; Samsung India: samsung.com; Sennheiser: sennheiser.com; Sennheiser India: sennheiser.com; Sharp: global.sharp; Sharp India: global.sharp; Singer: singerindia.net; Skullcandy: skullcandy.com; Sonos: sonos.com; Surya: surya.co.in; Symphony: symphonylimited.com; Syska: syska.co.in; Tata: tata.com, tatamotors.com; Tata Motors: tatamotors.com; TCL: tcl.com; TCL India: tcl.com; Tecno: tecnomobile.com; Tecno India: tecnomobile.com; Toshiba: toshiba.com; Toshiba India: toshiba.com; Toyota: toyota-global.com, toyotabharat.com; TVS: tvsmotor.com; TVS Motor: tvsmotor.com; V-Guard: vguard.in; Vidiem: vidiem.in; Vivo: vivo.com; Vivo India: vivo.com; Voltas: voltas.com; Wipro: wipro.com; Wonderchef: wonderchef.com; Xiaomi: mi.com, xiaomi.com; Xiaomi India: mi.com, xiaomi.com; Yamaha: yamaha.com; Yamaha India: yamaha.com; Zebronics: zebronics.com; Zebronics India: zebronics.com
- Failing domains: https_failed — Samsung:samsungmobile.com, Acer:acer.com, Huawei:huawei.com, Blue Star:bluestar.com, Hitachi:hitachi.com, Videocon:videoconindustries.com, Godrej:godrej.com, Usha:ushainternational.com, Prestige:prestige.in, Eureka Forbes:eurekaforbes.com, Aquaguard:eurekaforbes.com, Orient:orientfan.com, Inalsa:inalsa.com, Cera:cera-india.com, USHA:ushainternational.com, Orient Fans:orientfan.com, Godrej Appliances:godrej.com, Videocon Appliances:videoconindustries.com, Kelvinator:kelvinator.com, Acer India:acer.com, JBL India:jbl.com, JBL:jbl.com, Harman Kardon:harmankardon.com, Ambrane:ambrane.com, Canon:canon.com; no_brand_evidence — LG:lg.com, Sony:sony.com, Dell:dell.com, MSI:msi.com, Daikin:daikin.co.in, Panasonic:panasonic.com, Whirlpool:whirlpool.com, Pigeon:pigeon.in, Croma:croma.com, Havells Lloyd:lloydindia.in, Panasonic India:panasonic.com, LG India:lg.com, Sony India:sony.com, Dell India:dell.com, MSI India:msi.com, Ather Energy:atherenergy.com, Mahindra Electric:mahindra.com, Fastrack:fastrack.in, Titan:titan.co.in, Casio:casio.com, Fossil:fossil.com, Ather:atherenergy.com; dns_failed — LG:lgmobiles.com, Daikin:daikin.com, Lloyd:lloydindia.com, Sansui:sansui-world.com, Glen:glengroup.co.in, Inalsa:inalsa.in, Khaitan:khaitanindia.com, Havells Lloyd:lloydindia.com, Khaitan Fans:khaitanindia.com, Polar:polarindia.com, Sansui India:sansui-world.com; redirect_to_other_brand — Lloyd:mylloyd.com, Havells Lloyd:mylloyd.com, Fitbit:fitbit.com; https_status_402 — Candes:candesworld.com
- Consequence (existing code, now active): terms from a verified domain are labelled "Verified official
  source" (`source_trust`), `requires_oem_verification` follows the existing rules, and discovery ranking
  gives verified domains +15. Two source-trust tests pinned the empty-list behaviour; they now monkeypatch
  an empty list, plus a new test for the verified label.
- Registry data question: `Orient` maps to `orientbell.com` (a tiles company) and verifies on its title;
  `Orient Fans` (`orientfan.com`) failed HTTPS. Not changed.
- Tests: new `tests/test_domain_verification.py` (7, network mocked); `tests/test_source_trust.py` (+1).

### 91.B10 AI vision tier for low-text images (2026-10-03)

- New `app/services/vision_extraction.py`, off unless `VISION_AI_EXTRACTION=1` **and** the OpenAI lane is
  configured (no key set anywhere here). Runs in `invoice_pipeline.run_job` when the source is an image and
  OCR text (OCR notes excluded) is < `VISION_MIN_TEXT_CHARS` (60); a job with no text no longer fails
  `no_text` when the vision tier is due.
- **Image redaction before sending**: Tesseract word boxes from the better of two pre-processings (whole
  page 2x autocontrast; or crop to dark-text region, 5x, unsharp mask, `--psm 4`), lines rebuilt, B1 buyer
  rules applied, black boxes painted. If mean word confidence < 70 (`VISION_STRICT_REDACTION_BELOW_CONF`)
  **strict mode**: every line that is not invoice/product-like (keywords, letter+digit codes, dates,
  registry brands; address-like lines never kept) is blacked out entirely, because garbled OCR can miss a
  "Bill To" label. No locatable words → **not sent** (`no_locatable_text`).
- Provider (OpenAI Responses, `input_image` PNG data URL, strict JSON schema) returns
  `{value, source_line, confidence}` for brand, product_name, model_code, serial_no, invoice_no,
  purchase_date. Kept only if value is inside its quoted line, line not from a redacted area, confidence
  ≥ 0.5. Value also present in the OCR text → field (0.6, only if empty); otherwise **pending suggestion**
  in `alternatives.vision_suggestions` — vision-only values never become fields on their own. User decisions
  survive re-processing.
- New `POST /warranties/{id}/vision-suggestion {field, action, value?}` (confirm sets the column, or
  `alternatives.invoice_no`; purchase date parsed; confidence 0.95) and a "Please check these details"
  box in the Neo dashboard.
- **Measured on the 10 `hard_ocr` synthetic images**: first version (2x only) located 0 words on all 10 →
  0 sendable. With the crop/5x variant: **9/10 sendable** (S037 still 0 words), all in strict mode, mean OCR
  confidence 33.5–46.8, 8–25 of ~31 words masked per image (some invoice lines are masked too — privacy
  first). AI extraction accuracy **not measured: no API key** (Part C skipped).
- Tests: new `tests/test_vision_tier.py` (6; real Tesseract for redaction, provider mocked): buyer
  hidden/identifiers kept; unlocatable → never sent; validation grounds/suggests/rejects; pipeline only with
  flag, vision-only values are suggestions, sent image OCRs without buyer data; confirm/dismiss endpoint;
  strict mode masks a garbled buyer label and an address line and keeps the invoice line.

### 91.B10 AI vision tier for low-text images (2026-10-03)

- New `app/services/vision_extraction.py`, off unless `VISION_AI_EXTRACTION=1` **and** the OpenAI lane is
  configured (no key set anywhere here). Runs in `invoice_pipeline.run_job` when the source is an image and
  OCR text (OCR notes excluded) is < `VISION_MIN_TEXT_CHARS` (60); a job with no text no longer fails
  `no_text` when the vision tier is due.
- **Image redaction before sending**: Tesseract word boxes from the better of two pre-processings (whole
  page 2x autocontrast; or crop to dark-text region, 5x, unsharp mask, `--psm 4`), lines rebuilt, B1 buyer
  rules applied, black boxes painted. If mean word confidence < 70 (`VISION_STRICT_REDACTION_BELOW_CONF`)
  **strict mode**: every line that is not invoice/product-like (keywords, letter+digit codes, dates,
  registry brands; address-like lines never kept) is blacked out entirely, because garbled OCR can miss a
  "Bill To" label. No locatable words → **not sent** (`no_locatable_text`).
- Provider (OpenAI Responses, `input_image` PNG data URL, strict JSON schema) returns
  `{value, source_line, confidence}` for brand, product_name, model_code, serial_no, invoice_no,
  purchase_date. Kept only if value is inside its quoted line, line not from a redacted area, confidence
  ≥ 0.5. Value also present in the OCR text → field (0.6, only if empty); otherwise **pending suggestion**
  in `alternatives.vision_suggestions` — vision-only values never become fields on their own. User decisions
  survive re-processing.
- New `POST /warranties/{id}/vision-suggestion {field, action, value?}` (confirm sets the column, or
  `alternatives.invoice_no`; purchase date parsed; confidence 0.95) and a "Please check these details"
  box in the Neo dashboard.
- **Measured on the 10 `hard_ocr` synthetic images**: first version (2x only) located 0 words on all 10 →
  0 sendable. With the crop/5x variant: **9/10 sendable** (S037 still 0 words), all in strict mode, mean OCR
  confidence 33.5–46.8, 8–25 of ~31 words masked per image (some invoice lines are masked too — privacy
  first). AI extraction accuracy **not measured: no API key** (Part C skipped).
- Tests: new `tests/test_vision_tier.py` (6; real Tesseract for redaction, provider mocked): buyer
  hidden/identifiers kept; unlocatable → never sent; validation grounds/suggests/rejects; pipeline only with
  flag, vision-only values are suggestions, sent image OCRs without buyer data; confirm/dismiss endpoint;
  strict mode masks a garbled buyer label and an address line and keeps the invoice line.

### 91.C Real measurement — skipped (2026-10-03)

No API keys exist locally: `.env` holds only OCR_ENGINE, OEM_REFRESH_MINUTES, OEM_REVIEW_REQUIRED,
DISABLE_MODEL_SOURCE_CHECK; OPENAI/MISTRAL/SERPER/SERPAPI/GOOGLE_CSE/BRAVE/BING keys are not set in the shell
(checked by name only). AI-on vs AI-off field accuracy, the 20-brand warranty-page measurement and API cost
were **not measured**.

### 91.D Production-like local run (2026-10-03/04)

Setup: `python run_local.py` (scratchpad, not in repo) with every production variable **name** and local test
values: generated ADMIN/JWT secrets (scratchpad file, never printed or committed), `RAILWAY_ENVIRONMENT=production`,
`ALLOW_INSECURE_DEFAULTS=false`, `COOKIE_SECURE=false` (plain-HTTP localhost), `FORCE_HTTPS_REDIRECT=1`,
`OCR_ENGINE=paddle`, `OPENAI_ENABLED=1` + `OPENAI_INVOICE_ENRICHMENT=1` with **no key**, `RAG_ENABLED=1` with no
Mistral key, `SCHEDULER_ENABLED=0`, `EMAIL_ENABLED=false`, fresh SQLite DB. Started via the Browser pane
(`.claude/launch.json`, left untracked). Journeys scripted against the HTTP API, UI checked in the browser.

| Journey | Job | Stored fields | OCR | Risk (predictive / risk / advisories) | Notifications |
|---|---|---|---|---|---|
| Text PDF (`invoice_full_details.pdf`) | done 4.6 s | Samsung, "Samsung Galaxy S24 Ultra Model Code: SM-S928BZKGINS", model **S24** (should be SM-S928BZKGINS), serial R5CX40VP8LA, 12 m, 2026-01-22 → 2027-01-22, source `approved_oem_source` | pdf text layer | LOW 0.32 / low 0.32 predictive / low | onboarded |
| Scanned PDF (image-only, from S002) | done 7.6 s | brand **"Lo"** (OCR of "LG"; wrong), product "Product", 12 m (default), 2025-01-11 → 2026-01-11; serial suggestion SN002X1002 (pending) | pdf_ocr, tesseract, paddle failed | LOW 0.32 consistent | onboarded, **expiry_expired** (first expiry, genuinely past — correct) |
| Phone photo, clear (S001) | done 1.4 s | Apple, product **"Band: Apple"** (OCR "Brand"→"Band"; wrong), coverage **38** (truth 36, OCR), 2025-01-06; serial suggestion SNO01X1001 | tesseract_fallback | LOW 0.32 consistent | onboarded |
| Phone photo, blurred/skewed (S031) | done 1.4 s | nothing extracted; placeholder "Product", default 12 m, no dates | no text (vision tier off) | LOW 0.32 consistent | onboarded |

- Risk: `/predictive/score`, `/risk/score` (source `predictive`) and `/advisories` agree on every journey.
- UI (browser): admin hub shows the red banner "Critical: COOKIE_SECURE is off" (the only warning for these
  settings); Neo dashboard shows the serial suggestion box for S001 — corrected to SN001X1001 and confirmed in
  the UI → DB `serial_no=SN001X1001`, confidence 0.95, suggestion `confirmed`; OEM dashboard loads, no console
  errors, risk distribution LOW 4, aggregate insight "suppressed for privacy" (cohort 1 < 10).
- `/health/ocr`: ok=false, active engine tesseract, `paddle_backoff_sec` 899 after the first Paddle failure.
- HTTPS: `X-Forwarded-Proto: http` → 308 to https; without the header → 200 (internal checks unaffected).
- `/oem/domains/verified`: 153 brands. All OEM endpoints 200.
- Not done: AI paths with real providers (no keys); scheduler loops (disabled); e-mail (disabled; no SMTP);
  the blurred photo is unreadable without the vision tier, which needs a key.
- Defects observed (not fixed in this run): model code "S24" taken over the printed "SM-S928BZKGINS";
  garbled OCR brand "Lo" stored at face value; "Band: Apple" stored as product name; a photo with no text still
  gets a 12-month default coverage shown as "Estimated"; coverage-details lines render on one line in the
  Neo dashboard (newline-joined text in a div).

### 91.y Step log (each hash recorded by the next step's commit)

| Step | Commit | Tests | Notes |
|---|---|---|---|
| A | `5a8b8be4` | 299 passed | Production check; docs only. |
| B1 | `8d7865b3` | 307 passed (+8) | Redaction everywhere. |
| B2 | `80adf7df` | 311 passed (+4) | Paddle back-off; tesseract-ocr-eng. |
| B3 | `ad242961` | 321 passed (+10) | RAG never moves score by default. |
| B4 | `46a2cab4` | 326 passed (+5) | Admin security banner; HTTPS redirect implemented. |
| B5 | `e50fa3d0` | 330 passed (+4) | Serial suggestions confirmed in UI. |
| B6 | `c86d77c6` | 349 passed (+19) | Five bugs; Epson was a display artefact. |
| B7 | `e5c9e489` | 349 passed | Samsung duration force removed. |
| B9 | `2b62e8ed` | 359 passed (+10 incl. B8 tests) | One scorer; nudges connected. |
| B8 | `40ecb293` | 360 passed (+1) | 169 domains verified and written. |
| B10 | `0b1f70cc` | 366 passed (+6) | Vision tier, off by default. |
| B11 | `1c8b69c0` | 370 passed (+4) | Expiry recalculation guard. |
| D | (next) | 370 passed | Local production-like run; C skipped (no keys). |

### 91.x Open questions
- Pin `paddlepaddle` (unpinned in requirements; production pulls 3.x and Paddle cannot read with
  paddleocr 2.8 models) or drop Paddle from the image (saves the 195 MB wheel)? User decision (OCR engine).
- Playwright in the image: needs a real Docker build to measure size.
- B4: confirm the production value of FORCE_HTTPS_REDIRECT before deploy — when truthy, plain-HTTP
  requests (as reported by Railway's proxy) will now get a 308 to HTTPS.
- B8: with the verified list populated, 153 brands' terms show as "Verified official source". Domain
  verification proves the site belongs to the brand, not that scraped terms are correct — keep, or keep
  `requires_oem_verification` true for all scraped terms?
- B8: registry `Orient` → `orientbell.com` (tiles) looks wrong; LG/Sony/Dell/Panasonic/Whirlpool block the
  verifier with 403 — add them manually after a human check?
- B10: the crop/5x pre-processing that makes hard images locatable might also help normal OCR of blurry
  photos (it reads garbled-but-partial text on S031/S035/S040). Not wired into OCR — try and measure?
- Test run stalled twice in a row at the first test (`test_auth_form_routes`, which starts the app
  lifespan) during B11, then 2 consecutive clean runs (370 passed, 74-76 s). Not reproduced; cause unknown.
- Part D defects: model "S24" vs printed "SM-S928BZKGINS"; OCR-garbled brand "Lo" stored; "Band: Apple" as
  product name; default 12-month coverage shown for a photo with no readable text. Fix in a next run?

## 92. Follow-up run: deploy, registry review, extraction defects, clean-up (started 2026-10-04)

User approved the fix run 91 decisions. Rules: one local commit per step, full tests after each, MEMORY
update after each step, measured numbers only, never print secrets, no Railway changes. Step 0 is pushed
and deployed; Steps 1-3 are NOT pushed until the user approves.

### Checklist
- [x] 0a .gitignore: `.claude/`, `.kiro/`, `data/ai_usage_quota.json`
- [x] 0b Label: "Verified official source" -> "From the official <Brand> website" (brand spelled as in the
  verified registry). Note text now says the website was confirmed to belong to the brand.
- [x] 0c Orient: `Orient` -> `orientelectric.com` in `data/oem_domains.json` and `data/oem_verified.json`
  (was `orientbell.com`, a tiles company, plus `orientfan.com`). `Orient Fans` -> `orientfan.com` left as is
  (failed HTTPS in 91.B8; ownership unconfirmed — listed in Step 1 review).
- [x] 0d Pushed `bf7e1ee1..9e9bc278` to origin/master (Railway deploys from master; the new build was
  live about 5 min after the push). Live checks 2026-10-04 (https://www.smartwarrantyhub.com):
  - `/` 200, `/login` 200, `/api/health` 200, `/health/ocr` 200, `/health/full` 200.
  - `/health` is 404 before and after the deploy: the app has no such route (health is `/api/health`).
  - http://www -> 301 (Railway edge) -> https, 1 redirect, no loop; `/ui/*` pages redirect once to `/login?next=...`.
  - Login: POST /auth/login with a non-existent probe user -> 401 (no 500). A real login was not done
    (no production credentials used) - user to confirm.
  - `/health/ocr` now runs real OCR: `ok:false`, "PaddleOCR init failed: unexpected end of data; Tesseract
    fallback read the test image", active engine tesseract. Before the deploy it said "PaddleOCR available
    (lazy)" without reading anything. `/health/full` status "degraded" only because of that; llm (OpenAI),
    predictive and RAG (Mistral) report ok - so production AI calls are live and now redacted (B1).
  - Apex http(s)://smartwarrantyhub.com (no www) returns a 114-byte parking page that redirects to
    `/lander` - not served by the app (DNS/registrar), unchanged by this deploy.
  - Rollback if ever needed: Railway -> Deployments -> redeploy the previous deployment, or
    `git push --force-with-lease origin bf7e1ee1:master` (needs user approval).
- [x] 1 Registry review -> `docs/REGISTRY_REVIEW_2026-10-04.md`
  - A: 26 registry names shared by unrelated companies, listed for owner decision; NOT changed
    (Bajaj/Bajaj Auto/Bajaj Finserv, Tata, Hero, Honda, Yamaha, Hyundai, Usha, Wipro, Nokia/HMD, ...).
  - B: `data/oem_manual_confirmed.json` - LG lg.com, Sony sony.co.in, Dell dell.com, Panasonic
    panasonic.com, Whirlpool whirlpool.in + whirlpool.com; each opened in a real browser 2026-10-04, owner
    read from title/footer. Label "From the official <Brand> website (manually confirmed)", status
    `manually_confirmed_official`. `sony.co.in` and `whirlpool.in` added to the registry.
- [x] 2 Extraction defects (Part D journeys) - not pushed
  - Model: labelled "Model Code:/Model No:" read (was missed: regex needed "Model:"); a printed code
    (letters+digits with a hyphen, or 6+ mixed chars) beats a marketing name ("Galaxy S24"). A marketing
    name alone is still stored (0.7, `alternatives.model_evidence = marketing_name`) - the Samsung M17e
    regression tests require it. Misread model labels ("Mad", "Madet", "Modet") and unlabelled
    fallback tokens (was stored at 0.4) become `model_suggestion`.
  - Product name: a field line, exact or one OCR slip from a label ("Band: Apple", "Modet X"), is never a
    product name or line item; embedded labels are cut ("... S24 Ultra Model Code: SM-..." ->
    "Samsung Galaxy S24 Ultra"); "Product iPhone 15" without a colon is read.
  - Brand: `route_uncertain_identity` (ingestion) moves any brand not in the OEM registry, and any brand/
    model/serial below 0.6, into pending `brand_suggestion`/`model_suggestion`/`serial_suggestion`;
    user values (>= 0.9) and the Epson under-line-item serial are kept. Applied after extraction and
    again in the pipeline after AI enrichment/vision. Misread "Band:" is read as the brand label.
  - Unreadable: nothing identifying read and nothing to suggest -> `alternatives.unreadable_invoice`
    {message}, `terms_source_type = unreadable`, coverage/expiry/terms cleared (unless user-set), no
    terms lookup; evidence status "unreadable" ("Not read"), summary = the message. Also set when the job
    fails `no_text`. Message: "We couldn't read this invoice - retake the photo or enter the details."
  - New endpoints: POST /warranties/{id}/field-suggestion {field, action, value} (serial endpoint now
    delegates to the same resolver); POST /warranties/{id}/manual-details (brand/product/model/serial/
    purchase date, user confidence 0.95, then the same terms lookup as the pipeline via
    `invoice_pipeline.apply_terms_and_expiry`, which was moved out of `run_job` unchanged).
  - Neo dashboard: `#fieldSuggestions` (brand/model) and `#unreadableInvoice` (message + details form).
  - Measured, 30 labelled synthetic images, cached OCR text (`scripts/measure_invoice_fields.py`):
    | field | before | after |
    |---|---|---|
    | brand | 26 correct, 4 missing | 26 correct, 4 missing |
    | model_code | 2 correct, 1 wrong, 27 missing | 0 stored (0 wrong); 28 suggestions: 2 exact, 26 need an edit |
    | serial_no | 0 stored; 30 suggestions need an edit | unchanged |
    The 2 "correct" models came from misread labels, so they are now suggestions (same policy as serials).
  - Local production-like journeys (synthetic files) after the change: text PDF model SM-S928BZKGINS,
    product "Samsung Galaxy S24 Ultra"; scanned PDF brand none + suggestion "Lo", model suggestion
    OLEDSS-002; clear photo product "iPhone 15" (was "Band: Apple"); blurred photo coverage none, message
    shown (was 12 months "Estimated"). Browser: form saved -> message gone, terms looked up; brand
    suggestion confirmed as "LG" -> stored.
  - Found (pre-existing, not fixed, spawned as a separate task): POST /auth/login returns raw 403 "CSRF
    token missing or invalid" when the browser still holds an old `access_token` cookie (the login form
    sends no CSRF header). Reproduced locally and on the live site with a fake cookie; dates from
    `aa3f3b48` Phase 9C.
- [x] 3 Clean-up - not pushed
  - PaddleOCR removed from `requirements.txt` (`paddleocr==2.8.0`, unpinned `paddlepaddle`). Local
    install size: paddle 385 MB + paddleocr 3.2 MB, plus transitive packages. A fresh venv from the new
    requirements is 567 MB of site-packages with no paddle. `httpx==0.28.1` is now pinned (FastAPI
    TestClient needs it; it previously came via paddlepaddle and openai).
  - `ocr._resolve_engine()`: OCR_ENGINE=paddle falls back to Tesseract when PaddleOCR is not installed
    (production keeps OCR_ENGINE=paddle; no Railway change). `/health/ocr` then reports ok with
    `requested_engine: paddle`, a `note`, and no Paddle probe. Alias normalisation is `_requested_engine()`.
  - NEW EVIDENCE against removal: after the Step 0 deploy, production `/health/ocr` showed Paddle
    reading the test image ("PaddleOCR read the test image", active engine paddle); its first call
    had failed with "init failed: unexpected end of data" (model download). The oneDNN failure
    in 91.B2 was measured on local Windows only. Owner to decide before pushing Step 3.
  - Test stall: not reproduced in 6 full runs this session. Found that 3 tests made live calls to
    epson.co.in / epson.com (and DNS has no timeout), so a slow site could hold the run. Earlier "stalled at
    the first test" observations came from runs piped through `tail`, which shows no progress, so the
    stalled test was never actually identified. Fix: `tests/conftest.py` blocks non-loopback network unless
    `SWH_LIVE_NETWORK_TESTS=1`; the 2 tests that need live Epson pages are marked `live_network`
    (skipped by default; both pass with the flag); `pytest.ini` sets `faulthandler_timeout = 300` so
    any future hang prints every thread's stack. Side effect: tests no longer write
    `data/oem_verified.json` through auto-verify.
  - Tests: main venv 383 passed, 2 skipped (64 s); fresh no-Paddle venv 383 passed, 2 skipped (57 s).

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| 0 | `9e9bc278` | 372 passed (+2) | Label, Orient, gitignore. Pushed and deployed. |
| 1 | `17a40348` | 374 passed (+2) | Registry review doc; manual-confirmed list. Not pushed. |
| 2 | `04cca63a` | 384 passed (+10) | Model/brand/product fixes, suggestions, unreadable message. Not pushed. |
| 3 | (next) | 383 passed, 2 skipped (+1 test; 2 live tests opt-in) | Paddle out of requirements; hermetic tests. Not pushed. |

## 93. Consolidated run: push approved work, fixes, real-invoice loop, status (started 2026-10-04)

Rules: one local commit per step, full tests after each, MEMORY update per step, measured numbers only,
never print/commit secrets, no Railway changes. Push ONLY Part 1 (Steps 1-3 of entry 92 with Paddle kept).

### Checklist
- [x] P1.1 PaddleOCR restored in `requirements.txt` (`paddleocr==2.8.0`, unpinned `paddlepaddle`, as before
  92.3); Dockerfile comment restored. Reason (owner decision): production Paddle reads the test image;
  its first call failed only while the model was downloading. Kept from 92.3: Tesseract fallback when
  Paddle is missing, network blocking in tests, `httpx==0.28.1` pin, `faulthandler_timeout = 300`.
  Tests: 383 passed, 2 skipped.
- [x] P1.3 Paddle warm-up: `ocr.start_paddle_warmup()` called from the lifespan after `init_db`. Daemon
  thread OCRs the bundled health image with Paddle; start-up returns immediately. A watcher warns
  "still running after Ns" past OCR_WARMUP_TIMEOUT_SEC (default 300). Success is printed ("PaddleOCR
  warm-up finished in X.Xs", since the app sets no log level); failure is logged as a warning.
  `OCR_WARMUP=0` or a non-Paddle engine skips it. `get_paddle()` now has an init lock so the warm-up and
  an early upload never load the models twice. `/health/ocr` shows `paddle_warmup` {status, seconds,
  error}. Local start (Windows, OCR_ENGINE=paddle): server served requests during warm-up; warm-up
  failed after 5.3 s with the known local oneDNN error and was logged. Tests: 386 passed, 2 skipped.
- [x] P1.4 Pushed `9e9bc278..25e9d895` to origin/master (entry 92 Steps 1-3, Paddle restore, warm-up).
  Railway deployed it about 10 min later.
- [x] P1.5 Live checks 2026-10-04 (https://www.smartwarrantyhub.com): `/api/health` 200
  {"status":"ok"}; `/health/ocr` 200 ok, active engine paddle, `paddle_warmup` {"status":"ok",
  "seconds":106.5} - the warm-up took 106.5 s in production and start-up did not wait for it; `/login` 200;
  `/` 200; http://www -> 301 -> https, 1 redirect, no loop; login POST with an unknown probe user -> 303
  back to the form (no 500); `/ui/neo-dashboard` unauthenticated -> 303 to `/login?next=...`. No real
  login was done (no production credentials used).
- [x] P2.6 CSRF stale-cookie fix - not pushed. Base: the separate session's commit def3c278 (branch
  `claude/heuristic-davinci-19eae6`), cherry-picked as `2e472d20`: `/auth/login`, `/auth/signup`,
  `/auth/signup/form` are exempt from the cookie-session CSRF check (they are unauthenticated; before,
  they were checked only when an `access_token` cookie happened to be present). Every other route keeps
  the check unchanged. Extended here:
  - middleware `refresh_stale_auth_cookies` on /login, /auth/login, /auth/signup, /auth/signup/form: an
    invalid, expired or orphaned (user gone) `access_token` cookie is deleted and a fresh `csrf_token`
    issued, unless the response already sets them (successful login). Replaces def3c278's deletion in
    GET /login (which deleted the CSRF cookie without issuing a new one).
  - a CSRF failure from a browser page (Accept text/html, not JSON) now redirects 303 to
    `/login?error=session_expired` ("Your session expired. Please sign in again and retry.") instead of
    raw JSON; the request is still rejected. API clients still get 403 JSON.
  - tests (test_phase9c_csrf.py, 15): stale cookie, expired JWT, no cookie, failed login with stale cookie,
    signup with stale cookie, login -> logout -> login, CSRF still enforced on logout (JSON 403 / browser
    redirect, session unchanged). Full suite 436 passed, 2 skipped.
- [x] P2.7 Shared brand names - not pushed. `data/brand_families.json` + `app/services/brand_families.py`:
  `resolve_oem_entity(brand, product_name, model_code, category)` -> (family, segment, company).
  Segments by keyword (vehicles first): two_wheeler, car, bicycle, mobile, audio, industrial,
  home_appliance. Families: Bajaj (appliance -> Bajaj Electricals, 2W -> Bajaj Auto; never Bajaj Finserv),
  Honda (car / 2W), Hero (2W -> Hero MotoCorp, bicycle -> Hero Cycles), Yamaha (2W / audio -> Yamaha Music
  India), Hyundai (car only), Usha (appliance -> Usha International), Wipro (appliance -> Wipro Lighting),
  Nokia (mobile -> HMD), Tata (car -> Tata Motors), Kenmore (none), Havells, Crompton (industrial -> CG Power).
  No company for the segment, or segment unknown -> `lookup_terms` returns `needs_check_terms` (no
  duration, no search; source `internal://needs_check_shared_brand`, type `needs_check`, label
  "Estimated - please check your warranty card or the seller"). Otherwise lookup, auto-verify and source
  classification use the company; `alternatives.oem_entity` records it; the stored brand stays as printed.
  Registry: +9 company entries (Honda Cars India, Honda Motorcycle & Scooter India, Hero Cycles, Yamaha Motor
  India, Yamaha Music India, Wipro Lighting, HMD, CG Power, Usha International); 7 passed the domain check
  and were added to the verified list; honda2wheelersindia.com (no brand evidence) and
  ushainternational.com (HTTPS failed) are registry-only. Hero Electric (heroelectric.in) DNS failed - not added.
  Bugs found by the tests and fixed: the line joiner glued "Invoice No:"/"Date:" lines onto the product line
  (the item was then discarded); a lender in the seller line ("Bajaj Finserv") became the brand -
  `brand_registry.NON_MAKERS`. Tests: 416 passed, 2 skipped (+30). Field measurement unchanged.
- [x] P2.8 Marketplace invoices - not pushed. Synthetic fixtures `tests/fixtures/marketplace/` (Amazon/Appario,
  Flipkart/RetailNet, Croma own-label, Reliance Digital own-label "Reconnect").
  - Before: Amazon gave no brand/product/date (the item row was rejected as boilerplate because it
    contained "IGST"), category "mobile" (substring "phone" in "Headphones"), and the seller's PAN offered as
    a model; Croma own-label brand dropped (retailer-name sanitiser); Flipkart product name included
    "FSN: ... HSN/SAC" and "Invoice Number # X" was missed; Reliance unknown brand gave nothing.
  - Fixes (ingestion): numbered item rows are cut to their description (`_item_row_description`: stops at
    HSN/SAC/FSN or the first price; drops a trailing quantity); an identified item row counts as
    warranty context (dates are read); phone/mobile category by whole word, headphones/speakers ->
    electronics, mixer/grinder/ceiling fan -> appliance; PAN/GSTIN and tokens on PAN/GST/order/invoice
    lines are never model suggestions; FSN/ASIN/HSN cut from product names; "Invoice Number # X"; a
    retailer that starts the item line is kept as the brand (own label); an unknown first word of the item
    title becomes a pending `brand_suggestion`. The Epson under-line serial now matches the trimmed row.
  - Unknown/tiny/missing brand: `lookup_terms` returns `needs_check_terms` (source
    `internal://needs_check_unknown_brand`): no duration, no search, label "Estimated - please check your
    warranty card or the seller". Invoice-stated warranty months are still shown (not a guess).
    Exception: `url_override` (manual URL) still runs.
  - India page preference: `warranty_discovery._region_score` gave +8 to any URL containing "in"
    ("printer", "warranty-info"); now +8 only for a country path segment (/in/, /en-in/), +4 for "india",
    +6 for .in hosts (unchanged), -20 for another country's path (unchanged).
  - After: all 4 synthetic invoices give the expected brand (or suggestion), product, model/blank, invoice
    no, date; no serials invented. 50-sample field measurement unchanged. Tests: 425 passed, 2 skipped (+9).
- [x] P3.9-11 Real-invoice loop (setup only) - not pushed.
  - `real_invoices/` created and git-ignored (`.gitignore`); `real_invoices/expected.csv` holds only the
    header: file, brand, model, serial, invoice_no, purchase_date, category, warranty_months, key_exclusions
    (";"-separated keywords), oem_url. The owner fills it in. Nothing in real_invoices/ is ever committed.
  - `scripts/run_real_invoices.py [--dir] [--offline] [--no-ai] [--no-vision]`: posts each file to
    `/artifacts/upload` in-process (the full production path) against a throwaway SQLite DB, with generated
    admin credentials, OEM auto-verify/RAG/e-mail/scheduler/warm-up off, AI quota file in temp. AI on only if
    OPENAI_API_KEY / MISTRAL_API_KEY are in the local .env or environment (key values never printed);
    OpenAI also enables invoice enrichment and the vision tier (unless --no-vision). Counts AI calls and
    tokens (OpenAI responses usage; Mistral usage from responses); cost only when COST_<PROVIDER>_INPUT/
    OUTPUT prices (USD per 1M tokens) are set. Writes real_invoices/report.md: per invoice and stage
    (text read: engine, characters; fields vs expected; brand -> OEM domain; warranty page found/read;
    duration and exclusions; customer summary; time; API usage/cost), a pass-rate table per stage and
    failures grouped by cause. Outcomes: pass / please confirm (acceptable) / missing / FAIL (confident
    wrong) / n/a.
  - Tried on 3 synthetic invoices offline, no AI (scratchpad): text 3/3; fields 1/3; OEM domain 2/3;
    warranty page 0/3 (expected offline); duration 2/3; exclusions 1/1; summary 1/3; 8.6 s; no API calls.
    It surfaced two real gaps (not fixed): registry has philips.com but not philips.co.in; model
    "HL7756/00" is cut at "/" by extraction. `tests/test_run_real_invoices.py` runs it as a subprocess on 3
    synthetic invoices (offline, no AI) and checks the repo is untouched. Full suite 437 passed, 2 skipped.
  - "Unknown brand" (P2.8) = `terms_lookup._known_brand`: not an exact registry name and not resolvable by
    `brand_registry.resolve_brand`; empty brand counts as unknown.
- [x] P4.12-14 This entry checked against the code; `STATUS.md` written (what works, measured numbers with
  synthetic ones marked, live vs local, known issues, next steps); README "Review First", "Current Evidence
  Snapshot", "Validation Commands" and "Optional OCR / LLM" updated to match. Not pushed.

### Corrections to earlier entries
- 92.3 removed PaddleOCR from requirements; P1.1 above restored it (owner decision). The Tesseract
  fallback, test network blocking, httpx pin and faulthandler timeout from 92.3 remain.
- 91.B8 / 92 "169 domains (153 brands)" counted brand-domain pairs: at B8 the verified list had 153 brand
  names, 169 pairs, 117 distinct domains. Now (2026-10-04): 160 brand names, 176 pairs, 121 distinct
  domains; registry 209 names; 5 manually confirmed brands; 12 shared-brand families.
- README previously said the default OCR "expects paddleocr"; OCR falls back to Tesseract.

### State at the end of this run
- origin/master = `25e9d895` (live). Local master is ahead by P1.4-5 memory, P2.7, P2.8, P2.6 (2 commits), P3
  and P4 - none pushed; the owner approves Part 2 and Part 4 before any push.
- Separate session branch `claude/heuristic-davinci-19eae6` (worktree `.claude/worktrees/heuristic-davinci-19eae6`)
  holds def3c278, already cherry-picked here as `2e472d20`; the branch/worktree can be removed.

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| P1.1 | `f2e5d8e3` | 383 passed, 2 skipped | Paddle back in requirements. |
| P1.3 | `25e9d895` | 386 passed, 2 skipped (+3) | Background Paddle warm-up. Pushed. |
| P1.4-5 | `73e90793` | - | Push + live checks recorded. |
| P2.7 | `b53433eb` | 416 passed, 2 skipped (+30) | Shared brands by product segment. |
| P2.8 | `b147af43` | 425 passed, 2 skipped (+9) | Marketplace invoices; unknown brand -> please check; India pages. |
| P2.6 | `2e472d20` + `7e858a89` | 436 passed, 2 skipped (+11) | CSRF: cherry-picked exemption + stale-cookie middleware, friendly redirect. |
| P3 | `251bc733` | 437 passed, 2 skipped (+1) | real_invoices/ (ignored) + runner + runner test. |
| P4 | (next) | 437 passed, 2 skipped | MEMORY check, STATUS.md, README status. |

## 94. Push of Parts 2+4, small fixes, Mistral work, terms-cache review (started 2026-10-04)

Owner approved pushing entry 93 Parts 2 and 4. Rules as before; nothing after the push is pushed.

### Checklist
- [x] 94.0 Rate limits on sign-in/sign-up (checked before the push, since P2.6 skips CSRF there).
  Found: `/auth/login` was limited (`login` 10 per 10 min per client); `/auth/signup` and
  `/auth/signup/form` had NO rate limit. Added scope `signup` (5 per hour per client;
  RATE_LIMIT_SIGNUP_MAX / _WINDOW_SEC) to both. Browser forms that hit a limit now get a friendly redirect
  (`/login?error=rate_limited`, `/login?signup=rate_limited`) instead of raw 429 JSON; API clients still get
  429 with Retry-After. `tests/test_auth_rate_limits.py` (5): limits hold with a stale cookie, per client.
  Limits are on unless RATE_LIMIT_ENABLED is falsy (production value not known here; the admin security
  banner shows `rate_limit_off` if it is off). Open question: anonymous clients are keyed on the FIRST
  X-Forwarded-For entry, which a client can set; whether Railway's proxy replaces or appends that header
  decides if the limit can be dodged. Not changed. Tests 442 passed, 2 skipped.

- [x] 94.1 Pushed `25e9d895..eac60ead` (entry 93 P1.4-5 memory, P2.7, P2.8, P2.6 x2, P3, P4, and 94.0).
  Live 2026-10-04 19:27 (stale-cookie probe flipped from 403 to 303): `/api/health` 200 ok; `/health/ocr`
  200 ok, paddle active, warm-up ok in 85.3 s; the first `/health/ocr` after the deploy took 69.5 s (it runs
  real OCR with both engines, then caches 10 min); `/login` 200; http://www -> 301 -> https, 1 redirect;
  POST /auth/login with a stale cookie and an unknown probe user -> 303 `/login?error=invalid` (was 403);
  GET /login with a stale cookie -> deletes `access_token` (Max-Age=0) and sets a fresh `csrf_token`.
  No real login (owner will do it).

- [x] 94.2 Runner findings fixed - not pushed. `philips.co.in` added to Philips and Philips India in the registry
  (India first for Philips India) and, after passing the domain check, to the verified list; India pages
  score higher in discovery (+6 .in host). Model codes keep "/" variant parts ("HL7756/00", "SM-A155F/DS")
  in the printed-code and fallback patterns; unit pairs are dropped ("8GB/128GB" -> not part of the code).
  Field measurement unchanged (brand 26/30; model 0 stored, 28 suggestions). Tests 444 passed, 2 skipped.

- [x] 94.3 Mistral settings and redaction audit - not pushed.
  - `rag.embed_model_from_env()`: MISTRAL_EMBED_MODEL, else MISTRAL_EMBED_MODE (what production sets) when
    it looks like an embedding model name (contains "embed", no spaces), else "mistral-embed". The production
    MODE value was never read here; if it is not a model name it is ignored rather than breaking embeddings.
  - Every code path that sends data to Mistral, and where redaction (`privacy.ai_safe`) runs:
    | Path | Sends | Redaction |
    |---|---|---|
    | `llm.generate_with_mistral` <- `generate_text` <- POST /llm/generate (user prompt), POST /warranties/summary | chat prompt | inside the function |
    | `summary_engine._summarize_with_mistral` <- `summarize_warranty` (LLM_PROVIDER=mistral) and `_fallback_summary` (OPENAI_FALLBACK_PROVIDER=mistral) | summary prompt incl. RAG context | in `summarize_warranty` before either call, and now also inside the function |
    | `warranty_parser._mistral_enrich_terms` <- `_finalize_parsed` (TERMS_NLP_ENRICH_ENABLED, default on, when parsing is weak) | OEM page text (<= TERMS_NLP_MAX_CHARS) | inside the function |
    | `rag._embed` <- `upsert_document`, `search`, RAG smoke check | summaries, events, queries | inside the function (also masks user ids) |
    | `llm.health` (GET /models) | nothing | - |
    Tests cover each path (tests/test_privacy_redaction.py), plus the new summary-helper and embed-model tests.

- [x] 94.4 Provider fallback (OpenAI <-> Mistral) - not pushed. `app/services/ai_providers.py`:
  `run_with_fallback(task, text, handlers, default_first, chosen)` redacts once with `ai_safe`, then tries
  providers in order; a failure = exception (timeouts included), an error string or no result; meta records
  provider, fallback_used and every attempt (provider, ok, error, ms). Order: the chosen/first provider, then
  the other only if it has a key (OPENAI_ENABLED + OPENAI_API_KEY; MISTRAL_API_KEY) and AI_PROVIDER_FALLBACK
  is not 0 (default on). Wired into:
  - invoice enrichment: `ai_providers.enrich_invoice` (enabled by OPENAI_INVOICE_ENRICHMENT as before, or
    AI_INVOICE_ENRICHMENT=1); first = AI_PROVIDER or OpenAI; new `mistral_intelligence.request_invoice_enrichment`
    (JSON mode, same normalisation and 0.85 confidence cap); `openai_intelligence.request_invoice_enrichment`
    is the ungated core. Pipeline meta (`alternatives.openai_invoice_enrichment`, key unchanged) now has
    provider / fallback_used / attempts.
  - summaries: LLM_PROVIDER openai|mistral is tried first, then the other, then the old fallbacks/template.
  - OEM page terms extraction: AI_PROVIDER or Mistral first (always tried, as before), then OpenAI via new
    `openai_intelligence.request_terms_json`; output is still grounded in the page text.
  Production note: production has both providers configured (/health/full: OpenAI configured, Mistral RAG
  key present), so once pushed a failing provider's (redacted) request goes to the other one. Set
  AI_PROVIDER_FALLBACK=0 to keep the old single-provider behaviour.
  Privacy fix found by the new tests: a buyer label in the MIDDLE of a line ("... TAX INVOICE Bill To: Asha
  Verma Flat 12B ...", as OCR or row joining produce) left the name and address unmasked (phones/e-mails were
  masked). `privacy._mask_mid_line_buyer` masks from the label (needs ":"/"-"; bare "Name" excluded) to the
  next invoice keyword or an item row that names a product/brand (a house number is not an item row).
  Tests: tests/test_ai_provider_fallback.py (10, mocked timeouts/errors, redaction checked for both
  providers), mid-line redaction test. Full suite 457 passed, 2 skipped.

- [x] 94.5 Real-invoice runner: review mode, provider comparison; corrections log - not pushed.
  - `scripts/run_real_invoices.py`: expected.csv is optional. review.md is always written: per file (and per
    provider) a table of what SWH read - text engine/characters, brand, model, serial, invoice no, date,
    category (coarse / fine), OEM website used, warranty source URL, duration found, estimated / please-confirm
    status, first 3 summary lines - with blank "OK?" and "Correct value if wrong" columns. Marks: y/yes/ok
    = pass, n/no/x = fail, ? = please confirm (acceptable), a correction alone = fail. Re-running keeps marks
    while SWH's value is unchanged (otherwise lists them under "Marks cleared") and turns them into counts per
    stage ("Hand-marked results"). report.md is written when expected.csv has values or with --provider both.
  - `--provider auto|openai|mistral|both`: openai/mistral runs that provider alone (AI_PROVIDER set,
    AI_PROVIDER_FALLBACK=0, AI_INVOICE_ENRICHMENT=1; vision tier only with OpenAI); both runs each in its own
    subprocess and report.md starts with a comparison (fields / warranty page / duration acceptable, fields
    by hand marks, time, API calls, tokens, cost) and a table of items where the providers read differently.
    A provider that cannot run is listed with its reason (missing key, or the `openai` package not installed).
  - Found: the local .venv does NOT have the `openai` package (production does); the runner now says so
    instead of silently running without OpenAI.
  - `app/services/corrections_log.py`: when CORRECTIONS_LOG=1 (off by default; production stays off unless
    the owner approves), confirmations/corrections from the UI (brand/model/serial suggestions, vision
    suggestions, manual details) append to real_invoices/corrections.csv (git-ignored; CORRECTIONS_LOG_PATH
    overrides): logged_at, field, value_read, value_confirmed, action (confirmed / corrected / dismissed /
    entered). No warranty/user ids, names, addresses, phones or invoice text; values go through `ai_safe`.
  - Tests: runner review mode + marks, provider comparison (offline, fake keys in the subprocess env only),
    corrections log (off by default, columns, masking, git-ignored path). Full suite 462 passed, 2 skipped.

- [x] 94.6 Mistral for the vision tier - research only, nothing added or enabled.
  - Code today: `vision_extraction.apply_vision_tier(..., provider=None)` takes any
    `Provider = Callable[[bytes], dict]`; the only implementation is `_openai_vision_provider`, and
    `enabled()` is VISION_AI_EXTRACTION=1 with the OpenAI lane configured. The image is redacted
    (`redact_image`) before any provider gets it; values come back as suggestions to confirm.
  - Mistral docs (docs.mistral.ai, read 2026-10-04): vision-capable chat models - Mistral Large 3
    (`mistral-large-2512`), Mistral Medium 3.1 (`mistral-medium-2508`), Mistral Small 3.2
    (`mistral-small-2506`), Ministral 3 14B/8B/3B (2512) - take `{"type": "image_url", "image_url": ...}` content
    parts in Chat Completions, as a public URL or base64. Separate Document AI OCR: POST `/v1/ocr`, model
    `mistral-ocr-latest`, `document` of type `image_url` (PNG/JPEG/AVIF) or `document_url` (PDF/PPTX/DOCX),
    base64 accepted; returns `pages[].markdown`, optional confidence scores, and structured output via
    `document_annotation_format` / `document_annotation_prompt`. Image size/count limits and prices are in
    collapsed FAQ sections the fetch could not read - not confirmed.
  - To add: `_mistral_vision_provider(png)` (Chat Completions, a vision model such as `mistral-small-2506`
    set by MISTRAL_VISION_MODEL, the same JSON field contract {field: {value, source_line, confidence}},
    base64 data URL of the redacted PNG); choose it via AI_PROVIDER and `ai_providers.run_with_fallback`
    (image instead of text; redaction already done); relax `enabled()` from "OpenAI lane" to "any vision
    provider with a key"; mocked tests; then measure on the 10 hard synthetic photos with a key.
    Alternative: `/v1/ocr` as an OCR engine for the redacted image, feeding the deterministic extractor
    (markdown in, same suggestions out). About 80-120 lines plus tests either way.
- [x] 94.7 Terms cache - read-only review (no code changed).
  - Table `warranty_terms_cache` (`WarrantyTermsCacheDB`): brand, category, region, source_url, fetched_at,
    duration_months, raw_text, terms, exclusions, claim_steps. NOT stored: model, product name, confidence,
    source type / trust, grounding result, duration evidence, who or what wrote it.
  - Key: `brand == brand AND category == _normalize_category(category) AND region == region` (region None
    matches only NULL), newest `fetched_at` first. Category is coarse (mobile / ev / appliance / electronics /
    general ...), so one cached row serves every product of that brand and category in that region (a Samsung
    TV page could answer a Samsung monitor). Brand is the resolved company (P2.7), so Bajaj Auto and Bajaj
    Electricals do not share rows; a different region never matches.
  - Read only when `force_refresh` is False: POST /warranties/from-artifact and POST /warranty/terms/refresh
    (payload.force). The upload pipeline always forces a refresh, so for uploads the cache is write-only.
  - Before the cache, the same non-forced path reuses terms from ANY saved WarrantyDB row with the same brand
    and model (or product name, or brand alone when both are missing), across users, labelled "Confirmed
    from saved warranty record" (status confirmed_internal) even when those terms were default-rule
    estimates.
  - Fresh = fetched within 30 days (`_cache_is_fresh`); served only with a real http(s) source
    (`_cache_has_real_source`). Rows are never updated or deleted; every lookup that scrapes or falls back
    adds a row. Default-rules results ARE written (source_url NULL) but never served from the cache.
    "Needs check" results (P2.7/P2.8) are not written. Low-confidence or non-official scraped results can be
    written (no confidence is stored; trust is recomputed from the URL when read).
  - Failed refresh: discovery finds nothing -> default rules row written as newest -> the newest row has no
    real source -> the cache is skipped, so the older good row is effectively hidden until a scrape succeeds.
  - Counts: local `data/app.db` 3 rows (2 real-source Epson rows, 1 default row; 2 distinct keys);
    `data/preflight_eval.db` 50 rows (synthetic eval). No endpoint exposes counts. For production (Postgres):
    `SELECT count(*) AS rows, count(*) FILTER (WHERE source_url LIKE 'http%') AS real_source,
    count(*) FILTER (WHERE fetched_at > now() - interval '30 days') AS fresh,
    count(DISTINCT (brand, category, region)) AS keys, min(fetched_at), max(fetched_at) FROM warranty_terms_cache;`
  - Proposal (not implemented), "verified knowledge base": a separate `verified_terms` table (or columns)
    with brand company, region, category AND a product scope (model pattern or product line), source URL,
    page snapshot hash, duration, terms, exclusions, claim steps, verified_by, verified_at, note, locked.
    Lookup checks it first, also on force_refresh; refreshes never update or delete a locked row - a refresh
    that disagrees is stored as a "drift" candidate and raises an admin notification for review. Admin-only
    endpoints to add/lock/unlock with an audit log; customer label e.g. "From the official <Brand> website,
    checked on <date>"; a re-check reminder after N days without un-locking. Implies fixing: use the newest
    row WITH a real source, add a product scope to the cache key, and stop reusing other users' default-rule
    terms as "confirmed".

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| 94.0 | `eac60ead` (pushed) | 442 passed, 2 skipped (+5) | Sign-up rate limit; friendly limit messages. |
| 94.2 | `bc85e1ca` | 444 passed, 2 skipped (+2) | philips.co.in; "/" in model codes. |
| 94.3 | `025e21a8` | 446 passed, 2 skipped (+2) | Embed model env; Mistral redaction audit. |
| 94.4 | `682af6ad` | 457 passed, 2 skipped (+11) | Provider fallback; mid-line buyer redaction. |
| 94.5 | `557e6c6e` | 462 passed, 2 skipped (+5) | Runner review mode / marks / --provider; corrections log. |
| 94.6-7 | (next) | 462 passed, 2 skipped | Vision research, terms-cache review, STATUS.md, README count. |

### State at the end of this entry
- origin/master = `eac60ead` (live). Local only: `bc85e1ca`, `025e21a8`, `682af6ad`, `557e6c6e` and the
  94.6-7 commit. Nothing pushed after 94.1.

## 95. Terms-cache fixes and knowledge base v1 (started 2026-10-04)

Owner approved pushing entry 94's 5 commits, on condition that Railway's health check uses /api/health
and not /health/ocr. Rules as before; nothing in this entry is pushed without approval.

### Checklist
- [ ] 95.0 Push: NOT done. The repo defines no health check (no railway.json/railway.toml, no Dockerfile
  HEALTHCHECK, run_app.py just starts uvicorn), so the path - if any - is set in the Railway dashboard and
  cannot be confirmed from files. Adding railway.json would change Railway settings (not allowed). Asked
  the owner to check Settings > Deploy > Healthcheck Path. Evidence: the last two deploys went live while
  the first /health/ocr call took ~70 s; none of the 5 commits changes /health/ocr.
- [x] 95.1 Product scope in the cache key - not pushed. New columns on `warranty_terms_cache` (added for
  existing tables by `app/schema_upgrade.ensure_columns`, called from `init_db`: ADD COLUMN [IF NOT EXISTS],
  only when missing; checked on a copy of local data/app.db; Postgres path not run locally): model_code,
  product_line (+ source_type, confidence, grounded used by 95.4). `app/services/terms_cache.py`:
  product line = `product_recommendations.infer_product_category` of model + product name ("tv",
  "smartphone", "fan", ...; "general" -> None); model key = alphanumerics of the model code. Reads filter
  brand + category + region + product_line (NULL matches only NULL) and prefer the same model; writes store
  both. Tests: Samsung TV terms never answer a Samsung phone (same coarse category); same model preferred.

- [x] 95.2 Saved warranties of other users - not pushed. `lookup_terms` step 1 now needs a model or product
  name (never brand alone) and reuses a saved record only when `_reusable_official_record`: its
  terms_source_type is approved_oem_source or scraped AND its terms_source_url is a real page on a verified /
  manually confirmed official domain (or approved OEM path) AND it is the same product line. Up to the 20
  newest candidates are checked. The reused result carries that record's real source URL (so the normal
  "From the official <Brand> website" label applies); `internal://warranty_db` is no longer produced.
  Legacy rows with terms_source_type internal_warranty_db now show "From a saved warranty record - not
  confirmed" (status not_confirmed) instead of "Confirmed from saved warranty record".
  Tests: an estimate is never reused or shown as confirmed; official record reused with its URL; other
  product line / brand-only never reused; legacy label.

- [x] 95.3-4 Newest official entry; metadata; official-only caching - not pushed (one commit: same code).
  - Rows get source_type ("official" = verified or manually confirmed domain of the brand, "non_official",
    "default"), confidence (parser confidence; merged = highest), grounded (duration traced to a page
    sentence by duration selection; None when no duration), model_code and product_line.
  - Reads use `terms_cache.latest_official`: newest row of the scope that is official (legacy rows without
    source_type count only if their URL still verifies), so default or non-official rows never hide it.
  - Writes: scraped / manual-URL results are cached only when official (`terms_cache.cacheable`); default
    rows are still written but tagged "default" and never served.
  - Failed refresh (forced lookup finds no source): the last good official row is returned (any age; flagged
    by 95.5) instead of default rules, and no default row is written on top.
  - Removed `_cache_is_fresh` / `_cache_has_real_source` (replaced). Tests: default/non-official rows never
    hide a good entry; failed refresh keeps the last good entry; legacy rows; official result cached with
    metadata; non-official scrape not cached.

- [x] 95.5 Expiry and "checked on" - not pushed. Cache entries are served by normal reads only while
  fetched within 30 days (`terms_cache.FRESH_DAYS`); older official entries are used only as the last good
  entry when a refresh finds nothing, with `needs_refresh=True`. TermsResult gained checked_at /
  needs_refresh (and confidence / grounded); fresh scrapes set checked_at = now, cached / last-good / reused
  saved records keep their own date. The pipeline stores `terms_last_refreshed_at` = that date (was always
  "now") and `terms_needs_refresh`. Evidence summary: confirmed labels end "- checked on YYYY-MM-DD", plus
  ", needs refresh" (and requires_oem_verification) when older than 30 days or flagged; fields checked_on
  and needs_refresh. Tests: 31-day entry not served but returned flagged on failed refresh; 29-day served;
  label with date / needs refresh; reused saved record carries its date.

- [x] 95.6 Admin count endpoint - not pushed. GET /admin/terms-cache/stats (require_admin) ->
  `terms_cache.stats`: rows, real_source_rows (http source), official_rows, fresh_official_rows,
  stale_official_rows, default_rows (tagged default or no source), non_official_rows,
  legacy_rows_without_source_type, distinct_keys (brand, category, region, product line), fresh_days,
  oldest/newest fetched_at. Counts only, no row contents. Tests: counts; 401 without login, 403 for a user.
  Note: one full-suite run took 70 min and failed a runner subprocess test with "timed out after -3486 s"
  (negative = the wall clock jumped while the process was frozen: the machine slept 20:49-21:57). The
  same runner finished in 10 s afterwards; the commit gate held the commit; re-run was clean.

- [x] 95.7 Knowledge base v1 - not pushed; empty (no data added).
  - Tables (new, created by create_all): `verified_terms` (company, region NULL=any, category NULL=any,
    product_scope "model:<KEY>" or "line:<line>", source_url, page_fingerprint = SHA-256 of normalised page
    text, duration_months, terms, exclusions, claim_steps, verified_by, verified_at, locked default true,
    note) and `verified_terms_reviews` (entry_id, the new reading, differences, status pending/accepted/
    dismissed, resolved_by/at).
  - `app/services/knowledge_base.py`: `find_entry` (company case-insensitive, scope = model then product
    line, never brand-wide; region and category match or NULL; most specific first). `lookup_terms` checks
    it before saved records, cache and discovery, including forced refreshes (not for a manual
    url_override); result has source_kind "knowledge_base", checked_at = verified_at.
  - Pipeline: terms_source_type "knowledge_base"; its duration overrides an invoice-stated one, like an
    approved OEM page. Evidence: status confirmed, label "Checked on YYYY-MM-DD", note "Terms hand-checked
    against the official <Brand> website."; no 30-day needs-refresh flag (re-checks are an admin action).
  - `recheck`: re-reads the official page; same -> nothing changes; different + locked -> entry untouched,
    review saved, every admin notified (notification audience "admin", warranty_id "kb:<id>");
    different + unlocked -> entry updated. Reviews: accept only into an unlocked entry (409 otherwise),
    or dismiss. Create / lock / unlock / recheck / review decisions go to the audit log (kb_* actions).
  - Admin-only endpoints: GET/POST /admin/knowledge-base, POST /admin/knowledge-base/{id}/lock|unlock|recheck,
    GET /admin/knowledge-base/reviews, POST /admin/knowledge-base/reviews/{id}/accept|dismiss. Create checks:
    company is a registry name; source_url is on the company's verified official website; model_code or
    product_line given; lists of strings. /admin/terms-cache/stats also returns knowledge_base counts.
  - Tests (tests/test_knowledge_base.py, 9): checked entry first even when forced; scope/region/category
    matching (TV entry never answers a phone; never brand-wide); locked recheck -> review + admin
    notifications + audit, entry unchanged; unchanged / unlocked update; accept blocked while locked;
    "Checked on <date>"; endpoints (create, lock/unlock, list, validation, audit) and admin-only; pipeline
    end to end. Test isolation: these modules switch the rate limiter off (full-suite logins hit it).

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| 95.1 | `a8df141b` | 465 passed, 2 skipped (+3) | Product scope in the cache key; column upgrade helper. |
| 95.2 | `2d3926f9` | 469 passed, 2 skipped (+4) | Saved records reused only from official sources, same line. |
| 95.3-4 | `9a7de517` + `4ed67981` | 474 passed, 2 skipped (+5) | Newest official entry; metadata; official-only caching. `9a7de517` was committed with 1 failing test (the commit gate checked grep's exit code, not pytest's): test_samsung_notebook_page_rejected_for_mobile_in_auto_discovery got the last good Samsung mobile entry another test had cached - intended behaviour of 95.3; the next commit isolates that module's cache rows. Commits are now gated on pytest's exit code. |
| 95.5 | `8f9c94ca` | 477 passed, 2 skipped (+3) | 30-day expiry; "checked on <date>"; needs-refresh flag. |
| 95.6 | `6dc8aa69` | 479 passed, 2 skipped (+2) | Admin terms-cache counts. |
| 95.7 | `a4ad9b63` | 488 passed, 2 skipped (+9) | Knowledge base v1 (empty). |
| 95.8 | `f76df0d0` | 488 passed, 2 skipped | STATUS.md. |

### State at the end of this entry
- origin/master = `eac60ead` (live). Local only, not pushed: entry 94's 5 commits (bc85e1ca, 025e21a8, 682af6ad,
  557e6c6e, a5ab512f) + a8df141b, 2d3926f9, 9a7de517, 4ed67981, 8f9c94ca, 6dc8aa69, a4ad9b63 + 95.8. Push waits
  for the owner to confirm Railway's health-check path (95.0).

## 96. Safe start-up schema change, then push (2026-10-05)

### Checklist
- [x] 96.1 Start-up schema upgrade hardened - not pushed. `app/schema_upgrade.run_startup_upgrade(engine)`
  (called from `init_db`; never raises): creates `verified_terms` / `verified_terms_reviews` only if missing
  (they are excluded from the main create_all, so a failure there cannot skip the admin seed or other
  tables), adds the 5 cache columns only if missing (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on Postgres),
  each step with `SET LOCAL lock_timeout = '5s'` on Postgres. Additions only - nothing dropped or rewritten.
  Then it inspects the schema: `STATUS` = {ran, cache_ready, knowledge_base_ready, added, error}. On any
  failure it prints/logs "SCHEMA UPGRADE FAILED - app starting anyway; terms cache ON/OFF, knowledge base
  ON/OFF; error: ...". When not ready: the terms cache is neither read nor written (`terms_cache.schema_ready`
  guards reads, `cacheable` guards all 3 writes; reads also roll back and return None on any DB error), so
  lookups use saved records, discovery and defaults as before the cache existed; the knowledge base is
  skipped (`knowledge_base.ready`), its admin endpoints return 503; `/admin/terms-cache/stats` returns a
  `schema` block (always) and only a row count when not ready.
  Postgres DDL compiled for review (not run - no Postgres here): two CREATE TABLEs (SERIAL id, VARCHAR, JSON,
  TIMESTAMP, BOOLEAN) and five ADD COLUMN IF NOT EXISTS (TEXT x3, DOUBLE PRECISION, BOOLEAN).
  Tests (tests/test_schema_upgrade.py): upgrade of a legacy-schema DB adds only what is missing and keeps the
  existing row; second run adds nothing; a forced failure on the legacy DB is logged and a lookup still
  works without touching the cache; full app start-up (lifespan) with the upgrade failing: /api/health 200,
  login works, stats show the error, knowledge base 503. Full suite 491 passed, 2 skipped.
  Code rollback note: the previous code (eac60ead) maps only the old cache columns, so it runs fine on the
  upgraded schema; the added columns/tables need not be dropped to roll back.
- [x] 96.2 Production backup by the owner with `scripts/backup_prod_db.ps1` (hidden prompt; the password goes
  to pg_dump only through a temporary PGPASSWORD; verified with pg_restore --list):
  C:\Users\lenovo\swh_backups\swh_prod_2026-10-05_0106.dump, 1.23 MB, "OK". The script's "Tables: 72" counted
  TABLE and TABLE DATA entries together: production has 36 tables, all with data; count fixed in `03f6a0ab`.
  The owner's earlier screenshot showed the production DB password inside a connection URL: advised to rotate
  it in Railway (owner action; I did not use it).
- [x] 96.3 Pushed `eac60ead..03f6a0ab` (16 commits: entry 94's 5, entry 95's 9, 96.1, and the backup script +
  its fix). Deployed 2026-10-05 01:10 (detected by /admin/terms-cache/stats turning from 404 to 401).
  Live checks: `/api/health` 200 {"status":"ok"}; `/health/ocr` 200 ok, paddle active, warm-up ok in 66.7 s,
  first call after deploy 47.8 s; `/login` 200; http://www -> 301 -> https, 1 redirect, no loop;
  `/admin/terms-cache/stats` and `/admin/knowledge-base` without login -> 401. The admin stats call (with its
  `schema` block showing whether the Postgres upgrade succeeded) is left to the owner; no production
  credentials used. Railway's health-check path was never confirmed (not in the repo); the deploy went live.

- [ ] 96.4 Deploy log check for "SCHEMA UPGRADE FAILED": NOT possible from here (no Railway CLI or log
  access; not installed / signed in on the owner's account). Owner to check Railway > service > Deployments >
  latest (03f6a0ab) > logs: "SCHEMA UPGRADE FAILED" = upgrade failed (app still runs, cache/KB off);
  "Schema upgrade: added {...}" on the first start = success; or the `schema` block of
  /admin/terms-cache/stats. Re-check 2026-10-05 01:16: /api/health 200 ok; /health/ocr 200 ok (paddle,
  0.49 s, cached); /login 200; http -> https one 301, no loop. The owner's "backup done" + "push the 14"
  message arrived after the push had already been made (96.3); nothing new was pushed.

### State at the end of this entry
- origin/master = `03f6a0ab` (live). Local only: the STATUS/MEMORY commits for 96.3-96.4.

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| 96.1 | `1d8c127d` | 491 passed, 2 skipped (+3) | Guarded schema upgrade; cache/KB fall back when it fails. |
| 96.2 | `49cdfc7d` + `03f6a0ab` | 491 passed, 2 skipped | Backup script; table count fix. |
| 96.3 | `5b479703` | 491 passed, 2 skipped | Push + live checks; STATUS.md. |
| 96.4 | `31476ad6` | - | Deploy-log check not possible here; re-check. |

## 97. UI + content fixes from live test 1 (Samsung M17e invoice, 2026-10-05)

Owner tested the live site with a real Samsung Galaxy M17e 5G invoice (warranty wty_2cd9b3be) and sent the
downloaded summary PDF (image-only; rendered locally to read it) and screenshots. 11 items; local commits,
not pushed. Live findings (the owner's screenshots): claim steps "Out of Warranty Repair Charges / Digital
Service Center / Service Center" first; "Loaded (variant B)", a debug "Summary: template | Terms: ..." line,
raw warranty-ID inputs and "AGENTIC_WORKFLOW_ENABLED" text shown to the customer; guided check via
browser prompt() with "Not turning on" pre-filled and "Noise" offered for a phone; 59 notifications badge;
appliance wording ("machine or cabinet"), international-warranty clause, "external factors/medium/data
types" fragment and two near-identical "company's obligation" terms; label "Approved OEM source - checked
on ..."; Easy summary Pros containing a caution; "Claim: eligible - Claim is within coverage window" with
serial not confirmed; "How to look after it" showing only a placeholder; export without source/date/
evidence/purchase date; all care tips "MEDIUM"; two note boxes describing notes differently.

### Checklist
- [x] 97.1 Claim steps. New `app/services/customer_content.py`; `tidy()` runs in
  `MemoryStore._row_to_warranty`, so every display path (dashboard payload, summaries, export) gets cleaned
  content for new and old records; the database keeps the parsed OEM text. `clean_claim_steps`: drops labels
  (no instruction verb, <= 6 words, not a sentence), strips "Type of Service (X) -" prefixes, de-duplicates,
  and for an in-warranty product moves out-of-warranty/chargeable steps to the end. If every step was a
  label: two neutral steps (keep invoice + serial; contact <Brand> support or an authorized service center).
  Tests: tests/test_customer_content.py (live steps; ordering; fallback; store vs DB).

- [x] 97.5 Terms for phones (done before 2-4: same module). Live finding: samsung.com/in/support/warranty is one
  page with product sections (h3 "Mobile Phones", "TV & AV", "Home Appliances", "PC & OFFICE"); the parser
  read the whole page, so phones got appliance terms. Measured on the live page 2026-10-05: whole page ->
  duration 120 months (!), appliance exclusions, nav claim steps; mobile section -> 12 months, mobile
  terms, the mobile exclusion list.
  - `warranty_parser.section_text(html, product_line)`: when a page has >= 2 known product-section headings,
    only the section(s) for the product line are read (PRODUCT_SECTION_HEADINGS; smartphone = "mobile
    phones"/"mobile"/...). `parse_terms_from_url(..., product_line=)` / `parse_terms_from_html` use it and skip
    the page-wide OEM blocks when a section was used; `lookup_terms` passes the scope's product line.
  - Exclusion headings now include "not applicable in any of the following" and up to 12 exclusions are kept
    (was 6, which cut "lightning, abnormal voltage").
  - Display (customer_content.clean_terms, via tidy): for phones drop appliance wording (machine or cabinet,
    machine/unit, compressor, installation, site (premises, hard disk) and the international/overseas clause;
    for all products drop slash-joined fragments ("external factors/medium/data types") and near-duplicates
    (stem Jaccard >= 0.55, the longer one kept). Cleans stored records such as wty_2cd9b3be on display.
  - Label: `source_trust.official_page_label` -> "From <Brand> <Country>'s official warranty page" (country
    from a path segment like /in/, en-in, us-en, or a country domain like .in / .co.in; registry " India"
    suffix dropped from the brand), for approved, verified and (with " (manually confirmed)") manual sources.
    Confirmed labels still end "- checked on <date>".
  Tests: phone terms/exclusions; tidy on display; section parsing of a multi-product page; label.

- [x] 97.6 Easy summary. Pros = positive facts only (coverage shown, repair/replacement of defects, printhead);
  the "International support may be limited" caution is gone from Pros. Limits come from
  `summary_engine.limits_from_text` over terms + exclusions + claim steps: wear and tear (phones: "Normal wear
  of the battery, display and camera lenses is not covered."), abnormal voltage/power surges/lightning,
  unauthorized repair/modification (also when repairs must be "carried at ... authorized service"),
  liquid/water, accidental/misuse, serial number removed, consumables. Generic filler removed ("Read
  exclusions carefully...", "Coverage details are partially available...", "No explicit exclusions...",
  "Claim process is not fully available yet."); empty sections are hidden in the dashboard (was "Not
  available yet."); layman text is HTML-escaped. Approved-source note: "Terms came from the brand's official
  warranty page." Tests: phone summary from the live M17e text; non-phone wording; empty sections. One old
  test updated to the new liquid wording.

- [x] 97.7 Claim wording. `customer_content.claim_wording` (used by `_build_warranty_status_info` and the
  warranties list): within the period and no serial stored -> claim_eligibility "within_period", message
  "Within warranty period - <Brand> decides eligibility"; with a serial -> still "eligible" but the message
  says "Within warranty period - <Brand> confirms each claim" (was "Claim is within coverage window.").
  Expired/unknown unchanged. Dashboard line shows only the sentence ("Claim: Within warranty period -
  Samsung decides eligibility"), not the raw code. Tests: helper + GET /warranties/{id}.

- [x] 97.9 Export + grounding correction (one commit).
  - Export (`/warranties/{id}/export`, txt/html/pdf) is built by `customer_content.export_text` from the cleaned
    warranty: product, brand/model, serial (or "not confirmed"), purchase date, coverage + expiry, claim
    wording, evidence label, "Checked on", source URL, terms / not covered / how to claim, and a disclaimer
    ("Smart Warranty Hub is not the warranty provider..."). Title "Warranty summary - <product>" (was the raw
    warranty id); file name warranty-summary-<product-slug>-<date>.<fmt>. HTML export now escapes the text.
    fpdf deprecations fixed (Helvetica, text=, output()).
  - `tidy` drops a generated "Standard coverage for N months" line that contradicts the stored coverage.
  - Owner correction (2026-10-05): every customer-facing line must be grounded in the source text.
    `limits_from_text` now names only what the source names: wear and tear lists only the parts mentioned
    ("of camera lenses, batteries or displays"); causes ("lightning or abnormal voltage"), water words,
    misuse words as found; "Repairs or changes by unauthorized people are not covered." only if the source
    says "unauthorized" ("Modifications or alterations are not covered." if it only names those). A source
    that only says repairs are carried at authorized service centres gives the Claim-effort line "Repairs are
    done at <Brand> authorized service centres." (`service_route_lines`), not a "void" warning.
  - Two older tests updated to the grounded wording. Tests: export endpoint (all fields, no 60 months, no nav
    labels, no appliance wording; html/pdf), limits grounding.
- Redmi live-test steps B-D: none exist (owner: "no Redmi live test"); skipped.

- [x] 97.2-3 Customer UI and guided check (one commit, same template).
  - Item 2: CSS `body:not(.is-admin) .admin-only {display:none}`; `loadSessionRole()` reads /auth/session and sets
    body.is-admin for role=admin. Admin-only: the "Your ID" field, the manual Product/Warranty ID field and its
    "Or enter ID manually" note, warranty ids in "Saving for ..." labels and the notes context line, the raw
    "Summary: template | Terms: ... | Evidence ..." line (customers see the evidence panel), "Loaded (variant X)"
    (customers: "Product details loaded."), and the agent card when the agent is disabled (the
    AGENTIC_WORKFLOW_ENABLED message). The hidden inputs stay in the DOM, so the page still works.
  - Item 3: `askDiagQuestion` renders each question as an inline form (radio buttons, nothing pre-selected,
    Next disabled until an answer is picked, "Not sure / skip"); no window.prompt in the guided check.
    `guided_diagnostics._question_flow` now uses the product-line taxonomy (was raw substrings, so "Black" in a
    phone's name matched "ac"): per-line main-problem options (phone: not turning on, battery drains fast,
    overheating, screen or display, charging, camera, network, other - no "Noise"), phone/laptop safety
    question about battery swelling; `_probable_issue` maps the new options.
  - Tests: tests/test_customer_ui.py (page markup gating, session role, phone options, form, session API).

- [x] 97.4 Notifications. The owner's production account (59 unread) could not be counted from here (no
  production credentials). Code review + local DBs: alerts are de-duplicated per (user, warranty, type, unread,
  7 days), so every re-upload of the same invoice (a new warranty row) repeated onboarding / risk / expiry
  alerts (local partd.db: 8 "warranty_onboarded" for 8 uploads); admin accounts also get OEM/KPI alerts.
  - Fix: `notifications.product_key` (brand + model or product name + purchase date); `create_notification`
    skips an alert when the same user already has an unread one of that type within 7 days for the same product
    on another warranty (user audience only; needs all three parts; a different model or purchase date is a
    different product).
  - New GET /notifications/summary: unread_total, unread_by_type, duplicates_same_warranty,
    duplicates_same_product (ids), extra_from_duplicates - the owner can open it in the browser while signed in.
  - SECURITY FIX found here: GET /notifications?user_id=<anyone> and POST /notifications/{id}/read with a
    user_id let any signed-in user read/mark another user's notifications. Now `_notification_owner`: own only;
    another user's only for an admin (403 otherwise).
  - Tests: tests/test_notification_dedup.py (3).

- [x] 97.8+10+11 Care tips, "How to look after it", notes wording (one commit, same template).
  - Item 10: `product_recommendations._append_oem_care` rewritten: every "why" names only what the terms say
    ("Samsung's terms exclude damage from lightning and abnormal voltage."); abnormal voltage/lightning/
    surges -> phones/laptops "Charge with the original charger and use surge protection", appliances "Use a
    stabilizer or surge protector" (was appliances only); water words -> "Keep it away from water";
    unauthorized -> "Use only authorized service centres" only if the terms say "unauthorized", otherwise
    "Go to a <Brand> authorized service centre" / "Repairs are done at <Brand> authorized service centres.";
    claim docs. Priority by hazard (`_TIP_PRIORITY`): power HIGH, liquid HIGH, screen MEDIUM, authorized
    service MEDIUM, claim docs LOW; sorted; labels "From the warranty exclusions/terms/claim steps".
  - Item 8: "How to look after it" (#careSection) shows these terms-based tips (renderCareTips) with source
    and care priority, and is hidden when there are none; generic nudges ("Coverage Quick View") no longer
    fill it; Smart suggestions shows the other suggestions only (no duplicates).
  - Item 11: what the code does with notes (checked in code): saved with the product (needs analytics
    consent); identifiers stripped (sanitize_payload); error/failure raise the risk score, maintenance lowers
    it (derive_score), usage counts only as a number in "hours"; OEMs get counts by note type, never text,
    only for cohorts >= OEM_TELEMETRY_MIN_COHORT (default 10). Both note boxes now say exactly that (cohort
    size filled from the setting via __SWH_OEM_MIN_COHORT__); removed "used only to personalize care guidance"
    and "help improve risk insights and reminders". A typed number for "Usage hours" is now sent as hours.
    Bug fixed: sendTelemetry returned before setting "Saved.", so the status never changed.
  - Tests: tests/test_customer_ui.py (+4); two older recommendation tests updated to the new labels/order.

### Step log
| Step | Commit | Tests | Notes |
|---|---|---|---|
| 97.1 | `0a9ac4bf` | 495 passed, 2 skipped (+4) | Claim steps cleaned for display. |
| 97.5 | `5617482e` | 500 passed, 2 skipped (+5) | Phone section of multi-product pages; display filters; label. |
| 97.6 | `13cd7ebd` | 502 passed, 2 skipped (+2) | Easy summary: Pros/Limits, phone limits, no filler. |
| 97.7 | `4dc3f37f` | 504 passed, 2 skipped (+2) | Claim wording when the serial is not confirmed. |
| 97.9 | `6dd21ea2` | 506 passed, 2 skipped (+2) | Export with source/date/evidence/disclaimer; grounded limits. |
| 97.2-3 | `ce941e6b` | 511 passed, 2 skipped (+5) | Admin-only detail; guided check form and per-product options. |
| 97.4 | `c5f7da96` | 514 passed, 2 skipped (+3) | Product-level alert de-dup; summary; notification access fix. |
| 97.8+10+11 | (next) | 518 passed, 2 skipped (+4) | Grounded, ranked care tips; care section; notes wording. |


## 98. Customer experience run (started 2026-10-05)
Local commits, full tests after each step, no push. GLOBAL RULE from the owner for every step: fix the general
cause (any product, OEM, invoice, warranty type); brand-specific code only when unavoidable, named and tested;
test on a mix of product types, >=3 brands, text/scanned/photo, marketplace/shop invoices and warranty types;
say in the report when a rule cannot be made general yet.

### Checklist
- [x] 98.1 Document storage (read-only check; NO change to where files go until the owner approves).
  - `POST /artifacts/upload` (app/main.py ~1890) writes the file to `<repo>/data/uploads/upload_<id>.<ext>`
    = `/app/data/uploads` in the container. The Dockerfile has no VOLUME and the repo has no railway.toml/json;
    a Railway volume can only be set in the dashboard (not visible from here). Without a volume mounted at
    /app/data, every redeploy starts with an empty folder: all originals are lost.
  - No database row says which file belongs to which warranty or user: `artifacts` keeps only the extracted
    text; only `invoice_jobs.source_path` holds the disk path. So even files that survive cannot be listed
    per warranty, and older warranties have no original to show.
  - `object_store.put_bytes` (local or S3/R2 via OBJECT_STORE_* env, boto3 installed) exists but is used
    only by the review crawler.
  - Proposal (needs approval): new `documents` table (owner, warranty, kind, file name, type, size, sha256,
    uploaded_at) + a document store with three backends: `local` (today's behaviour, default), `db` (bytes in
    Postgres, recommended now: no new service or secrets, covered by the existing pg_dump backup, deleted with
    the row; 10 MB upload cap keeps it manageable) and `s3` (via object_store, for later at scale; needs a
    bucket + keys set by the owner). Switch = env `DOCUMENT_STORE=db` set by the owner on Railway.
- [x] 98.2 My documents. New `documents` table (DocumentDB; new table only, created by create_all, no ALTER),
  `app/services/document_store.py` (backends local [default, unchanged] / db / s3 via DOCUMENT_STORE),
  endpoints GET/POST /warranties/{id}/documents, GET /documents/{id}/file (?download=1), DELETE /documents/{id}.
  Owner-only, also for admin/OEM/TPA accounts (404 for anyone else). Invoice uploads keep their original.
  Same file twice for the same product is stored once. A file lost on redeploy shows "no longer available" (410).
  Dashboard: "My documents" panel with a type dropdown, view/download/delete, upload date and size.
  S3 delete of the bytes is not implemented yet (row is removed). Tests: tests/test_my_documents.py (8).
  Full suite 526 passed, 2 skipped.
- [ ] 98.7 STARTED, not committed: app/services/product_naming.py (short names, nickname, "Bought <date>
  from <seller>", icons, support ref) - untracked, not wired in. Found a general taxonomy bug to fix next:
  infer_product_category puts "Inverter" fridges/ACs under "inverter" (and "ups" matches as a substring).
- [ ] 98.3-98.6 not started (plain language, 5-line summary, product care design + source list, reminders).

## 99. Consolidated run 3 (2026-10-05). Same rules as 98 (global rule, local commits, no push).
Part 1 items 1-2 were already done in entry 97 (commits 0a9ac4bf..c7e48676); Part 2 items 4-5 in entry 98
(98.1 report, 98.2 = 1995378c). Storage switch to Postgres still waits for the owner's approval.

- [x] 99.3 Redmi live test B-D (synthetic invoices; no real Redmi file used).
  - Brand from the title, never the seller: `brand_registry.MAKER_OF_LINE` (Redmi, POCO -> Xiaomi). BRAND-SPECIFIC
    DATA on purpose: a general "domain owner" rule was measured over all 209 registry brands and rejected (it
    would rename 20 brands, e.g. Bajaj -> Bajaj Auto, Hero -> Hero MotoCorp). "Redmi Note 12 Pro" keeps "NOTE".
  - `ingestion.is_listing_code`: Amazon ASIN (B0...) / FNSKU (X0...) and Flipkart FSN never become a model.
  - IMEI: `luhn_ok`, `_imei_candidate`. 15 digits + Luhn -> stored; OCR-split groups joined only if Luhn passes
    (serial_evidence "imei_repaired"); otherwise a suggestion "This IMEI did not pass the IMEI check".
    A labelled "Serial Number" wins over an IMEI line; letters after "IMEI" are handled as a serial.
  - Order ID kept in alternatives["order_id"], never the invoice number.
  - Expired: `claim_wording` -> "Expired on 5 Jan 2024", claim_eligibility "expired"; unknown dates -> "Please
    check the purchase date on your invoice". Summary bullet "Unauthorized repair can affect claim eligibility"
    was ungrounded when terms only said "authorized" -> now "Repairs are done at authorized service centres."
  - Combined PDF: GET /warranties/{id}/export/combined?include_invoice&hide_address (owner-only, in memory,
    Cache-Control no-store, nothing stored). `app/services/combined_export.py`: summary + invoice (PDF pages,
    photo, text). Hide address = customer block under Bill to/Ship to/Billing/Shipping/Delivery address/
    Customer/Buyer (+ phone) removed with real PDF redaction (text gone), OCR boxes for photos/scans; if no
    block is found -> 422 "We could not find your address..." (never claims it was hidden). Dashboard:
    "Include invoice" / "Hide my address" checkboxes + "Download claim PDF".
  - Tests: tests/test_redmi_steps.py (38; brands Xiaomi/Samsung/LG/Voltas/Philips/Epson; Amazon, Flipkart,
    shop; text PDF, photo with OCR, text file). Full suite 564 passed, 2 skipped.
- [x] 99.8 Product names instead of IDs. `app/services/product_naming.py`: short name from the title (cut at the
  first separator, sizes/specs/colours removed, brand in front; long feature lists -> brand + model + type),
  else brand + model, else type, else "Your product" (never an ID). Nickname per owner (new table
  `product_nicknames`, PUT /warranties/{id}/nickname, owner-only, 40 chars, empty clears) shown first.
  Second line "Bought 3 May 2026 from Croma"; identical name + line get "(2)", "(3)" (oldest first). Type icon.
  /warranties/list adds display_name, product_name_short, nickname, subtitle, icon, type_label; display_label
  is "<icon> <name> - <second line>" (admin also gets "| Ref XXXXXX | <old label with invoice no>" and
  support_ref). Placeholder records fall back to the parsed invoice fields. Customer dashboard: the typed
  "Product / Warranty ID" field is not sent at all (server removes <!--ADMIN_ONLY--> blocks; hidden input
  keeps the state); nickname box. PDF/text export: short name + "Support reference: Ref XXXXXX".
  General taxonomy bug fixed: "Inverter" fridges/ACs/washers/microwaves were power inverters and "ups"
  matched inside words (also scoped the terms lookup wrongly). Tests: tests/test_product_names.py (25),
  one older list test updated to the new label. Full suite 589 passed, 2 skipped.
- [x] 99.6 Plain language. Customer page: OCR/AI/Pred chips, raw JSON link, "Advanced settings"/access key,
  "Technical view" JSON box and the brand-fetch modal are admin-only; reworded labels ("Your products", "Show
  this product", "Why this estimate?", "Looking after it", upload progress "Reading the text in your photo...",
  "Checking the brand's warranty terms...", "Done! Your product details are ready."); raw job errors and
  "Upload error: <exception>" only for admin. Where-the-terms-came-from labels/notes (summary_engine +
  source_trust) rewritten without OEM/cache/default rules/fixture ("Estimated, please check" for typical terms).
  behaviour_questions: "The brand's warranty terms mention ..." (was "The OEM source mentions").
  Notifications: product label = nickname or short name, never "(wty_...)"; IDs left in older stored text are
  shown as the name; onboarding/risk texts plain and no longer claim "started health checks".
  Pickers: brand datalist from the registry (manual entry), number inputs for invoice amount and usage hours
  (note box switches to text for other note types), document-type options in plain words.
  Not done: dynamic JS strings were reviewed by search, not one by one; the OEM/admin pages were not changed.
  Tests: tests/test_plain_language.py (12; the visible-text check parses the customer page), 3 older tests
  updated to the new wording. Full suite 601 passed, 2 skipped.
- [x] 99.7 "Your warranty in 5 lines". `app/services/warranty_card.py`: five_lines() = (1) "Covered until 3 May 2027
  (6 months left)." / "Expired on ..." / "Your invoice says there is no warranty" / "Please confirm your purchase
  date..."; (2) "Covered: <first coverage term as written>"; (3) "Not covered: <grounded limits_from_text, else the
  first exclusion>"; (4) "If it breaks: <service route line or first claim step>", else "contact <brand or the
  seller> with your invoice and serial number"; (5) link to the original invoice in My documents, else "add it".
  Lines without a source say "Please confirm ..." with confirm=True; estimated terms or no brand -> tag
  "Estimated, please check". please_confirm = pending brand/model/serial/vision suggestions + missing date.
  detect_types(): part periods (compressor/motor/panel/battery/accessories/...), extended or protection plan
  bought (offers like "Extended Warranty Available" are not), pro-rata, starts at installation (line 1 asks to
  confirm the installation date), registration required, on-site, carry-in, seller warranty, no warranty and
  refurbished (invoice text only), international - each with the sentence it came from; shown as "Also: ...".
  GET /warranties/{id}/five-lines (warranty access; documents owner-only). Card at the top of the overview.
  Tests: tests/test_five_lines.py (24, 15 warranty-type cases over fridge/AC/phone/TV/laptop/battery/
  purifier/washer/small appliance/printer/camera + 3 no-false-positive cases). Full suite 625 passed, 2 skipped.
