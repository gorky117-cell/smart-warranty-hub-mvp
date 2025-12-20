# MVP scope from specification

- Core promise: Smart Warranty Hub that ingests artefacts, canonicalises warranty data with confidence/alternatives, logs behaviour, computes risk, surfaces nudged guidance, and orchestrates service/tickets/parts. Works stand-alone or with optional device telemetry/actuation under consent and audit.
- Data: canonical warranty record (brand, model, serial, purchase, coverage months, expiry, terms, exclusions, claim steps, confidence per field, retained alternatives). Behaviour events and contextual signals feed risk and nudges.
- Pipelines: ingestion (OCR/NLP + OEM sync) → canonicalisation → behavioural monitor → trend/risk engine → Nudged Insight Propagation (NIP) → advisory bundle → service/ticketing with parts mapping → anonymised OEM feedback.
- Safety/privacy: purpose-tagged consent, RBAC, encryption, immutable audit, pseudonymised device IDs, anonymised aggregates for OEM analytics. Safe-listed actuation only after explicit consent.
- Drawings (FIG 1-6): show system data flow, behavioural and nudge orchestration, predictive risk/trend pipeline, operational support/parts fulfilment, product-feature visibility panel, and device cooperation.

## What the current code covers
- API to ingest artefacts and build a canonical warranty record with expiry calculation.
- Behaviour logging, basic risk scoring, and advisory bundle generation (nudges driven by risk/expiry).
- Service ticket draft creation with symptom-to-part mapping and evidence capture.
- In-memory store and ID generation; FastAPI surface with OpenAPI docs.

## Backlog to reach full spec
- OCR/NLP (layout-aware, confidence scoring) and multi-source reconciliation.
- Device adapter layer (REST/MQTT/BLE/Wi-Fi) with consent scopes, safe-listed actuation, and audit.
- Trend engine and drift-aware risk recalibration; A/B-tested NIP policy engine.
- Durable storage, role-based auth, consent registry, encryption, and anonymised OEM sync jobs.
- Front-end dashboard for coverage, feature panel, nudges, and ticket flows; notifications across channels.
