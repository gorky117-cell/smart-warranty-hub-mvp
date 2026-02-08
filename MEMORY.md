# Smart Warranty Hub – Working Memory

Purpose: keep a running, human‑readable record of changes, decisions, and integrations so future updates don’t overwrite or duplicate work. Review this file before making new changes.

Last updated: 2026-02-06

## Key Integrations (Current State)
- OCR + ingestion + warranty parsing is integrated.
- Auto warranty term discovery and scraping is integrated (offline sources + live search).
- Brave Search API support is integrated (preferred free-tier option).
- Optional headless scraping (Playwright) is integrated and gated by env var.
- Regional policy rules + OEM issue signals are integrated into predictive risk.
- Scheduled ingestion + risk refresh is integrated via scheduler.
- Mistral LLM + RAG (pgvector) is integrated for smarter summaries.
- RAG indices now ingest product/user behaviour, telemetry, and OEM issue signals for predictive context.
- Review crawling pipeline added (India focus, daily scheduling, robots-respecting). Stores raw snapshots in object storage and ingests review sentiment into predictive signals.
- Per-upload review crawl supported for real-time enrichment.
- OEM official domain list added for safer discovery.
- OEM-specific parsing rules applied during warranty parsing (brand-specific selectors + extended parts).
- Expanded India OEM domain list for appliances/electronics/audio/EV.

## Environment / Config
- `TERMS_SCRAPE_ENABLED=1` (default)
- `TERMS_SCRAPE_MODE=auto+manual`
- `TERMS_SCRAPE_ALLOW_RETAIL=1`
- `TERMS_SEARCH_PROVIDER=brave|bing|auto`
- `BRAVE_SEARCH_KEY` (for Brave search)
- `HEADLESS_SCRAPE=1` (optional, requires Playwright)
- `OEM_ISSUE_FEED_REFRESH_MINUTES` (default 180)
- `RISK_REFRESH_MINUTES` (default 120)
- `REVIEW_CRAWL_ENABLED=true`
- `REVIEW_CRAWL_MINUTES=1440`
- `REVIEW_REGION=IN`
- `REVIEW_MAX_PAGES`, `REVIEW_MAX_PAGES_PER_DOMAIN`, `REVIEW_MAX_QUERIES_PER_PRODUCT`, `REVIEW_MAX_RESULTS_PER_QUERY`
- `REVIEW_ROBOTS_RESPECT=true`
- `REVIEW_CRAWL_DELAY_SEC`
- `REVIEW_SEARCH_PROVIDER` (brave/bing/auto)
- `REVIEW_SEARCH_PROVIDER` (brave/serpapi/google/bing/auto)
- `REVIEW_DENYLIST_DOMAINS`
- Search quota guard:
  - `SEARCH_DAILY_LIMIT` (0 = unlimited)
  - `SEARCH_MONTHLY_LIMIT` (0 = unlimited)
  - `SEARCH_QUOTA_FILE` (default `data/search_quota.json`)
  - `SERPAPI_KEY` (SerpAPI fallback)
  - `SERPAPI_ENDPOINT` (default `https://serpapi.com/search.json`)
- `REVIEW_CRAWL_ON_UPLOAD=true` (real-time per invoice)
- `REVIEW_ON_UPLOAD_MAX_PAGES=5`
- `TERMS_OFFICIAL_ONLY=true` (only allow OEM domain matches)
- `DATA_GOVERNANCE_CLEANUP_MINUTES=1440`
- `REVIEW_RETENTION_DAYS`, `REVIEW_PAGE_RETENTION_DAYS`, `TELEMETRY_RETENTION_DAYS`, `SEARCH_LOG_RETENTION_DAYS`
- `REVIEW_FETCH_RETRIES` (default 2)
- `ALERT_WEBHOOK_URL`
- `REQUIRE_USER_CONSENT=true` (enforce consent on telemetry/behaviour)
- Object storage:
  - `OBJECT_STORE_DRIVER=local|s3`
  - `OBJECT_STORE_LOCAL_DIR`
  - `OBJECT_STORE_S3_BUCKET`, `OBJECT_STORE_S3_ENDPOINT`, `OBJECT_STORE_S3_REGION`
  - `OBJECT_STORE_S3_ACCESS_KEY`, `OBJECT_STORE_S3_SECRET_KEY`
- `MISTRAL_API_KEY`
- `MISTRAL_MODEL` (default `mistral-small-latest`)
- `MISTRAL_EMBED_MODEL` (default `mistral-embed`)
- `RAG_ENABLED=1`

## Changes & Additions
- Added warranty discovery + parsing:
  - `app/services/warranty_discovery.py`
  - `app/services/warranty_parser.py`
  - `app/services/web_search.py` (Bing + Brave + auto)
  - Google Custom Search support (`GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_CX`)
- Added RAG + Mistral:
  - `app/services/rag.py`
  - `app/services/summary_engine.py` supports `LLM_PROVIDER=mistral`
  - New DB table: `DocumentEmbeddingDB`
- Extended terms lookup:
- Structured summaries stored with points/tags in `WarrantySummaryDB`.
- Review crawler:
  - `app/services/review_crawler.py`
  - `app/services/review_sources.py`
  - `app/services/sentiment.py`
  - `app/services/object_store.py`
  - New DB table: `ReviewPageDB`
  - `app/services/terms_lookup.py` (auto discovery + manual URL + regional policy)
- Added region policy + OEM issue signals:
  - `app/services/regional_policy.py`
  - `app/services/oem_issue_signals.py`
  - New DB tables: `RegionalPolicyDB`, `OemIssueSignalDB`, `RiskSnapshotDB`
- Added scheduled ingestion + risk refresh:
  - `app/services/oem_issue_feeds.py`
  - `app/services/risk_refresh.py`
  - Scheduler updated in `app/services/scheduler.py`
- Added APIs:
  - `POST /region-rules`, `GET /region-rules`
  - `POST /oem/issues`, `GET /oem/issues/summary`
  - `POST /warranty/terms/refresh`
- Demo assets + flow:
  - `test_data/mock_invoice.txt`
  - `test_data/mock_oem_warranty.html`
  - `data/warranty_sources.json` (mock mapping)
  - `scripts/demo_mock_flow.py` (saves `data/demo_output.json`)
- Test setup:
  - `tests/conftest.py` uses temp DB, initializes schema
  - `pytest.ini` disables cache provider
  - `tests/test_warranty_parser.py` added
- Fixes:
  - Brand parsing trim in `app/services/ingestion.py`
  - Summary uses refreshed warranty data in `app/services/invoice_pipeline.py`
- Requirements:
  - `paddleocr==2.8.0`
  - `paddlepaddle==2.6.2`
  - `PyMuPDF==1.23.8`
- Helper:
  - `scripts/set_brave_env.ps1`

## Operational Notes
- For live web discovery, set `BRAVE_SEARCH_KEY`.
- Without a search key, discovery uses `data/warranty_sources.json` only.
- Headless scraping is optional and off by default.
- Tests run with: `python -m pytest -q --ignore=scripts`

## Deployment Notes (Railway)
- Set `DATABASE_URL` to Railway Postgres (recommended) or SQLite path (not ideal for prod).
- Add env vars:
  - `BRAVE_SEARCH_KEY`
  - `TERMS_SEARCH_PROVIDER=brave`
  - Optional limits: `TERMS_SEARCH_MAX_QUERIES`, `TERMS_SEARCH_MAX_RESULTS`, `TERMS_SEARCH_TIMEOUT_SEC`
  - Optional: `HEADLESS_SCRAPE=1` (requires Playwright install)
- Ensure `OEM_ISSUE_FEED_REFRESH_MINUTES` and `RISK_REFRESH_MINUTES` are set if you want scheduled updates.

## Architecture Notes (High Level)
- Ingestion: `/artifacts` → OCR → parsed fields → warranty record.
- Terms: discovery (offline + search) → scrape HTML/PDF → cache terms → update warranty.
- Risk: behaviour + telemetry + regional rules + OEM issue signals → predictive score → notifications.
- Scheduler: OEM fetch queue + OEM issue feed ingest + risk refresh.

## TODOs / Next Improvements
- Add real OEM feed sources to `data/oem_issue_feeds.json`.
- Add allow/deny list for OEM domains.
- Add search retry/backoff + rate limit handling.
- Add per‑OEM parsers for higher accuracy.
- Add cron job to refresh summaries after risk changes.
