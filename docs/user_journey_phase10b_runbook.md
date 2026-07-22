# Phase 10B - User Journey Synthetic Coverage

Phase 10B adds controlled synthetic coverage for user-side MVP journeys. It complements the KPI evaluators by showing that the repo tracks realistic customer paths, not only aggregate KPI math.

## Scope

The evaluator covers:

1. New user invoice upload.
2. Partial/missing invoice fields.
3. Active, near-expiry and expired warranty states.
4. Low, medium and high predictive risk.
5. Notification/nudge expectations.
6. Draft-only warranty-resolution agent boundary.
7. Cross-user access blocking.
8. Direct OEM sharing consent blocked/allowed scenarios.
9. Mobile-first Neo/dashboard journey inclusion.

## Run

```powershell
.\.venv\Scripts\python.exe scripts\eval_user_journey_phase10b.py
```

Outputs:

- `data/user_journey_phase10b_eval_50.json`
- `test_data/user_journey_phase10b_cases_50.json`

## Safe Presentation Wording

Use this wording:

> User journey coverage is represented by a controlled synthetic 50-case evaluation covering upload, summaries, risk, care, consent, security boundaries, notifications, draft-only agent behavior and mobile-first scenarios.

Avoid saying:

> These are live funnel, retention or customer conversion results.

Those require production analytics and real user cohorts.
