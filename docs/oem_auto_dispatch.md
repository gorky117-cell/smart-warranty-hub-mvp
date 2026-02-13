# Weekly OEM Auto Dispatch

This feature runs OEM-to-user communication automatically on a weekly schedule for MVP.

## Schedule

- `OEM_AUTO_DISPATCH_ENABLED=true`
- `OEM_AUTO_DISPATCH_MINUTES=10080` (7 days)

The scheduler picks eligible user+warranty pairs and evaluates if updates are important enough to send.

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
- `min_issue_count`
- `min_issue_severity`
- `issue_lookback_days`
- `include_regions`
- `exclude_regions`
- `sender_user_id`, `sender_role`

## Traceability

All send attempts flow through OEM communication trace:
- sent / blocked
- reason and blocked reason
- sender, recipient, timestamp, and context
