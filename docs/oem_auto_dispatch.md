# OEM Analysis + Monthly Dispatch

This feature separates analysis from sending:
- weekly analysis (internal signal evaluation)
- monthly dispatch (user communication only if signals are strong enough)

## Schedule

- `OEM_ANALYSIS_ENABLED=true`
- `OEM_ANALYSIS_MINUTES=10080` (7 days)
- `OEM_AUTO_DISPATCH_ENABLED=true`
- `OEM_AUTO_DISPATCH_MINUTES=43200` (30 days)

The scheduler evaluates user+warranty signals weekly, and sends only in monthly windows.

## Inputs Used

- OEM issue signals
- Warranty context (brand/model/region)
- User behaviour profile
- Symptom search patterns
- Existing outreach guardrails (6-month throttle, no marketing)

## Control Plane (Admin)

- `GET /admin/oem-dispatch/policy`
- `POST /admin/oem-dispatch/policy`
- `POST /admin/oem-dispatch/run` (manual trigger, supports dry-run)

## Policy Fields

- `enabled`
- `plan_tier` (`free` / `pro`)
- `allowed_kinds` (`important_update`, `product_recommendation`)
- `send_product_recommendations`
- `max_targets_per_run`
- `min_eligible_for_send`
- `min_issue_count`
- `min_issue_severity`
- `issue_lookback_days`
- `include_regions`
- `exclude_regions`
- `notify_oem_when_no_signal`
- `notify_oem_summary`
- `sender_user_id`, `sender_role`

## Traceability

All send attempts flow through OEM communication trace:
- sent / blocked
- reason and blocked reason
- sender, recipient, timestamp, and context

If monthly signals are below threshold, user messages are skipped and OEM gets:
- "Monthly analysis not yet conclusive."
