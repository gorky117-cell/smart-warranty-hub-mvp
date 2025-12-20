# Model/control plane, SLM, and human wrapper plan

Goal: a light “MCP” layer that holds all external connections (OCR, NLP/LLM, telemetry, storage), supports a small-language-model (SLM) edge path, and keeps human-in-the-loop override/wrap for sensitive flows.

## Components
- Connection registry (stub in `app/services/connection_registry.py`): tracks connectors with name/kind/endpoint/token/metadata. Replace with DB-backed registry + secrets vault in prod.
- SLM path: run a local small model (e.g., Llama 3.2 3B/8B, Phi-3.5 mini, or Mistral 7B) for low-latency summarization/extraction; use cloud LLMs only as fallback.
- Human wrapper: an approval/triage queue for high-risk actions (actuation commands, PII handling, claims submission). Gate by policy + consent, send to a human review UI.
- Policy router: chooses engine (SLM vs LLM vs rules) based on cost/latency/sensitivity.
- Audit/logging: immutable log of connector calls, with purpose tags and redacted payloads.

## Wiring suggestion
1) Extend `ConnectionRegistry` to persist connectors (Postgres table: connectors(name, kind, endpoint, token_ref, metadata JSONB)).
2) Add a “policy router” service that:
   - Prefers SLM for on-device/edge summarization.
   - Routes to OCR engine (PaddleOCR/DocTR) for images, then to extractor (LayoutLM/Donut or regex heuristics).
   - Uses cloud LLM only when policy allows and consent is present.
3) Add a human-review queue service (table: review_queue with payload, risk tag, status) and endpoints to approve/deny.
4) Provide secrets via env/KeyVault/SM; never store raw tokens in registry.
5) Add middleware to tag requests with purpose, user, and consent scope; log connector calls with hashed IDs.

## SLM options
- **Llama 3.2 3B/8B** (local GGUF via llama.cpp, or Ollama): good general text tasks, fast on CPU/GPU.
- **Phi-3.5-mini** (ONNX or direct PyTorch): strong reasoning for size, light footprint.
- **Mistral 7B** (GGUF): balanced quality/latency.
Use these for: short-form extraction, risk explanations, summarizing OCR output. Keep prompts short and constrain output JSON.

## OCR/NLP options (recap)
- OCR: PaddleOCR (default hook), DocTR, EasyOCR.
- Layout-aware extraction: LayoutLMv3/LayoutXLM, Donut (end-to-end), TrOCR (image-to-text) plus regex/rules.

## How to use the registry now (stub)
```python
from app.services.connection_registry import Connector, registry

registry.register(Connector(name="ocr-default", kind="ocr", endpoint="paddleocr://local"))
registry.register(Connector(name="slm-local", kind="llm", endpoint="ollama://llama3.2:8b"))

ocr_conn = registry.get("ocr-default")
llm_conn = registry.get("slm-local")
```

## Next build steps
- Persist the registry + review queue in DB; add CRUD endpoints under `/connectors` and `/reviews`.
- Add a policy router service that selects SLM/LLM/heuristic based on policy + consent.
- Integrate an SLM runner (e.g., Ollama client or llama-cpp-python) with a constrained JSON output mode for extraction.
- Add middleware for audit, consent tagging, and purpose-based routing.
