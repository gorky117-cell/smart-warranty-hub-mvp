# Smart Warranty Hub - Exhaustive Feature Catalog

## 1. Authentication, Roles, and Access

1. JWT/cookie session authentication.
2. RBAC (`user`, `oem`, `admin`).
3. Per-warranty ownership checks.
4. User consent field and enforcement in analytics flows.

## 2. Artifact Ingestion

1. Upload endpoint for invoice/manual/label/portal artifacts.
2. Camera capture ingestion path.
3. OCR-enabled processing with metadata on OCR method.
4. Invoice relevance guardrail:
   - clear
   - caution
   - needs_review + force override

## 3. OCR and Field Extraction

1. Product field extraction from text:
   - brand, model_code, product_name, product_category
   - serial_no, invoice_no, purchase_date, coverage_months
2. Confidence capture and parsed raw text persistence.
3. Parsed-field history table.

## 4. Canonical Warranty Layer

1. Warranty canonical object creation and update.
2. Coverage/expiry computations.
3. Terms, exclusions, claim_steps persistence.
4. Alternatives metadata block for source transparency.

## 5. Terms Discovery and Lookup

1. Internal DB and cache short-circuit lookups.
2. Preflight domain checks and official-domain bias.
3. Search query shaping and bounded search controls.
4. Parse from URL/HTML/text with scraper + parser combo.
5. Fallback default rules by category.

## 6. Terms NLP Enrichment

1. Deterministic parser as primary.
2. Low-confidence trigger for Mistral JSON enrichment.
3. Merge strategy preserving deterministic duration.
4. Confidence-aware section completeness.

## 7. Summary System

1. Warranty summary generation (provider-based or template fallback).
2. Structured summary points/tags.
3. Layman summary with:
   - overview
   - pros/cons
   - fine print
   - red flags
4. Source metadata fields shown in UI.

## 8. Warranty Status

1. Active/expiring/expired/unknown calculation.
2. Days left and lapsed duration text.
3. Claim eligibility message generation.

## 9. Risk and Nudge Engine

1. Risk model from behavior events and expiry awareness.
2. Nudge generation with A/B copy variants.
3. Care, snapshot, expiry, and lapsed nudges.
4. Nudge event logging.

## 10. Behavior Intelligence

1. Next-question retrieval endpoint.
2. OEM scoped question support and standard question bank.
3. Answer recording.
4. Behavior profile score updates:
   - behaviour_score
   - care_score
   - responsiveness_score

## 11. Predictive Engine

1. Feature vector build from telemetry + profile + context.
2. Model prediction with fallback heuristic.
3. Behavior delta post-adjustment.
4. Region policy and OEM issue signal risk deltas.
5. RAG context adjustment pass.
6. Explainability reasons and calibrated outputs.

## 12. Telemetry and EV

1. Generic telemetry event ingestion and storage.
2. EV telemetry storage.
3. EV battery scoring endpoint and recommendations.

## 13. Recommendation Engine

1. Rule-based recommendation matching.
2. Product recommendations by risk/region.
3. Recommendation event tracking.
4. OEM recommendation CRUD-style operations.

## 14. OEM Intelligence

1. OEM domain verification and suggestions.
2. OEM issue signal ingestion and summary.
3. OEM communication send with governance.
4. OEM communication trace retrieval.
5. OEM dispatch policy and execution.

## 15. Review and Moderation

1. Review item creation and persistence.
2. Approve/reject flow.
3. Review crawler trigger and stats.

## 16. RAG Layer

1. Embedding upsert and metadata-filtered similarity retrieval.
2. Context builders (single/multi doc type).
3. Health and smoke-check helpers.
4. Indexed doc classes:
   - `warranty_summary`
   - `behaviour`
   - `telemetry`
   - `oem_issue`
   - `review`
   - `diagnostic`

## 17. KPI System

1. KPI scorecard (phase 8).
2. KPI watchdog (phase 9).
3. KPI remediation planning (phase 10).
4. KPI task execution lifecycle (phase 12).
5. History, report, plan, board artifact files.

## 18. Scheduler and Automation

1. OEM fetch queue polling.
2. OEM issue feed ingestion.
3. Risk refresh snapshots.
4. Review crawling.
5. Retention cleanup.
6. Expiry reminder refresh.
7. OEM analysis/dispatch cycles.
8. KPI watchdog/remediation/execution cycles.
9. Remote diagnostics queued command cycle.

## 19. Remote Diagnostics Module (IoT/IIoT)

1. Session model and APIs.
2. Command request with review-gate support.
3. Approve/reject command flow.
4. Connector execution with timeout/auth support.
5. Execution trace and result persistence.
6. Telemetry/RAG writeback for executed diagnostics.

## 20. Guided Diagnostics Module (Non-IoT)

1. Guided diagnostic session APIs.
2. Product-sensitive question flow.
3. Answer capture.
4. Evidence capture (photo/video/log/text refs).
5. Probable issue + confidence + priority.
6. Nearest service-center recommendation.
7. Optional service ticket creation.

## 21. Capability Auto-Routing

1. Inference helper for IoT vs non-IoT path.
2. User-safe remote-check request endpoint.
3. Neo dashboard diagnostics card:
   - Request remote check
   - Start guided check

## 22. Export and Reporting

1. Warranty summary export (`txt`, `html`, `pdf`).
2. KPI reports in JSON artifacts.
3. Operational status and health endpoints.
