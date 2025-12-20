# Smart Warranty Hub (MVP)

Minimal FastAPI service that mirrors the MVP scope from the Smart Warranty Hub specification: ingest artefacts, build a canonical warranty record, log behaviour, compute a lightweight risk score, surface nudged advisories, and start a service ticket with recommended parts.

## Quick start
- Install Python 3.11+.
- `python -m venv .venv && .\\.venv\\Scripts\\activate` (PowerShell) or `source .venv/bin/activate` (bash).
- `pip install -r requirements.txt`
- `uvicorn app.main:app --reload`
- Open http://127.0.0.1:8000/docs for the interactive API.

### Optional OCR / layout models
- Default OCR hook expects `paddleocr` if you want image/PDF ingestion. Install (Windows needs correct paddlepaddle wheel): `pip install paddleocr==2.7.0.2 paddlepaddle`.
- Swap in other engines by editing `app/services/ocr.py` (DocTR, EasyOCR, TrOCR, Donut, LayoutLMv3, etc). See `docs/ocr-nlp-options.md`.

### Connectors (real endpoints)
- Connectors are stored in `data/connectors.json`. Default:
  - `ocr-default`: engine `paddleocr` (local).
  - `llm-ollama`: engine `ollama` at `http://127.0.0.1:11434` (model `llama3.2:8b`).
- APIs:
  - `GET /connectors` (optional `?kind=ocr|llm|...`)
  - `POST /connectors` with `{name, kind, endpoint, auth_token?, metadata?}`
  - `POST /connectors/reload` reloads `data/connectors.json`
- LLM generation via `POST /llm/generate` with `{"prompt": "...", "model": "llama3.2:8b"}`; routes through registered LLM connector.

### Camera / uploads
- File upload with OCR: `POST /artifacts/upload` (multipart file) -> saves under `data/uploads/` and runs OCR.
- Camera capture with OCR: `POST /artifacts/capture` -> grabs frame from default camera (OpenCV), saves under `data/captures/capture.jpg`, and runs OCR.
- Requirements: `opencv-python`, `python-multipart`, plus your OCR engine (PaddleOCR by default).

## MVP coverage
- **Ingestion:** accept invoice/manual/label/portal artefacts and parse brand/model/serial/purchase date heuristically.
- **Canonicalisation:** build a canonical warranty record with confidence per field, expiry calculation, defaults for terms/exclusions/claim steps.
- **Behaviour logging:** record consented interactions (`nudge_dismissed`, `task_completed`, `issue_reported`) per user+warranty.
- **Risk score:** rule-based score using behaviour signals and presence of expiry; returns band and contributors.
- **NIP-style advisories:** generate a bundle of nudges (snapshot, preventive care, expiry reminder) driven by risk.
- **Service orchestration:** draft service tickets with symptom-to-part mapping and evidence capture.

## Sample workflow (cURL)
```bash
# 1) Create an artefact from an invoice snippet
curl -X POST http://localhost:8000/artifacts \
  -H "Content-Type: application/json" \
  -d '{"type":"invoice","content":"Brand: AcmeCo Model: WM-900 Serial: SN123456 Purchase: 11-10-2025 24 months warranty"}'

# 1b) OR create from an image/PDF with OCR
curl -X POST http://localhost:8000/artifacts \
  -H "Content-Type: application/json" \
  -d '{"type":"invoice","file_path":"C:/path/to/invoice.jpg","use_ocr":true}'

# 2) Convert to a canonical warranty
curl -X POST http://localhost:8000/warranties/from-artifact \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"<artifact_id_from_step_1>","overrides":{"product_name":"Washer 900 Pro"}}'

# 3) Log behaviour and fetch advisories
curl -X POST http://localhost:8000/behaviour-events \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-1","warranty_id":"<warranty_id>","event_type":"nudge_dismissed"}'
curl "http://localhost:8000/advisories/<warranty_id>?user_id=user-1"
```

## Repo layout
- `app/main.py` — FastAPI entrypoint and routes.
- `app/models.py` — Pydantic models for artefacts, warranties, risk, nudges, and tickets.
- `app/storage.py` — in-memory store and ID generator.
- `app/services/` — ingestion/parsing, canonicalisation, risk scoring, advisory generation, service ticket logic, OCR hook, and connector registry (MCP stub).
- `docs/` — notes and backlog items.

## Next steps
1) Replace in-memory storage with Postgres + SQLAlchemy models and migrations.  
2) Add OCR + warranty NLP (layout-aware extraction and confidence scoring) and plug into ingestion.  
3) Implement telemetry/device adapter layer with consented scopes and audit logging.  
4) Add policy engine for NIP (time-of-day, geography, cohort-based prompts) and A/B testing.  
5) Harden privacy and security: RBAC, purpose-tagged consent, encryption at rest, and anonymised OEM sync jobs.  
6) Build front-end dashboard (coverage, feature panel, nudges, ticketing) and notification channels.
