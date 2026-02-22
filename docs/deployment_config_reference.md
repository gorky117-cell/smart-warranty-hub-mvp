# Smart Warranty Hub - Deployment and Configuration Reference

## 1. Deployment Topology

Primary deployment target in current setup:

1. GitHub `master` branch
2. Railway auto-deploy on push
3. FastAPI app startup triggers:
   - `init_db()`
   - scheduler startup

## 2. Post-Deploy Critical Checks

After every deployment:

1. Confirm app health endpoint.
2. Confirm DB tables are created (new modules rely on startup `init_db()`).
3. Confirm scheduler status.
4. Confirm auth/session operational.
5. Confirm PDF export still working.

## 3. High-Impact Environment Variables

### 3.1 Security/Auth

1. `JWT_SECRET`
2. `JWT_SALT`
3. `JWT_EXPIRE_HOURS`
4. `ADMIN_USER`
5. `ADMIN_PASS`
6. `ALLOW_INSECURE_DEFAULTS` (disable in production)

### 3.2 LLM/OCR

1. `LLM_PROVIDER`
2. `MISTRAL_API_KEY`
3. `MISTRAL_API_URL`
4. `MISTRAL_MODEL`
5. `OLLAMA_URL`
6. `OLLAMA_MODEL`
7. `LLM_MODEL_PATH`

### 3.3 Terms and Search

1. `TERMS_SCRAPE_ENABLED`
2. `TERMS_SCRAPE_MODE`
3. `TERMS_PREFLIGHT_STRICT`
4. `TERMS_SEARCH_MAX_QUERIES`
5. `TERMS_SEARCH_MAX_RESULTS`
6. `TERMS_ALLOW_BROAD_FALLBACK`

### 3.4 Scheduler

1. `SCHEDULER_ENABLED`
2. `OEM_REFRESH_MINUTES`
3. `OEM_ISSUE_FEED_REFRESH_MINUTES`
4. `RISK_REFRESH_MINUTES`
5. `REVIEW_CRAWL_ENABLED`
6. `REVIEW_CRAWL_MINUTES`
7. `EXPIRY_REMINDER_ENABLED`
8. `EXPIRY_REMINDER_MINUTES`

### 3.5 OEM Dispatch

1. `OEM_ANALYSIS_ENABLED`
2. `OEM_ANALYSIS_MINUTES`
3. `OEM_AUTO_DISPATCH_ENABLED`
4. `OEM_AUTO_DISPATCH_MINUTES`
5. `OEM_DISPATCH_POLICY_FILE`

### 3.6 RAG

1. `RAG_ENABLED`
2. `MISTRAL_EMBED_MODEL`
3. `PGVECTOR_DDL_ENABLED`

### 3.7 Remote Diagnostics (IoT)

1. `REMOTE_DIAGNOSTICS_ALLOWED_COMMANDS`
2. `REMOTE_DIAGNOSTICS_CONNECTOR`
3. `REMOTE_DIAGNOSTICS_TIMEOUT_SEC`
4. `REMOTE_DIAGNOSTICS_AUTO_EXECUTE`
5. `REMOTE_DIAGNOSTICS_POLL_MINUTES`
6. `REMOTE_DIAGNOSTICS_BATCH_SIZE`

## 4. Data and File Artifacts

Important runtime files:

1. `data/connectors.json` (connector registry)
2. `data/oem_dispatch_policy*.json` (policy variants)
3. `data/service_centers.json` (guided diagnostics lookup)
4. KPI artifacts:
   - `data/kpi_phase*_eval_50.json`
   - `data/kpi_phase*_report.json`
   - `data/kpi_phase*_plan.json`
   - `data/kpi_phase*_board.json`

## 5. Railway Runtime Checklist

1. Ensure env vars set in Railway service.
2. Validate database URL (`DATABASE_URL`) connectivity.
3. Confirm logs show scheduler started.
4. Confirm no startup warnings for missing critical secrets.
5. Run smoke API calls for:
   - `/health/full`
   - `/health/predictive`
   - `/health/rag` (if present/enabled)

## 6. Git and Release Workflow

1. Commit local changes.
2. Push to `origin master`.
3. Railway auto-deploy triggers.
4. Verify deployment health.
5. Run post-deploy smoke checks.

## 7. Rollback Strategy

1. Identify last known good commit.
2. Re-deploy by resetting release target commit in CI/Git.
3. Verify schema compatibility before rollback.
4. Re-run smoke checks.

## 8. Operational Alerts Recommended

1. App startup failures
2. Scheduler exception spikes
3. OEM dispatch failure spikes
4. Remote diagnostics failure rate threshold breach
5. Search/terms lookup timeout spikes
6. KPI watchdog alert streak growth

## 9. Backup/Retention Considerations

1. Retain KPI artifacts by date/version.
2. Archive connector/policy files.
3. Keep DB backups before major feature rollouts.
4. Keep log retention sufficient for RCA on OEM-facing issues.

## 10. Production Hardening Notes

1. Turn off insecure defaults in production.
2. Use strong secrets for JWT/admin credentials.
3. Restrict connector tokens and rotate regularly.
4. Keep review gating enabled for remote diagnostics commands.
5. Add synthetic uptime checks for OEM connector endpoint.
