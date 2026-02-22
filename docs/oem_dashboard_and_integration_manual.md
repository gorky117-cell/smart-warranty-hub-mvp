# Smart Warranty Hub - OEM Dashboard and Integration Manual

## 1. Purpose

This document explains:

1. OEM dashboard operational capabilities
2. Integration requirements
3. IoT remote diagnostics integration
4. Non-IoT guided diagnostics escalation model
5. API and policy controls

## 2. OEM Dashboard Capabilities

### 2.1 Risk and Trend Visibility

1. Risk distribution snapshots (`LOW/MEDIUM/HIGH/UNKNOWN`)
2. Behavior aggregate scores
3. OEM issue trend summaries
4. Forecast and actionable recommendations

### 2.2 OEM Content Operations

1. Publish/disable OEM questions
2. Publish/disable OEM recommendations
3. Preview recommendation outcomes before publish

### 2.3 OEM Communications

1. Send controlled communication to users
2. Enforce allowed communication kinds
3. Enforce rate limits and eligibility criteria
4. Store communication trace for audit

### 2.4 OEM Dispatch

1. Dispatch policy config (admin)
2. Dry-run dispatch
3. Live dispatch
4. Region and issue-based target filtering

## 3. Integration Modes

### 3.1 IoT/IIoT Mode

Use remote diagnostics module:

1. create diagnostic session
2. create command request
3. review/approve
4. execute via OEM connector API
5. store response and telemetry

### 3.2 Non-IoT Mode

Use guided diagnostics module:

1. guided symptom flow
2. evidence collection
3. probable issue and confidence
4. nearest authorized service center recommendation
5. optional service ticket creation

## 4. Connector Requirements (IoT)

### 4.1 Connector Registration

Register in connection registry:

1. `kind`: `remote_diagnostics`
2. `endpoint`: OEM base API URL
3. `auth_token`: optional bearer token
4. `metadata.execute_path`: execution path
5. `metadata.timeout_sec`: per-call timeout

### 4.2 Command Request Contract

Outgoing payload includes:

1. `command_id`, `session_id`
2. `warranty_id`, `user_id`, `device_id`
3. `command_type`, `command_payload`, `context`

### 4.3 Expected Connector Response

Success:

```json
{
  "ok": true,
  "result": {
    "health": "good"
  }
}
```

Failure:

```json
{
  "ok": false,
  "error": "device_offline"
}
```

## 5. Remote Diagnostics API Reference

1. `GET /remote-diagnostics/health`
2. `POST /remote-diagnostics/sessions/start`
3. `GET /remote-diagnostics/sessions`
4. `GET /remote-diagnostics/sessions/{session_id}`
5. `POST /remote-diagnostics/commands/request`
6. `GET /remote-diagnostics/commands`
7. `GET /remote-diagnostics/commands/{command_id}`
8. `POST /remote-diagnostics/commands/{command_id}/approve`
9. `POST /remote-diagnostics/commands/{command_id}/reject`
10. `POST /remote-diagnostics/commands/{command_id}/execute`
11. `POST /remote-diagnostics/run-pending`

## 6. Guided Diagnostics API Reference

1. `POST /guided-diagnostics/start`
2. `GET /guided-diagnostics/{session_id}`
3. `GET /guided-diagnostics/{session_id}/next`
4. `POST /guided-diagnostics/{session_id}/answer`
5. `POST /guided-diagnostics/{session_id}/evidence`
6. `POST /guided-diagnostics/{session_id}/finalize`

## 7. Capability Routing APIs

1. `GET /diagnostics/capability/{warranty_id}`
2. `POST /diagnostics/request-remote-check`

These APIs drive automatic IoT/non-IoT flow routing in the user dashboard.

## 8. OEM Policy Controls

### 8.1 Communication Controls

1. Allowed communication kinds
2. Importance gating
3. Contact frequency window
4. Consent enforcement

### 8.2 Dispatch Controls

1. include/exclude regions
2. min issue count/severity
3. max targets per run
4. min eligible threshold before send

### 8.3 Remote Diagnostics Controls

1. allowed command list
2. queue poll interval
3. batch size
4. auto-execute enabled/disabled

## 9. Safety and Audit

1. RBAC on OEM/admin actions
2. Review gates for risky device actions
3. Full execution trace logging
4. Communication trace logging
5. Scheduler audit entries for automated operations

## 10. OEM Onboarding Checklist

1. Share official domains and supported product regions
2. Register connector (if IoT)
3. Confirm command allowlist and review policy
4. Provide authorized service-center list (for non-IoT escalation)
5. Verify staging smoke test
6. Enable production rollout by cohort

## 11. Common Failure Codes and Action

1. `no_remote_diagnostics_connector`: configure connector or fallback to guided flow
2. `review_required`: approve command before execute
3. `unsupported_command_type`: update allowlist or request valid command
4. `request_failed` or `http_4xx/5xx`: check OEM endpoint health/auth/contract

## 12. Operational Recommendations

1. Keep review gate enabled in production.
2. Start with non-invasive commands first.
3. Track failed execution rates and retry patterns.
4. Use dry-run dispatch before policy changes.
5. Review weekly KPI + trace health before scaling target cohorts.
