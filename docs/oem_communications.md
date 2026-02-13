# OEM Communication Guardrails

This module adds controlled OEM-to-user communication with full audit trace.

## Goals

- Keep communication subtle and trust-safe.
- No frequent outreach: max one message in six months by default.
- Send only important updates.
- Product recommendations only when user behavior/risk signals justify it.
- Keep a complete trace: who sent what, when, why, and to whom.

## Endpoints

- `POST /oem/communications/send` (OEM/admin only)
- `GET /oem/communications/traces` (OEM/admin only)

## Data Trace

Each attempt is recorded in `oem_communication_traces` with:
- sender, recipient, warranty/context
- message title/body
- reason code + reason text
- decision (`sent` or `blocked`)
- blocked reason (if any)
- timestamp + structured trace JSON

## Default Guardrails

- `OEM_CONTACT_MIN_DAYS=180`
- `OEM_CONTACT_MAX_PER_WINDOW=1`
- `OEM_CONTACT_REQUIRE_IMPORTANCE=true`
- `OEM_CONTACT_ALLOW_MARKETING=false`
- `OEM_IMPORTANCE_ISSUE_LOOKBACK_DAYS=90`
- `OEM_IMPORTANCE_SYMPTOM_LOOKBACK_DAYS=30`
- `OEM_IMPORTANCE_EXPIRY_DAYS=45`

## Importance / Match Signals

For `important_update`:
- predictive risk medium/high
- warranty expiring soon
- recent OEM issue signals

For `product_recommendation`:
- low care/responsiveness behavior scores
- repeated symptom searches
- risk/issue urgency signals

If no qualifying signals are found, send is blocked by default.
