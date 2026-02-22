# Smart Warranty Hub - Product Manual

## 1. Product Overview

Smart Warranty Hub is a warranty intelligence platform that converts invoices and product signals into:

1. Clean warranty records
2. Explainable risk insights
3. User care nudges and recommendations
4. OEM action workflows
5. Service escalation workflows (IoT and non-IoT)

It supports both customer and OEM use-cases in one stack.

## 2. Primary Actors

1. End User: registers warranties, receives summaries, nudges, guided support.
2. OEM User: publishes questions/recommendations, monitors risk and issue trends, runs communications.
3. Admin: controls policies, reviews, dispatch, KPI watchdog/remediation/execution.

## 3. End-to-End User Journey

1. User uploads bill/invoice or captures via camera.
2. OCR + parsing extracts warranty fields.
3. Terms lookup enriches coverage, exclusions, and claim steps.
4. Warranty summary is generated (and exportable to PDF/TXT/HTML).
5. Risk/advisory/predictive insights are produced.
6. Behavior questions and telemetry refine ongoing insights.
7. Diagnostics flow is selected:
   - IoT: remote diagnostic request
   - Non-IoT: guided diagnostics + service-center escalation

## 4. Major Functional Areas

### 4.1 Ingestion and OCR

1. Multi-source artifact ingestion (`invoice`, `manual`, `label`, `portal`).
2. OCR fallback when direct text is weak.
3. Parsed-field persistence with confidence scoring.

### 4.2 Warranty Canonicalization

1. Canonical record normalization.
2. Expiry derivation from purchase date + coverage.
3. Structured terms/exclusions/claim steps storage.
4. Ownership isolation per user.

### 4.3 Terms Discovery and Enrichment

1. Official-domain-first preflight search.
2. Region-aware terms source selection.
3. Deterministic parser first.
4. NLP/LLM enricher only for low-confidence cases.
5. Terms cache for repeated lookups.

### 4.4 Summary and Export

1. Warranty summary endpoint.
2. Layman summary with red flags/fine print.
3. Exports to `txt`, `html`, `pdf`.

### 4.5 Behavior, Risk, and Predictive

1. Behavior question flow and profile scoring.
2. Risk scoring from behavior events.
3. Predictive scoring from telemetry + behavior + context.
4. Explainable reasons for decisions.
5. Nudge generation (care/expiry/lapse).

### 4.6 OEM Intelligence and Communication

1. OEM issue signal ingestion and summary.
2. OEM recommendations and question lifecycle.
3. OEM communication controls with governance.
4. OEM dispatch automation (policy + thresholds).

### 4.7 Diagnostics

1. Remote diagnostics module (IoT):
   - Session -> command -> review -> execute -> trace
2. Guided diagnostics module (non-IoT):
   - Q&A -> evidence -> probable issue -> nearest service center -> optional ticket
3. Capability auto-routing in Neo Dashboard.

### 4.8 RAG Layer

1. Embedding-backed retrieval context.
2. Indexed document classes: summary, behavior, telemetry, OEM issue, review, diagnostics.
3. Context used in predictive and summary flows.

### 4.9 KPI and Operations

1. KPI scorecard and reporting engine.
2. Watchdog decisioning.
3. Remediation plan generation.
4. Execution task lifecycle and overdue alerts.

## 5. Dashboard Surfaces

### 5.1 Neo Dashboard (User)

1. Warranty details + summary + advisories.
2. Predictive status and badges.
3. Behavior question and recommendation card.
4. EV card (when product is EV-like).
5. Diagnostics assistant card:
   - remote request or guided check (auto-selected).

### 5.2 OEM Dashboard

1. Risk distribution and trend views.
2. OEM issue/communications/recommendation controls.
3. Dispatch policy and run outcomes.

## 6. Data Governance and Safety

1. Consent checks for analytics-sensitive operations.
2. Review/approval gates for sensitive workflows.
3. Audit logs for critical actions.
4. Retention cleanup schedules.
5. Rate limits and policy constraints on OEM contact.

## 7. Product Boundaries

1. IoT remote diagnostics needs an OEM connector/device API.
2. Non-IoT devices use guided diagnostics and service-center workflows.
3. Capability inference is metadata/heuristic-driven and can be strengthened with OEM registry integration.

## 8. Related Documents

1. Exhaustive feature list: `docs/feature_catalog_exhaustive.md`
2. KPI details: `docs/kpi_master_scorecard.md`
3. OEM technical manual: `docs/oem_dashboard_and_integration_manual.md`
4. Deployment/config manual: `docs/deployment_config_reference.md`
