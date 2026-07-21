# Smart Warranty Hub Hackathon Demo Guide

Downloadable Word version: `docs/Smart_Warranty_Hub_Hackathon_Demo_Guide.docx`

## One-line pitch

Smart Warranty Hub turns a customer's invoice into clear warranty guidance, proactive care and risk support, while giving OEM and TPA teams privacy-safe signals to act earlier.

## Two-minute judge flow

1. Start on the public site and say: "This is a post-purchase warranty platform for customers, OEMs and TPAs."
2. Sign in and open the Neo dashboard.
3. Upload a sample invoice or choose an available warranty.
4. Show the warranty summary: product details, coverage, exclusions, claim steps, confidence and evidence/source context.
5. Show predictive risk, behaviour questions and preventative care/expiry guidance.
6. Open the Resolution checklist and explain that it is draft-only: it can recommend safe next steps but cannot submit a claim, contact an OEM or run a device action.
7. Switch to the OEM dashboard. Show aggregate insight, source verification and controlled question/recommendation workflows.
8. Close with the privacy boundary: direct OEM sharing needs explicit consent, and aggregate telemetry is cohort-suppressed.

## What makes the demo credible

- Invoice upload is size/type restricted and stored with server-generated filenames.
- Warranty access is protected by authenticated ownership checks.
- The OpenAI lane is optional and falls back safely when unavailable.
- Telemetry strips direct identifiers before use and OEM aggregates require a minimum cohort.
- High-risk/cost paths have CSRF protection, rate limits, request IDs and per-user AI quotas.
- The warranty-resolution agent remains draft-only and records an audit trace.
- The full automated suite currently passes: 122 tests.

## What to say about metrics

Use this wording: "The repository includes controlled 50-case evaluations for the OCR, predictive, nudge, service, OEM dispatch, watchdog and remediation workflows. These are test metrics, not live customer results."

Do not claim real reductions in warranty cost, claim turnaround time, failure prevention or OEM outcomes unless independently measured with live data.

## Judge questions: short answers

**Is this production-ready?**

"It is ready for a controlled hackathon demo and pilot. A full production rollout would move local/process-level stores to managed Postgres, object storage and shared rate-limit/quota infrastructure."

**What does AI decide?**

"AI enriches and explains information, but deterministic warranty data, policy checks, consent, ownership and human review boundaries remain authoritative. The agent cannot execute claims or device actions."

**How is customer data protected?**

"Users are isolated by ownership checks. Telemetry is sanitized, aggregate OEM insight has cohort suppression, and direct OEM communication requires separate explicit consent."

**What is the business value?**

"Customers get clearer coverage and earlier care guidance; OEM and TPA teams get privacy-safe early signals for support, service and product-quality workflows."

## Presentation checklist

- Use the active `master` branch for any code walkthrough.
- Before judges access GitHub, make `master` the default branch so they see the current project.
- Keep one sample invoice and one known login ready.
- Demonstrate the happy path; do not rely on an external OCR/LLM call during the presentation.
- If an optional provider is unavailable, explain that deterministic fallbacks preserve the core flow.
