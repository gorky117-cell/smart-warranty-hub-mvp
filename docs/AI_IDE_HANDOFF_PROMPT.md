# SWH AI IDE Handoff Prompt

Copy the complete prompt below into Kiro, Antigravity/Gemini, Cursor, VS Code Copilot, Claude Code, or another coding assistant after opening the repository folder.

---

```text
You are continuing development of Smart Warranty Hub (SWH), a FastAPI + Jinja HTML + SQLAlchemy warranty intelligence MVP.

YOUR FIRST RULES
1. Do not assume the product is fully enterprise production-ready. It is a strong demo/controlled-pilot MVP.
2. Preserve existing routes, API payloads, database fields, UI IDs and working flows unless the requested task explicitly requires a compatible change.
3. Do not rewrite working features or run destructive Git commands.
4. Do not commit secrets, `.env`, cookies, virtual environments, SQLite database files, uploads, logs, JSONL runtime data, `__pycache__`, or `.pyc` files.
5. Prefer targeted changes and test the smallest affected area first.
6. AI/OCR/search/OEM integrations are optional. The deterministic fallback path must always continue to work.
7. Do not claim live business accuracy/KPI impact from the synthetic evaluation data in this repo.

REPOSITORY LOCATION
Use the repository folder already opened in your IDE. Do not hard-code a developer-specific local path into source code or documentation.

GITHUB REPOSITORY
https://github.com/gorky117-cell/smart-warranty-hub-mvp

ACTIVE GIT BRANCH
Use `master`.

IMPORTANT GIT NOTE
An older `main` branch is diverged/outdated relative to the active work. Do not switch to, merge from, or deploy it unless the owner explicitly asks for branch reconciliation.

START EVERY SESSION WITH THESE COMMANDS IN POWERSHELL
```powershell
cd "<repository-root>"
git status -sb
git branch -vv
git log -8 --oneline
git remote -v
```

READ THESE FILES BEFORE EDITING
1. `MEMORY.md` — current engineering memory, repository facts, feature wiring, production boundaries and handoff rules.
2. `docs/PROJECT_REFERENCE.md` — full system architecture, major source files, AI/OCR/RAG/OEM details and production roadmap.
3. `docs/HANDOFF.md` — concise engineering handoff.
4. `docs/GOLDEN_PATH_TEST.md` — executable customer/API test flow.
5. `docs/DOCS_INDEX.md` — index of all technical/business documentation.
6. `README.md` — local quick start.

PROJECT PURPOSE
SWH converts receipts/invoices, known warranty IDs, behaviour and telemetry into a structured customer warranty/product record. It shows understandable coverage, exclusions, claim steps, expiry, risk, care guidance, notifications, recommendations and diagnostics. OEM/TPA/admin users see controlled aggregated intelligence and operational workflows.

CURRENT VERIFIED HARDENING
- OCR connector aliases such as `paddleocr` normalize to `paddle`; Tesseract is the fallback when Paddle cannot run.
- OCR health is lazy and does not load a Paddle model merely to report package availability.
- `/reviews/crawl` and `/reviews/stats` each have one active modular-router handler.

MAIN DIRECTORY MAP
```text
app/
  main.py                 FastAPI entrypoint and most API/UI routes
  db.py                   SQLAlchemy engine; SQLite locally / Postgres via DATABASE_URL
  db_models.py            Persistent table models
  deps.py                 JWT cookie auth, RBAC, password hashing, ownership checks
  models.py               Pydantic/domain models
  storage.py              Legacy/in-memory compatibility storage
  services/               Domain logic (see service map below)
  routes/                 Modular routers: reviews, remote diagnostics, guided diagnostics,
                          OEM router variants
  scrapers/               Example OEM source adapters (Acmeco, Zenith)

templates/
  neo_dashboard.html      Customer Care Dashboard: /ui/neo-dashboard
  oem_dashboard.html      OEM Dashboard: /ui/oem-dashboard
  console.html            Power-user console: /ui/console
  login.html              Sign-in/sign-up page
  admin_hub.html          Admin UI
  scheduler.html          Scheduler page
  public_site.html        Root public/marketing page

scripts/                  Migration, test, smoke, evaluation and training helpers
tests/                    Pytest tests
docs/                     Product, technical, deployment, KPI and handoff documentation
data/                     Local runtime DB, evaluation data, seed/config files, uploads/cache
static/                   Browser JS assets
Dockerfile                Railway/container build
run_app.py                Uvicorn boot using Railway PORT
requirements.txt          Python dependencies
```

AUTH AND ACCESS
- Browser/API authentication uses JWT in an `access_token` cookie or `Authorization: Bearer` header.
- Roles: `user`, `oem`, `tpa`, `admin`.
- Customer warranty ownership is enforced.
- Key auth routes: `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/password/change`, `/auth/session`.
- In production, set `JWT_SECRET`, `JWT_SALT`, `ADMIN_USER`, `ADMIN_PASS`, `ALLOWED_HOSTS`; set `ALLOW_INSECURE_DEFAULTS=false`.

LOCAL START COMMANDS
```powershell
.\.venv\Scripts\Activate.ps1
python scripts\sqlite_migrate.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

LOCAL URLS
- http://127.0.0.1:8000/login
- http://127.0.0.1:8000/ui/neo-dashboard
- http://127.0.0.1:8000/ui/console
- http://127.0.0.1:8000/ui/oem-dashboard
- http://127.0.0.1:8000/ui/admin-hub
- http://127.0.0.1:8000/ui/scheduler
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/health/full

CUSTOMER WARRANTY FLOW
1. Login.
2. Customer opens `/ui/neo-dashboard`.
3. Load a product/warranty with `GET /warranties/{warranty_id}`.
4. “See full summary” controls ONLY Step 2 (Details & Care).
5. Step 3 (bill/receipt) and Step 4 (Usage & Health) must remain outside that summary toggle and visible independently.
6. Receipt upload posts to `POST /artifacts/upload`.
7. Upload starts a pipeline job. Poll `GET /jobs/{job_id}`.
8. Use `GET /warranties/{id}/summary` for the current structured summary.
9. Behaviour/risk/recommendations/advisories/notifications add ongoing care context.

INVOICE/WARRANTY PIPELINE
Files:
- `app/services/invoice_pipeline.py`
- `app/services/ocr.py`
- `app/services/ingestion.py`
- `app/services/canonical.py`
- `app/services/terms_lookup.py`
- `app/services/warranty_discovery.py`
- `app/services/warranty_parser.py`
- `app/services/summary_engine.py`

Stages:
`uploaded → extracting_text → ocr_if_needed → parsed_fields → terms_lookup → summarized → done | failed`

Important facts:
- PDF text is attempted before image OCR.
- Tesseract is the environment fallback and PaddleOCR is optional. OCR connector aliases such as `paddleocr` are normalized to `paddle`; if Paddle is unavailable, image extraction safely tries Tesseract. If OCR is unavailable, pipeline must degrade cleanly rather than return 500.
- Invoice fields are parsed with regex/heuristics: brand, product, category, model, serial/IMEI, invoice number, purchase date, coverage if present.
- An invoice normally does not contain full warranty terms. SWH performs source/cache lookup, then gives a sourced/confidence-aware result or transparent default rules.
- Summary has a deterministic template fallback; LLM is optional.

WARRANTY DISCOVERY / OEM WEB LOOKUP
Files:
- `app/services/warranty_discovery.py`
- `app/services/warranty_parser.py`
- `app/services/terms_lookup.py`
- `app/services/web_search.py`
- `app/services/oem_domains.py`
- `app/services/oem_domain_verify.py`
- `app/scrapers/acmeco.py`, `app/scrapers/zenith.py`

Workflow:
1. Existing warranty record.
2. Terms cache.
3. Known/verified OEM domains.
4. Domain/reachability preflight.
5. Official-domain/model/region-ranked bounded search.
6. HTML/PDF terms parsing.
7. Cache structured result.
8. Default category rules only if reliable terms are unavailable.

Relevant env vars:
- `TERMS_SCRAPE_ENABLED`
- `TERMS_SCRAPE_MODE`
- `TERMS_OFFICIAL_ONLY`
- `TERMS_PREFLIGHT_STRICT`
- `TERMS_SEARCH_MAX_QUERIES`
- `TERMS_SEARCH_MAX_RESULTS`
- `TERMS_ALLOW_BROAD_FALLBACK`
- Search provider keys such as `BRAVE_SEARCH_KEY`.

Do not describe preflight as a security certification. It is bounded application-level source validation. Real production should use approved OEM adapters/APIs where available.

RAG / MISTRAL / LLM
Files:
- `app/services/rag.py`
- `app/services/summary_engine.py`
- `app/services/warranty_parser.py`
- `app/services/predictive.py`

RAG:
- Uses optional Mistral embeddings.
- Can index/retrieve warranty summaries, behaviour, telemetry, OEM issues, reviews and diagnostics.
- Is active only when `RAG_ENABLED=1` and `MISTRAL_API_KEY` is configured.
- Must use metadata filters for user/warranty/region scope.
- If disabled/unreachable, normal deterministic flows continue.

LLM:
- `LLM_PROVIDER=none|mistral|ollama_remote|llamacpp`.
- Template summaries are the fallback.
- Mistral can enrich low-confidence structured terms parsing and summaries.
- Never make LLM availability a hard dependency for customer upload or warranty display.

BEHAVIOUR / RISK / PREDICTIVE / RECOMMENDATIONS
Files:
- `app/services/behaviour.py`
- `app/services/behaviour_questions.py`
- `app/services/oem_question_service.py`
- `app/services/risk.py`
- `app/services/predictive.py`
- `app/services/regional_policy.py`
- `app/services/nudge.py`, `app/services/nudges.py`, `app/services/policy.py`
- `app/services/recommendation.py`, `app/services/product_recommendations.py`
- `app/services/oem_recommendation_service.py`
- `app/services/ev_battery.py`

The predictive engine combines warranty/product fields, telemetry, usage, behaviour profile, region/climate policy, OEM issue signals, reviews/search signals and optional RAG context. Preserve explainability fields: risk label/score, base score, behaviour delta and reasons.

OEM INTELLIGENCE
Dashboard: `/ui/oem-dashboard`

Main capabilities:
- product/brand/model/region filtering;
- risk stats and forecast;
- OEM issue signals;
- Question Studio;
- Recommendation Studio;
- product-interest/demand events;
- domain verification;
- communications and dispatch policies/traces.

Important OEM endpoints include:
- `/oem/questions/llm-status`
- `/oem/questions/active`, `/generate`, `/publish`, `/disable`
- `/oem/recommendations/preview`, `/generate`, `/publish`, `/active`, `/disable`
- `/oem/products`, `/oem/risk-stats`, `/oem/forecast`
- `/oem/issues`, `/oem/issues/summary`
- `/oem/communications/send`, `/oem/communications/traces`
- `/events/product-interest`

Compatibility aliases under `/api/oem/...` exist for OEM questions/recommendations. Check `app/main.py` and OpenAPI before creating duplicate paths.

DIAGNOSTICS
- IoT path: `app/routes/remote_diagnostics.py`, `app/services/remote_diagnostics.py`.
- Non-IoT path: `app/routes/guided_diagnostics.py`, `app/services/guided_diagnostics.py`.
- Routing: `app/services/diagnostics_capability.py`.

Remote diagnostics is connector-based and needs consent, command allowlist and review/approval. Guided diagnostics is the safe default for non-connected products and can collect evidence, estimate probable issue, find service centres and create service tickets.

SCHEDULER / KPI
- Scheduler: `app/services/scheduler.py`.
- KPI: `kpi_scorecard.py`, `kpi_watchdog.py`, `kpi_remediation.py`, `kpi_execution.py`.
- The scheduler is in-process: suitable for a demo/single instance, not the final durable queue architecture.

KPI EVIDENCE RULE
KPI/evaluation JSON files under `data/` are primarily synthetic/controlled 50-case runs. They prove implementation paths were exercised, not that SWH has achieved the same customer, OEM, financial or repair outcomes in live production.

Safe wording:
“SWH has implemented and test-validated MVP workflows with synthetic/controlled benchmark evidence. Live business impact and model performance require a monitored pilot.”

GOOGLE ADK / AGENTIC EXTENSION STATUS
Google ADK is NOT installed/active in this repository yet.

If asked to add it, implement it as an optional feature-flagged coordinator, never a replacement for core SWH services:
`AGENTIC_WORKFLOW_ENABLED=0` by default.

Suggested safe agent flow:
invoice/customer request → read parsed fields → confidence check → ask one missing question only if needed → approved OEM terms lookup → authorized RAG retrieval → customer-friendly sourced summary/next action.

The agent may use existing functions as tools. It must NOT:
- run on every page load/invoice;
- search unrestricted web sources;
- change records/send communications/device commands without validation and policy;
- expose customer data across tenant/user boundaries;
- run unbounded tool loops.

Use quotas, token limits, cache agent outputs, enforce timeouts and log tool calls/costs. Use rules/cache/PDF text first; AI only for difficult cases or explicit user requests.

HEALTH AND TESTING
Health routes:
- `/health/full`
- `/health/ocr`
- `/health/llm`
- `/health/predictive`
- `/health/rag`

Core docs/tests:
- `docs/GOLDEN_PATH_TEST.md`
- `scripts/test_upload.ps1`
- `scripts/sqlite_migrate.py`
- `tests/test_invoice_pipeline.py`
- `tests/test_warranty_discovery.py`
- `tests/test_warranty_parser.py`
- `tests/test_notifications.py`
- `tests/test_oem_communication.py`
- `tests/test_oem_dispatch.py`
- `tests/test_rag_health.py`
- `scripts/smoke_test_behaviour_*.py`
- `scripts/smoke_test_oem_*.py`
- `scripts/smoke_test_product_*.py`

USEFUL COMMANDS
```powershell
# Start local system
.\.venv\Scripts\Activate.ps1
python scripts\sqlite_migrate.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Tests
python -m pytest tests -q
python -m py_compile app\main.py

# Health
curl.exe http://127.0.0.1:8000/health/full
curl.exe http://127.0.0.1:8000/health/ocr
curl.exe http://127.0.0.1:8000/health/llm
curl.exe http://127.0.0.1:8000/health/predictive

# Git before/after work
git status -sb
git diff --check
git log -5 --oneline
```

DEPLOYMENT / RAILWAY
- Container files: `Dockerfile`, `run_app.py`.
- The app reads Railway `PORT` through `run_app.py`.
- Verify the Railway service watches `master` before relying on auto-deploy.
- After a push, check Railway logs and deployed `/health/full`; repository files cannot prove current Railway health.
- Before unrestricted production, move SQLite/JSONL/local uploads to managed Postgres/object storage, use durable job workers, configure secrets, backups, monitoring, rate limits and legal/privacy controls.

FINAL WORKING DISCIPLINE
1. Read the memory/docs first.
2. Confirm the active branch and dirty files.
3. Inspect related code before editing.
4. Preserve fallbacks and route compatibility.
5. Run focused tests.
6. Show `git diff --check`, `git status -sb` and tests before committing.
7. Commit only intentional files with a clear message.
```

---

## Notes for the repository owner

- This prompt does not include secrets or local `.env` values.
- The new AI should start in the repository root, not in `Downloads` or a parent directory.
- Give the agent this prompt plus `MEMORY.md`; then it can navigate the rest of the documentation without guessing.
