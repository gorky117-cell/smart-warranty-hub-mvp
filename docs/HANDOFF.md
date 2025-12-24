# Smart Warranty Hub (SWH) — Handoff Report

## 1) Repo layout (key files)

- app/main.py — FastAPI app entrypoint, routes, UI mounting, health checks
- app/db.py — SQLAlchemy engine/session (SQLite data/app.db)
- app/db_models.py — SQLAlchemy models (users, warranties, behaviour, notifications, jobs)
- app/services/* — business logic (predictive, OCR, pipeline, notifications, OEM, etc.)
- app/routes/* — OEM Questions + OEM Recommendations routers
- app/scrapers/* — OEM terms scrapers (lightweight)
- templates/* — UI templates (neo_dashboard.html, oem_dashboard.html, console.html, login.html)
- scripts/* — smoke tests + sqlite migration helper
- docs/GOLDEN_PATH_TEST.md — golden path manual test checklist

## 2) Core wiring (endpoints → services → storage)

### Auth + UI
- UI: /ui/neo-dashboard → templates/neo_dashboard.html
- UI: /ui/oem-dashboard → templates/oem_dashboard.html
- UI: /ui/console → templates/console.html
- Login: /auth/login (cookie-based)

### Warranty load + summary
- GET /warranties/{warranty_id} → app/main.py → WarrantyDB
- POST /warranties/summary (existing)
- GET /warranties/{warranty_id}/summary → invoice pipeline summary

### Predictive risk
- POST /predictive/score → app/services/predictive.py
- Inputs: warranty + usage + behaviour
- Outputs: risk_label, risk_score, base_risk_score, behaviour_delta, reasons

### EV battery
- POST /ev/battery/score → app/services/ev_battery.py

### Behaviour Q&A
- GET /behaviour/next-question
- POST /behaviour/answer
- Service: app/services/behaviour_questions.py
- Storage: data/behaviour_answers.jsonl (ignored in git)

### Notifications (user)
- GET /notifications
- POST /notifications/{id}/read
- Service: app/services/notifications.py
- DB: NotificationDB

### Advisories/nudges
- GET /advisories/{warranty_id}
- Services: app/services/nudge.py + app/services/policy.py

### Telemetry
- POST /telemetry → TelemetryEvent / EVTelemetry

## 3) Invoice pipeline (end-to-end)

### Endpoints
- POST /artifacts/upload → returns job_id
- POST /artifacts/capture → returns job_id
- POST /warranties/{id}/process → manual trigger
- GET /jobs/{job_id} → pipeline status
- GET /warranties/{id}/summary → latest summary

### Pipeline stages
uploaded → extracting_text → ocr_if_needed → parsed_fields → terms_lookup → summarized → done

### Services
- app/services/invoice_pipeline.py — pipeline orchestration
- app/services/ocr.py — PDF text extraction + optional OCR
- app/services/ingestion.py — regex extraction (brand, model, dates, invoice_no, etc.)
- app/services/terms_lookup.py — scraper + cache + fallback rules
- app/services/summary_engine.py — LLM optional, template fallback

### DB additions
- PipelineJobDB
- ParsedFieldDB
- WarrantyTermsCacheDB
- WarrantySummaryDB

### Migration helper
- scripts/sqlite_migrate.py (idempotent):
  - adds climate_zone column
  - creates pipeline tables if missing

## 4) OEM Question Studio

### Routes (both /oem and /api/oem aliases)
- /oem/questions/llm-status
- /oem/questions/active
- /oem/questions/generate
- /oem/questions/publish
- /oem/questions/disable

### Router
- app/routes/oem_questions.py

### Service
- app/services/oem_question_service.py
- JSONL: data/oem_questions.jsonl
- JSONL answers: data/oem_question_answers.jsonl

### UI
- templates/oem_dashboard.html

## 5) OEM Recommendation Studio

### Routes (both /oem and /api/oem aliases)
- /oem/recommendations/preview
- /oem/recommendations/generate
- /oem/recommendations/publish
- /oem/recommendations/active
- /oem/recommendations/disable

### Router
- app/routes/oem_recommendations.py

### Service
- app/services/oem_recommendation_service.py
- JSONL: data/oem_recommendations.jsonl

## 6) Health checks

- /health/ocr → app/services/ocr.py
- /health/llm → app/services/summary_engine.py
- /health/predictive
- /health/full → structured + degraded if OCR/LLM missing

## 7) Neo dashboard UI wiring

File: templates/neo_dashboard.html
- loadAll() calls:
  - /warranties/{id}
  - /predictive/score
  - /recommendations
  - /advisories/{id}
  - /notifications
  - /behaviour/next-question
- Step 3 receipt flow:
  - single “Add receipt” button
  - dropdown for upload / camera / manual
  - upload → /artifacts/upload
  - camera capture → /artifacts/upload
- Notifications: bell + toast
- Warranty details: formatted view, raw JSON only in debug mode

## 8) Smoke tests

Scripts in scripts/:
- smoke_test_notifications.py
- smoke_test_behaviour_next_question.py
- smoke_test_behaviour_flow.py
- smoke_test_behaviour_risk.py
- smoke_test_oem_questions.py
- smoke_test_oem_recommendations.py
- smoke_test_oem_to_customer_flow.py
- smoke_test_product_recommendations.py
- sqlite_migrate.py

## 9) Environment variables

- OCR_ENGINE = tesseract (default) or paddle
- OCR_MIN_TEXT_CHARS (default 200)
- OCR_ENGINE_TTL_SEC
- LLM_PROVIDER = none | llamacpp | ollama_remote
- OLLAMA_URL / OLLAMA_MODEL (if ollama)
- ENABLE_LLM_QUESTIONS (OEM question generation)

## 10) Quick run / verify

PowerShell:

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
python scripts/sqlite_migrate.py

curl http://127.0.0.1:8000/health/full
curl http://127.0.0.1:8000/health/ocr
curl http://127.0.0.1:8000/health/llm

## 11) Known notes

- OEM routers exist in app/routes/* and are also duplicated in app/main.py (safe, but can be cleaned later).
- JSONL caches under data/*.jsonl are ignored by git.
- OCR may be degraded if tesseract/paddle not installed; pipeline still works with PDF text extraction.

---

If you need this report in another format, ask for HANDOFF.html or HANDOFF.pdf.
