# Smart Warranty Hub - working notes for Claude

Customers upload an invoice; SWH reads it (OCR + extraction), finds the brand's warranty terms, and shows
dates, cover, care tips and reminders. FastAPI + SQLAlchemy (SQLite locally, Postgres on Railway), static
HTML templates. Live at https://www.smartwarrantyhub.com; Railway deploys `origin/master`.

Read first: `STATUS.md` (what is live, measured numbers, known issues) and `MEMORY.md` (numbered log of every
run, newest at the bottom; resume from its last entry). Open work: `docs/BACKLOG.md`, tagged **[NEEDS-KEYS]**
(API keys, real invoices or production data) or **[GAURAV]** (the owner's decision or manual work); untagged
items are code work the cloud session can do.

## Priorities
1. Correct, grounded warranty facts for the invoice the customer uploaded (dates, cover, what to do).
2. Never mislead: unsure -> "please confirm" / "Estimated, please check"; never a guess.
3. Plain language for customers; technical detail admin-only.
4. Fill the knowledge base (docs/KB_WORKSHEET.md) before adding new features. Open work: docs/BACKLOG.md.

## GLOBAL RULE
Fix the general cause for any product, brand, invoice and warranty type; brand-specific code only when
unavoidable, named, documented and tested. Test on a mix (phone, laptop, TV, fridge, AC, washing machine,
geyser, small appliance, printer; 3+ brands; text PDF, scanned PDF, phone photo; marketplace and shop
invoices; warranty types incl. part periods, extended plans, installation start, no warranty). Say so when
something cannot be made general yet.

## Single-entry rule
Customers upload only the invoice. The warranty card is a later add-on (not built).

## Safety rules
- Cloud work: one branch per batch (`cloud/batch-1`, `cloud/batch-2`, ...), pushed after every commit, one pull
  request per batch. Never push to or merge master/main: the owner merges after a production backup
  (`scripts/backup_prod_db.ps1`). Never change Railway settings.
- Never read, print, log or commit secrets (`.env`, API keys, `cookies.txt`, database URLs).
- Never commit `real_invoices/` or results from real invoices.
- One commit per step; full test suite before each commit (commit only when it passes); update `MEMORY.md`
  after each step. Report measured numbers only.
- Own words: customers see SWH-written facts, never a brand's sentences, unless
  `data/brand_reuse_policy.json` grants permission (none today). Every customer line grounded in the source.
- Every read of a brand's site goes through `app/services/robots_guard.py`. The Right to Repair portal is a
  secondary, admin-entered citation only; never fetched automatically.

## Commands (Windows, Git Bash or PowerShell)
- Tests: `.venv/Scripts/python -m pytest -q -p no:cacheprovider` (~2-3 min; network is blocked in tests unless
  `SWH_LIVE_NETWORK_TESTS=1`). Gate commits on the exit code.
- Run locally: `.venv/Scripts/python run_app.py` (port from `PORT`, default 8000).
- Synthetic global check (162 documents, writes `docs/GLOBAL_CHECK.md`): `python scripts/global_check.py`.
- Real invoices (owner's files, local only): `python scripts/run_real_invoices.py`.
- Python edited through a Bash heredoc can turn `\b` into a backspace character: write code with the
  file tools, or check changed files for chr(8).

## Where things are
- `app/main.py` - all routes (customer, admin, OEM), page serving (`templates/neo_dashboard.html` is the
  customer dashboard; admin pages under `/ui/admin...`).
- `app/storage.py` - warranty load; `_row_to_warranty` applies `customer_content.tidy` (display layer:
  cleaned claim steps, terms filtered by product line, facts in own words). The database keeps raw text.
- Extraction: `services/ingestion.py` (fields, IMEI Luhn, listing codes, confusable OCR codes ->
  "please confirm"), `services/invoice_pipeline.py` (upload job), `services/ocr.py`.
- Terms: `services/terms_lookup.py` (source order), `knowledge_base.py` + `kb_quick.py` (admin entries),
  `terms_cache.py`, `warranty_parser.py`, `warranty_discovery.py`, `source_trust.py`, `brand_registry.py`,
  `brand_families.py` (shared names: product category picks the company), data in `data/*.json`.
- Customer content: `warranty_facts.py` (facts), `customer_content.py`, `warranty_card.py` (five lines and
  warranty types), `summary_engine.py`, `product_naming.py`, `product_recommendations.py` (care tips),
  `care_guides.py`, `reminders.py` + `notifications.py`, `document_store.py` (files in Postgres by default),
  `combined_export.py` (claim PDF).
- `app/schema_upgrade.py` - guarded start-up schema changes (only additions; never fatal).
