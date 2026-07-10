# Smart Warranty Hub — Complete Project Reference

**Repository:** Smart Warranty Hub MVP (`master`)
**Architecture:** FastAPI + Jinja HTML dashboards + SQLAlchemy + SQLite by default; PostgreSQL is supported through `DATABASE_URL`.
**Primary purpose:** turn customer invoices, product details, behaviour and telemetry into a usable warranty record, understandable coverage information, risk/advisory signals, service workflows, and OEM aggregate intelligence.

This is the single handoff document for a new engineer, investor, or migration assistant. It describes what is in the repository now, how the pieces connect, and which capabilities need real production integrations before commercial rollout.

### Latest verified safeguards

- OCR connector aliases (`paddleocr`, `paddle`, `pytesseract`) are normalized; image OCR uses a Tesseract fallback if Paddle cannot run.
- OCR health checks package availability without loading an OCR model.
- Review crawl/stat paths are owned by one modular router each, so FastAPI route matching is deterministic.

## 1. What the product does

### Customer journey

1. A customer signs in and opens the Care Dashboard.
2. The customer loads an existing product/warranty ID or uploads a receipt/invoice.
3. The ingestion pipeline saves the evidence, extracts text where possible, parses product fields, creates or updates a canonical warranty record, finds terms, and creates a customer-friendly summary.
4. The customer sees warranty status, coverage, exclusions, claim steps, expiry, risk explanation, care guidance, recommendations, notifications, behaviour questions, and diagnostics options.
5. Customer behaviour/telemetry can refine risk and recommendations over time.
6. For an issue, the product is routed to either safe remote diagnostics (IoT) or guided diagnostics (non-IoT), with optional service-ticket creation.

### OEM / operational journey

1. OEM/TPA/admin users sign in to the OEM dashboard.
2. They filter by product, brand, model and region; inspect risk, issue and demand signals.
3. They publish targeted customer questions or recommendations.
4. They can send governed communications, run controlled dispatches, view traces, and review KPI/watchdog/remediation information.
5. Scheduler jobs refresh operational signals and run maintenance tasks when enabled.

## 2. System map

```text
Customer/OEM/Admin browser
        │
        ├── Jinja templates (`templates/`)
        │       ├── Neo Care Dashboard
        │       ├── OEM Dashboard
        │       ├── Console/Admin/Scheduler
        │       └── Login/Public pages
        │
        └── FastAPI (`app/main.py`)
                ├── Auth + RBAC + ownership checks
                ├── Warranty / artifact / invoice pipeline
                ├── Behaviour / risk / predictive / recommendations
                ├── Notifications / service / diagnostics
                ├── OEM intelligence / communications / KPI
                └── Health, exports and UI routes
                        │
                        ├── SQLAlchemy data layer (`app/db*.py`)
                        │       └── SQLite `data/app.db` locally
                        ├── JSON/JSONL runtime caches under `data/`
                        ├── Optional OCR / LLM / search / OEM integrations
                        └── Optional scheduler
```

## 3. Runtime and deployment

### Local start

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\sqlite_migrate.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- Customer Care: `http://127.0.0.1:8000/ui/neo-dashboard`
- Console: `http://127.0.0.1:8000/ui/console`
- OEM dashboard: `http://127.0.0.1:8000/ui/oem-dashboard`
- Scheduler: `http://127.0.0.1:8000/ui/scheduler`
- Admin hub: `http://127.0.0.1:8000/ui/admin-hub`
- API documentation: `http://127.0.0.1:8000/docs`

### Deployment files

| File | Purpose |
|---|---|
| `Dockerfile` | Python 3.11 Debian image; installs Tesseract, Poppler, OpenCV runtime libraries and application dependencies. |
| `run_app.py` | Starts Uvicorn using Railway’s `PORT` environment variable, defaulting to 8000. |
| `requirements.txt` | Python runtime dependencies. |
| `.gitignore` | Excludes venvs, database files, uploaded evidence, cookies, logs, env files and JSONL runtime stores. |
| `docs/deployment_config_reference.md` | Environment and Railway deployment guide. |

### Security configuration required before production

- Set a strong `JWT_SECRET` and `JWT_SALT`.
- Set `ADMIN_USER` and `ADMIN_PASS`; set `ALLOW_INSECURE_DEFAULTS=false`.
- Configure `ALLOWED_HOSTS` for the deployed domain.
- Use managed PostgreSQL and object storage for production; SQLite and local files are suitable for local/demo use, not a multi-instance production deployment.
- Do not commit `.env`, `cookies.txt`, `data/app.db`, `data/uploads/`, or API tokens.

## 4. Intelligence core: how SWH fills the gaps an invoice cannot answer

An invoice is evidence of a sale. It normally does **not** contain the complete warranty contract: it may omit coverage duration, exclusions, regional terms, claim process, registration requirement, serial number, product model, or whether an extended warranty applies. SWH is designed to turn that incomplete evidence into a transparent, confidence-aware best available warranty record.

### 4.1 Evidence-first warranty resolution flow

```text
Invoice / receipt / manual product entry
        │
        ├── Extract text and fields: brand, product, model, purchase date,
        │   seller, invoice number and serial number when present
        │
        ├── Create/update canonical product + warranty record
        │
        ├── Check existing customer warranty records and cached terms first
        │
        ├── If terms are missing: use brand/model/product/region to discover
        │   likely official OEM sources, preflight domains, parse useful pages
        │
        ├── If confidence is still low: ask the customer only the smallest
        │   useful follow-up (for example serial number, country/region, or
        │   product/model confirmation)
        │
        └── Return terms/expiry/summary with source and confidence context;
            use safe default rules when no official source is available
```

### 4.2 Invoice understanding

- `app/services/ocr.py` extracts PDF text first and only tries OCR for weak text; this keeps memory and cost low.
- `app/services/ingestion.py` uses deterministic patterns and heuristics to identify brand, product name/category, model code, serial/IMEI, invoice number, purchase date and coverage duration where these occur in the evidence.
- `app/services/invoice_pipeline.py` persists raw parsing results and confidence, updates the canonical warranty, then performs lookup and summary stages.
- Missing fields are not silently invented. A missing serial, country/region, product class or model stays low-confidence and is a valid reason to ask a short follow-up question.

### 4.3 Warranty-source discovery, web search and preflight controls

The system does **not** blindly crawl every web page. It performs bounded, policy-controlled discovery:

1. Check an already known warranty record for the same product.
2. Check `WarrantyTermsCacheDB` for a fresh brand/category/region result.
3. Load known and verified OEM domains from `app/services/oem_domains.py`.
4. Preflight allowed OEM domains in `app/services/warranty_discovery.py` using host/domain checks and lightweight availability checks.
5. Prefer verified/official domains, product manuals and warranty pages. Region and model/product matching influence ranking.
6. When configured, use bounded web search (`TERMS_SEARCH_MAX_QUERIES`, `TERMS_SEARCH_MAX_RESULTS`, timeouts) to find candidate pages; `TERMS_OFFICIAL_ONLY` can prohibit non-official results.
7. Parse terms with deterministic HTML/PDF/text rules in `app/services/warranty_parser.py`.
8. Cache successful structured results in `WarrantyTermsCacheDB` and apply regional policy.
9. If no reliable source exists, use transparent category defaults rather than claiming an OEM-confirmed result.

`app/scrapers/acmeco.py` and `app/scrapers/zenith.py` are examples of brand adapters. For a real OEM, add an approved adapter/API, verified domains and regional rules. This is safer and more maintainable than scraping every OEM site without permission.

### 4.4 Mistral NLP, RAG and deterministic fallback

SWH uses AI as an optional enrichment layer, not as a single point of failure.

| Layer | What it uses | Why it exists | Fallback |
|---|---|---|---|
| Terms NLP | `app/services/warranty_parser.py` | When deterministic parsing is incomplete or low confidence, it can ask Mistral for strict structured terms/exclusions/claim-step JSON. | Deterministic parsed terms and default rules remain authoritative. |
| Warranty summary | `app/services/summary_engine.py` | Can create a shorter customer-facing explanation through Mistral, Ollama, or local llama.cpp. | Template summary from canonical warranty data. |
| RAG embeddings | `app/services/rag.py` | Uses Mistral embeddings to index/retrieve relevant warranty, behaviour, telemetry, issue, review and diagnostic context. | Empty RAG context; normal rules/models continue. |
| Predictive RAG context | `app/services/predictive.py` | Adds related historical/contextual information to the explainable risk calculation when RAG is enabled. | Standard feature vector, policies and heuristic/model scoring. |

RAG is enabled only when `RAG_ENABLED=1` and `MISTRAL_API_KEY` is present. It stores document embeddings with metadata, supports strict metadata filters (for example warranty/user/region), and retrieves only relevant context. It is not a general uncontrolled chatbot and should be evaluated for retrieval quality, permissions and privacy before production use.

### 4.5 Behaviour intelligence and predictive care loop

The customer journey is not limited to the invoice:

1. `app/services/behaviour_questions.py` supplies small, deterministic questions such as location of use, usage level, voltage conditions, environment or installation context.
2. OEM-published questions from `app/services/oem_question_service.py` can be shown first if they match brand/model/product type/region and have not already been answered.
3. Answers are stored against the user and warranty, avoiding repeat questions.
4. Telemetry, saved usage notes, nudge outcomes, behaviour answers, regional policy, peer reviews, symptom searches and OEM issue signals become inputs to `app/services/predictive.py`.
5. The predictive response exposes a risk label/score plus reasons, base score and behaviour adjustments so the UI can explain **why** it made a recommendation.
6. Advisories, care suggestions, expiry notices and product recommendations are then selected from the resulting product/risk context.

The design principle is to ask for a small amount of missing information only when it improves confidence or care guidance. It should not repeatedly ask every user for a full form.

### 4.6 IoT and non-IoT support: agentic but controlled

SWH has two separate support flows after a customer reports an issue:

| Product capability | Flow | What happens |
|---|---|---|
| IoT / connected product | Remote diagnostics | `diagnostics_capability.py` selects the path. `remote_diagnostics.py` creates a session and safe command request. Commands can require review/approval, use an OEM connector, record request/response traces, and write meaningful results back to telemetry/RAG. |
| Non-IoT product | Guided diagnostics | `guided_diagnostics.py` asks product-aware troubleshooting questions, collects evidence, estimates a probable issue/confidence/priority, recommends authorised service centres and can create a service ticket. |

This is **guided/agentic orchestration**, not an unrestricted autonomous agent. It may ask for warranty ID, serial, symptom, city/region, photographs or logs when those details are needed. For remote device actions, explicit consent, connector configuration, command allowlists and human review are the production safety boundaries.

### 4.7 OEM aggregate intelligence

OEM users do not need to inspect individual raw invoices to gain value. The OEM layer aggregates and filters privacy-controlled operational signals such as:

- risk distribution and forecast by product/brand/model/region;
- OEM issue signals and approved review trends;
- anonymized/controlled behaviour and recommendation-interest signals;
- product recommendation demand (`/events/product-interest`);
- customer questions/recommendations targeted by product context;
- communication eligibility, rate limits and dispatch policy traces.

The future production version should enforce tenant isolation, consent purpose, aggregation thresholds and data-sharing agreements before exposing any customer-derived insight to an OEM.

## 5. Important UI files

| File | Page / responsibility | Main user-visible features |
|---|---|---|
| `templates/neo_dashboard.html` | `/ui/neo-dashboard` | Customer product/warranty loading, formatted summary, Step 2 details/care, receipt upload/camera/manual entry, usage/health log, behaviour question, recommendations, notifications and diagnostics entry points. |
| `templates/oem_dashboard.html` | `/ui/oem-dashboard` | OEM filters, risk/product analytics, Question Studio, Recommendation Studio, communications/issue intelligence and charts. |
| `templates/console.html` | `/ui/console` | Power-user console for warranty, summary, advisory, OCR/predictive/telemetry inspection. |
| `templates/login.html` | `/login`, `/auth/login` | Sign-in, sign-up and auth messages. |
| `templates/admin_hub.html` | `/ui/admin-hub` | Admin policy/KPI navigation surface. |
| `templates/scheduler.html` | `/ui/scheduler` | Scheduler queue/status operations. |
| `templates/react_dashboard.html` | `/ui/react-dashboard` | Redirect/front-end development surface where configured. |
| `templates/warranty.html`, `templates/warranty_tabs.html` | Warranty-focused views | Alternative warranty presentation pages. |
| `templates/public_site.html` | `/` | Public landing page. |
| `templates/simple_upload.html` | Upload helper view | Basic artifact-upload surface. |
| `static/warranty-dropdown.js` | Shared small browser helper | Warranty dropdown behaviour. |

### Care Dashboard design rules already implemented

- Step 2 (Details & Care) is the only section controlled by **See full summary**.
- Step 3 (bill/receipt) and Step 4 (usage & health) remain separate from that toggle.
- Product context is presented as product name/brand/model plus the technical warranty ID where data is available.
- Raw warranty JSON is intended for debug mode only; customer views use formatted terms, exclusions and claim steps.

## 6. Core backend files

| File | Purpose |
|---|---|
| `app/main.py` | Main FastAPI application: request models, authentication endpoints, UI routes, health, warranty APIs, invoice upload, risk, notifications, OEM APIs, admin controls and exports. This is the primary route registry. |
| `app/db.py` | Selects SQLite or PostgreSQL from `DATABASE_URL`, creates SQLAlchemy engine/session factory. |
| `app/db_models.py` | Persistent SQLAlchemy models: users, warranties, artifacts, ownership, parsed fields, pipeline jobs, summaries, telemetry, notifications, OEM/review/KPI/diagnostic entities. |
| `app/deps.py` | Cookie/Bearer JWT authentication, password hashing, role guards (`user`, `oem`, `tpa`, `admin`), DB dependency and initial database/admin seed. |
| `app/models.py` | Pydantic/domain models used by canonicalization, risk, nudges and service workflows. |
| `app/storage.py` | Legacy in-memory store, ID generation and compatibility support for older flows. |

### Authentication and access model

- `POST /auth/signup`: creates allowed users under the role rules.
- `POST /auth/login`: authenticates and sets an `access_token` HTTP-only cookie; it may return a redirect for browser flows.
- `POST /auth/logout`: clears the auth cookie.
- `GET /auth/session`: returns signed-in user state.
- Protected endpoints accept the access-token cookie or an `Authorization: Bearer <token>` header.
- Warranty ownership is checked for customer access; OEM/TPA/admin routes have stronger role guards.

## 7. Feature-to-file wiring

### 6.1 Invoice / artifact ingestion and warranty creation

| Component | File(s) | What it does | Readiness |
|---|---|---|---|
| Upload API | `app/main.py` (`POST /artifacts/upload`) | Saves uploaded evidence, creates artifact/warranty records and starts the pipeline. Returns artifact, warranty ID, job ID and status. | MVP implemented |
| Camera capture API | `app/main.py` (`POST /artifacts/capture`) | Captures a server-side/default-camera frame when supported, stores it and runs equivalent extraction. Browser camera UI uses regular upload of captured content. | Environment dependent |
| Pipeline | `app/services/invoice_pipeline.py` | Runs stateful stages: `uploaded → extracting_text → ocr_if_needed → parsed_fields → terms_lookup → summarized → done/failed`. Persists job status. | MVP implemented |
| Ingestion parser | `app/services/ingestion.py` | Regex/heuristic extraction of invoice/product fields; no heavy model required. | Implemented; accuracy depends on input quality |
| Canonicalizer | `app/services/canonical.py` | Turns artifacts/extracted fields into a normalized warranty object, terms structure and expiry calculation. | Implemented |
| Warranty parser/discovery | `app/services/warranty_parser.py`, `app/services/warranty_discovery.py` | Parses warranty terms and searches/normalizes possible warranty sources. | Partial; external-source reliability varies |
| Pipeline storage | `app/db_models.py` | `PipelineJobDB`, `ParsedFieldDB`, `WarrantySummaryDB`, artifact/warranty records. | Implemented |
| Schema safety | `scripts/sqlite_migrate.py` | Idempotent SQLite repair/migration for known schema drift, including `climate_zone` and pipeline tables. | Implemented |

### 6.2 OCR and document text extraction

| File | Purpose |
|---|---|
| `app/services/ocr.py` | Lazy extraction. Attempts PDF text extraction first; normalizes Paddle/Tesseract engine aliases and uses Tesseract as a fallback when Paddle is unavailable. Handles unavailable engines without crashing the pipeline. |
| `app/services/object_store.py` | Local/object storage abstraction for file handling. |
| `scripts/verify_ocr_extraction.py`, `scripts/verify_paddle.py`, `scripts/eval_ingestion_ocr.py` | Verification and evaluation helpers. |
| `docs/ocr-nlp-options.md`, `docs/ingestion_ocr_kpi_runbook.md` | OCR choices and benchmark/runbook notes. |

**Production reality:** OCR is not guaranteed merely because the code exists. Tesseract must be installed in the runtime, or Paddle dependencies/model support must be available. `/health/ocr` reports actual availability. Degraded OCR does not stop text/PDF-based ingestion; it limits image-only extraction.

### 6.3 Terms lookup, scraping and warranty summary

| Component | File(s) | Purpose | Readiness |
|---|---|---|---|
| Terms lookup | `app/services/terms_lookup.py` | Cache-first lookup, optional scraping, fallback warranty rules and structured sections. | Implemented with fallback |
| OEM scrapers | `app/scrapers/acmeco.py`, `app/scrapers/zenith.py` | Example lightweight official-source adapters. | Example adapters; not universal OEM integration |
| Search | `app/services/web_search.py` | Bounded/controlled web lookup helper. | Optional; requires external search configuration |
| Summary engine | `app/services/summary_engine.py` | Produces a summary via optional LLM provider or deterministic template. | Implemented with no-LLM fallback |
| Generic LLM connector | `app/services/llm.py`, `app/services/connection_registry.py` | Connector registry and generation path for configured LLMs. | Integration dependent |
| Exports | `app/services/exporter.py` | Summary export in TXT, HTML and PDF. | Implemented |

**Production reality:** deterministic templates and fallback rules work without AI. Scraping should remain feature-flagged (`TERMS_SCRAPE_ENABLED`) and treated as best effort, because OEM sites can change, block requests or require formal API partnerships.

### 6.4 Behaviour, risk, predictive care and recommendations

| Component | File(s) | Purpose |
|---|---|---|
| Behaviour events | `app/services/behaviour.py` | Records user behaviour signals used by risk/nudges. |
| Behaviour questions | `app/services/behaviour_questions.py` | Deterministic customer question bank and JSONL fallback for answers. |
| OEM questions | `app/services/oem_question_service.py`, `app/services/ollama_questions.py` | OEM-targeted questions; optional Ollama generation with deterministic fallback. |
| Base risk | `app/services/risk.py` | Rule-based risk computation. |
| Predictive engine | `app/services/predictive.py` | Builds feature vectors from warranty, telemetry, behaviour, region and issue context; uses trained model if present, heuristic fallback otherwise; returns explanations. |
| Regional policy | `app/services/regional_policy.py` | Region/brand/model product policy adjustments. |
| Risk refresh | `app/services/risk_refresh.py` | Snapshot/refresh support. |
| Advisories and nudges | `app/services/nudge.py`, `app/services/nudges.py`, `app/services/policy.py` | Care, expiry, lapsed and risk-aware guidance; policy/variant support. |
| Customer recommendations | `app/services/recommendation.py`, `app/services/product_recommendations.py` | Care recommendations plus deterministic product suggestions by product/risk/region. |
| OEM recommendations | `app/services/oem_recommendation_service.py` | OEM recommendation create/list/disable persistence through JSONL fallback. |
| EV battery | `app/services/ev_battery.py` | EV-specific battery score and recommendation logic. |

**Production reality:** the core score/explanations are deterministic and locally testable. Any “trained” predictive model needs monitored production data, calibration, drift checks and governance before high-stakes automation. The repository’s benchmark figures are evaluation/synthetic evidence, not live production outcomes.

### 6.5 Notifications, service and diagnostics

| Component | File(s) | Purpose |
|---|---|---|
| Notifications | `app/services/notifications.py` | Creates/reads customer and OEM notifications; warranty-expiry/risk analysis helpers. |
| Service tickets | `app/services/service.py` | Symptom-to-part mapping and ticket draft creation. |
| Diagnostics capability routing | `app/services/diagnostics_capability.py` | Decides safe remote versus guided diagnostics route from product capability. |
| Remote diagnostics | `app/routes/remote_diagnostics.py`, `app/services/remote_diagnostics.py` | Session, command request, review/approval, connector call, execution trace and queue runner. |
| Guided diagnostics | `app/routes/guided_diagnostics.py`, `app/services/guided_diagnostics.py` | Non-IoT guided Q&A, evidence, probable issue, service-center suggestion and optional ticketing. |
| Service centers | `data/service_centers.json` | Local service-center lookup source. |

**Production reality:** guided diagnostics is usable without external hardware. Remote diagnostics needs a real OEM connector, an allowlist, consent, review gates and audited execution; keep automatic execution disabled until formal OEM validation.

### 6.6 OEM intelligence, communications and operations

| Component | File(s) | Purpose |
|---|---|---|
| OEM page/API | `templates/oem_dashboard.html`, `app/main.py` | Product filters, risk overview, forecast, issue/behaviour stats, questions and recommendations. |
| OEM questions router | `app/routes/oem_questions.py` | Alternative router implementation for question Studio endpoints. Main API also contains compatibility endpoints. |
| OEM recommendations router | `app/routes/oem_recommendations.py` | Alternative router implementation for recommendation Studio endpoints. Main API also contains compatibility endpoints. |
| OEM terms fetch | `app/services/oem.py`, `app/services/oem_parsers.py`, `app/services/oem_domains.py`, `app/services/oem_domain_verify.py` | Fetches and parses allowed OEM content; manages verified domains. |
| Issue signals | `app/services/oem_issue_feeds.py`, `app/services/oem_issue_signals.py` | Intake/aggregate OEM issue signals. |
| Communications | `app/services/oem_communication.py` | Eligibility, rate checks, traceable communication sends. |
| Dispatch | `app/services/oem_dispatch.py` | Policy-controlled dry-run/live OEM targeting and dispatch. |
| Product demand events | `POST /events/product-interest` in `app/main.py` | Captures customer interest in recommended products for OEM insight. |

**Production reality:** the dashboard and data contracts exist. Real OEM execution needs verified domains, a formal data-sharing agreement, connector credentials, tested recipient channels and legal/privacy review. Question/recommendation persistence uses JSONL locally; move to a managed database for scale.

### 6.7 RAG, reviews, data governance, scheduler and KPI

| Component | File(s) | Purpose |
|---|---|---|
| Retrieval/RAG | `app/services/rag.py` | Optional embeddings/context retrieval for summaries and prediction. |
| Reviews | `app/routes/reviews.py`, `app/services/review.py`, `app/services/review_crawler.py`, `app/services/review_sources.py`, `app/services/sentiment.py` | Review ingestion, moderation, crawling and sentiment inputs. |
| Governance | `app/services/data_governance.py`, `app/services/audit.py` | Consent/purpose/audit helpers. |
| Scheduler | `app/services/scheduler.py` | Startup-driven recurring OEM fetch, issue/risk/review/expiry/KPI/diagnostic tasks when enabled. |
| KPI scorecard | `app/services/kpi_scorecard.py` | KPI aggregation/report artifacts. |
| Watchdog/remediation/execution | `app/services/kpi_watchdog.py`, `app/services/kpi_remediation.py`, `app/services/kpi_execution.py` | Detects KPI concerns, builds remediation plans, tracks execution tasks. |

**Production reality:** these are operational tooling building blocks. A production rollout needs durable scheduling/queue infrastructure, alerting, retention policies, observability and ownership of each KPI action.

## 8. API map by business function

`/docs` and `/openapi.json` are the authoritative runtime list. Main groups are:

| Area | Principal endpoints |
|---|---|
| Health | `GET /api/health`, `/health/ocr`, `/health/llm`, `/health/predictive`, `/health/rag`, `/health/full` |
| Auth | `POST /auth/signup`, `/auth/login`, `/auth/logout`, `/auth/password/change`; `GET /auth/session` |
| Artifacts | `POST /artifacts`, `/artifacts/upload`, `/artifacts/capture` |
| Warranties | `GET /warranties/list`, `/warranties/{id}`, `/warranties/{id}/summary`, `/warranties/{id}/export`; `POST /warranties/from-artifact`, `/warranties/{id}/process`, `/warranties/summary`, `/warranty/terms/refresh` |
| Jobs | `GET /jobs/{job_id}` |
| Customer intelligence | `GET /behaviour/next-question`, `POST /behaviour/answer`, `/behaviour-events`, `/telemetry`, `/predictive/score`, `/risk/score`, `/recommendations`, `/advisories/{id}`, `/notifications`, `/notifications/{id}/read` |
| Service/diagnostics | `/service-tickets`, `/diagnostics/capability/{id}`, `/diagnostics/request-remote-check`, `/remote-diagnostics/*`, `/guided-diagnostics/*` |
| OEM | `/oem/questions/*`, `/oem/recommendations/*`, `/oem/products`, `/oem/risk-stats`, `/oem/forecast`, `/oem/issues*`, `/oem/communications/*`, `/oem/domains/*`, `/oem/fetch*` |
| Admin/KPI | `/admin/oem-dispatch/*`, `/admin/kpi-*`, `/admin/rag/smoke`, `/region-rules`, `/reviews*` |
| UI | `/`, `/login`, `/ui/neo-dashboard`, `/ui/console`, `/ui/oem-dashboard`, `/ui/admin-hub`, `/ui/scheduler` |

## 9. Database and local runtime data

### Persistent SQL tables

See `app/db_models.py` for the complete schema. Important groups include:

- identity/access: `UserDB`, `AuditLogDB`, `WarrantyOwnerDB`;
- customer data: warranties, artifacts, parsed fields, summaries, behaviour profiles/answers, telemetry, notifications, tickets;
- pipeline/terms: `PipelineJobDB`, `WarrantyTermsCacheDB`;
- OEM/operations: OEM fetch, issue signal, product reviews, recommendation/risk snapshots, regional policies;
- diagnostics/KPI: sessions/commands/traces and KPI history/task artifacts.

### Local filesystem data

- `data/app.db`: local SQLite database; deliberately ignored by Git.
- `data/uploads/`: invoice/evidence uploads; ignored by Git.
- `data/*.jsonl`: behaviour/OEM-question/OEM-recommendation fallback stores; ignored by Git.
- `data/connectors.json`: local connector registry.
- `data/service_centers.json`: guided-diagnostics support data.
- `data/kpi_phase*.json`: generated evaluation/report artifacts where present.

## 10. AI and automation: what is real now

| Capability | Current mode | Safe production statement |
|---|---|---|
| Invoice field understanding | Regex/heuristics plus optional OCR | Works for supported text patterns; requires measured accuracy on real invoices before automated decisions. |
| OCR | PDF text first, Tesseract/Paddle optional and lazy | Degrades gracefully if engine unavailable; production needs installed engine, image quality testing and monitoring. |
| Warranty summary | Deterministic template; optional LLM providers | A readable fallback always exists. LLM is enhancement only, not required to produce a summary. |
| OEM question generation | Deterministic question bank; optional Ollama | Use deterministic content by default; approve generated content before customer publishing. |
| Predictive risk | Rules/feature model with explainable reasons | Suitable for advisory/triage MVP. Do not use as a sole claims, safety or credit decision without calibration, monitoring and human governance. |
| RAG | Optional enrichment/context retrieval | Needs vector store, document permissions and evaluation before being relied on in production. |
| Web/OEM lookup | Optional scrapers/search + default rules | Best effort only until each OEM supplies a supported API or approved source. |
| Remote diagnostics | Connector-based, policy/review gated | Requires partner integration, explicit consent and safe allowlisted commands. |
| Scheduler | In-process scheduler | Fine for development/demo; move recurring production work to durable workers/queues. |

## 11. Production readiness plan

### Ready for local/demo/MVP validation

- FastAPI application, auth cookie flow and RBAC structure.
- Customer, OEM, console, scheduler and admin HTML surfaces.
- Warranty record lifecycle, terms/summary fallback, invoice job status, export.
- Behaviour questions, notifications, recommendations, telemetry and explainable risk flows.
- Guided diagnostics and service-ticket workflow.
- Health endpoints and automated/smoke/evaluation scripts.

### Before a limited pilot

1. Set production secrets and disable insecure defaults.
2. Move production state from SQLite/JSONL/local uploads to managed Postgres + object storage.
3. Add error tracking, request logging, backups, rate limiting and uptime monitoring.
4. Validate customer uploads, OCR and parser accuracy on representative invoices.
5. Obtain legal/privacy review for consent, retention, OEM aggregation and communication.
6. Configure a genuine email provider, OEM domains and approved sender/recipient policy.
7. Keep LLM/scraping/remote diagnostics feature flags conservative; test clear degraded experiences.

### Before broad production rollout

1. Replace in-process scheduler with durable job workers/queue and idempotency controls.
2. Add database migrations with version tracking and disaster recovery.
3. Integrate supported OEM APIs rather than relying on public-site scraping.
4. Add real analytics, model monitoring, drift/calibration, audit dashboards and human review processes.
5. Pen-test authentication/authorization and validate GDPR/DPDP/privacy/compliance obligations for target regions.
6. Load-test uploads, concurrent users, exports and scheduled jobs.

## 12. Tests, smoke tests and useful scripts

| Script/test | Purpose |
|---|---|
| `docs/GOLDEN_PATH_TEST.md` | Manual browser/API pre-deploy checklist. |
| `scripts/test_upload.ps1` | Windows login + authenticated upload helper. |
| `scripts/sqlite_migrate.py` | Safe local SQLite schema repair/migration. |
| `scripts/smoke_test_behaviour_*.py` | Behaviour question, answer and risk checks. |
| `scripts/smoke_test_notifications.py` | Notification read/list behaviour. |
| `scripts/smoke_test_oem_*.py` | OEM question, recommendation and customer-flow checks. |
| `scripts/smoke_test_product_*.py` | Product recommendation and interest-event checks. |
| `tests/test_invoice_pipeline.py` | Pipeline without OCR/LLM and mocked OCR text coverage. |
| `tests/test_warranty_*.py` | Discovery/parser/status tests. |
| `tests/test_kpi_*.py` | Scorecard/watchdog/remediation/execution checks. |
| `tests/test_notifications.py`, `tests/test_oem_communication.py`, `tests/test_oem_dispatch.py`, `tests/test_rag_health.py` | Supporting domain tests. |
| `scripts/eval_*.py` | Evaluation/KPI evidence generators; not a substitute for live business validation. |

Suggested local verification:

```powershell
python scripts\sqlite_migrate.py
python -m pytest tests -q
python -m py_compile app\main.py
powershell -ExecutionPolicy Bypass -File scripts\test_upload.ps1 -FilePath "C:\path\to\invoice.pdf"
```

## 13. Documentation reading order

1. This file: `docs/PROJECT_REFERENCE.md`.
2. `docs/HANDOFF.md` for a shorter engineering handoff.
3. `docs/GOLDEN_PATH_TEST.md` to test the customer journey.
4. `docs/product_manual_smart_warranty_hub.md` for business workflows.
5. `docs/feature_catalog_exhaustive.md` for module coverage.
6. `docs/oem_dashboard_and_integration_manual.md` for OEM integration.
7. `docs/deployment_config_reference.md` for Railway/operations.
8. `docs/complete_product_specification_and_kpi.md` and KPI runbooks for benchmark context.

## 14. Current repository audit notes

- The Git branch is `master`.
- Runtime-only venv/cache/database/upload files are intentionally ignored.
- At the time this document was created, `docs/OEM_Intelligence_Flow_Simple.pdf` and `scripts/generate_oem_intel_pdf.py` were untracked local files. Review and intentionally commit them only if they are desired project artifacts.
- `scripts/print_routes.py` imports `app.main`; when run directly, set the repository root on `PYTHONPATH` in PowerShell if needed: `$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe scripts\print_routes.py`.
- Main API routes for OEM questions/recommendations are currently present in `app/main.py`, while alternate router modules also exist under `app/routes/`. Consolidating duplicate route implementations is a future maintenance cleanup, not a required MVP change.

## 15. One-minute explanation for a new person

Smart Warranty Hub is a warranty intelligence MVP. A customer uploads an invoice or loads a product ID; SWH creates a structured warranty record, explains coverage and exclusions, estimates expiry/risk, provides care advice and supports diagnosis/service. OEM users see filtered aggregate signals and can publish targeted customer content under role and policy controls. The system works without an LLM or OCR model through deterministic fallbacks, while optional OCR, LLM, scraping, RAG, OEM connectors and automation add richer capability when configured. For production, the biggest remaining work is hardening storage/jobs/integrations/governance—not inventing a new product flow.
