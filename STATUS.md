# Smart Warranty Hub - status (2026-10-05)

Measured numbers only. **Synthetic** marks results from generated test files, not real customer
invoices. No real-invoice accuracy has been measured yet (see "Next steps").

## Live vs local

- **Live** (https://www.smartwarrantyhub.com, Railway deploys `origin/master`): everything, up to commit
  `03f6a0ab` (deployed 2026-10-05 01:10).
  - Fix run 91: redaction before AI calls, Paddle back-off with Tesseract fallback, one risk scorer,
    domain verification, vision tier (off by default), expiry recalculation guard, admin security banner.
  - Follow-up run 92: "From the official <Brand> website" label, Orient Electric fix, manually confirmed
    sites, extraction suggestions, unreadable-invoice message, hermetic tests.
  - Run 93:
    - Paddle warm-up;
    - shared brand names resolved by product;
    - marketplace invoices;
    - unknown brands get "please check";
    - India pages preferred;
    - sign-in stale-cookie fix;
    - real-invoice runner.
  - Run 94:
    - sign-up rate limit;
    - philips.co.in and "/" model codes;
    - MISTRAL_EMBED_MODE;
    - OpenAI <-> Mistral fallback and mid-line buyer redaction;
    - runner review mode, `--provider`, corrections log (off).
  - Run 95-96:
    - terms-cache fixes (product scope, no estimates as "confirmed", newest official entry, metadata,
      official-only caching, 30-day expiry with "checked on", admin counts);
    - knowledge base v1 (empty);
    - guarded start-up schema upgrade;
    - backup script.
- **Local only:** nothing except this status update.
- **Production backup before this deploy:** `swh_prod_2026-10-05_0106.dump`, 1.23 MB, 36 tables, verified
  with `pg_restore --list`, kept on the owner's machine.

Live checks on 2026-10-05 01:10 after the deploy:

| Check | Result |
|---|---|
| `/api/health` | 200 `{"status":"ok"}` |
| `/health/ocr` | 200 ok, Paddle active; warm-up 66.7 s; first call after deploy took 47.8 s |
| `/login` | 200 |
| http to https | one 301 redirect, no loop |
| `/admin/terms-cache/stats` and `/admin/knowledge-base` without login | 401 (routes live, admin-only) |
| `/admin/terms-cache/stats` as admin | owner to run: `schema` should show `cache_ready: true`, `knowledge_base_ready: true`, `error: null` |
| Deploy log: "SCHEMA UPGRADE FAILED"? | not checked by me (no Railway log access); owner to check the latest deploy's logs, or the stats `schema` block |
| Re-check 2026-10-05 01:16 | `/api/health` 200, `/health/ocr` 200 (cached, 0.49 s), `/login` 200, http to https one redirect |

A real sign-in was not tested by me; no production credentials were used.

## What works

- **Upload pipeline.** Accepts PDF (text layer, or OCR for scans), photos, `.docx` and `.txt`. Paddle OCR
  runs in production with Tesseract as fallback.
- **Field extraction.**
  - Low-confidence values, misread labels and unknown brands become **suggestions the customer
    confirms**; they are never stored as fact.
  - Printed model codes beat marketing names; "/" variants such as "HL7756/00" are kept. *Local only.*
  - Marketplace rows (Amazon, Flipkart, Croma, Reliance Digital) are trimmed to the product title, and
    the seller is never taken as the brand.
- **Unreadable invoices.** These show "We couldn't read this invoice - retake the photo or enter the
  details", with a details form. No estimated coverage is shown.
- **Warranty terms.**
  - Taken from registry or verified OEM sites ("From the official <Brand> website" / "(manually confirmed)").
  - *Local only:* the terms cache is keyed by product line and model, so a Samsung TV page never answers a
    Samsung phone.
  - *Local only:* only pages on verified official domains are cached, with source type, confidence,
    grounding and model.
  - *Local only:* entries are served for 30 days and labelled "checked on <date>"; older terms are
    flagged "needs refresh".
  - *Local only:* a failed refresh keeps the last good entry, and default estimates are never served
    from the cache.
  - *Local only:* other users' saved warranties are reused only when their terms came from an official
    page, for the same product line.
  - *Local only:* admin counts at `/admin/terms-cache/stats`.
  - *Local only:* knowledge base v1. Hand-checked entries come first, even on forced refreshes, and
    customers see "Checked on <date>". Locked entries are never overwritten: a disagreeing re-check is
    saved for review and admins are notified. Admin-only endpoints are audit-logged. The table is empty.
  - Shared brand names use the company that matches the product.
  - Unknown brands get "Estimated - please check your warranty card or the seller" and no guessed duration.
  - India pages are preferred, including philips.co.in. *philips.co.in is local only.*
- **AI providers.**
  - OpenAI and Mistral can each do invoice enrichment, summaries and OEM-page terms extraction.
  - If the chosen provider fails or times out, the other one is tried (`AI_PROVIDER_FALLBACK=0` turns
    this off). Text is redacted before either provider sees it. *Local only.*
- **Privacy.**
  - Buyer details are redacted before every AI call, including a buyer label in the middle of a line.
    *Mid-line masking is local only.*
  - The vision tier sends only redacted images.
- **Security.**
  - Admin security banner and HTTPS redirect behind the proxy.
  - CSRF on cookie sessions, and a stale session cookie never blocks sign-in.
  - Rate limits on sign-in (10 per 10 min) and sign-up (5 per hour), with friendly messages on the forms.
- **Real-invoice loop** (`scripts/run_real_invoices.py`, local, `real_invoices/` git-ignored).
  - Always writes `review.md` (what SWH read, with "OK?" / "Correct value if wrong" columns). Hand marks
    become pass/fail counts on re-run.
  - `expected.csv` is optional and adds automatic scoring in `report.md`.
  - `--provider openai|mistral|both` compares the providers.
  - Optional corrections log (`CORRECTIONS_LOG=1`, off by default) records what customers confirm or
    correct in the UI, with no personal data. *Local only.*

## Measured numbers

| What | Result | Data |
|---|---|---|
| Test suite | 491 passed, 2 skipped (live-network tests, opt-in with `SWH_LIVE_NETWORK_TESTS=1`) | - |
| Brand (30 labelled invoice photos) | 26 correct, 0 wrong, 4 missing | synthetic |
| Model | 0 stored wrong; 28 offered to confirm (2 exact, 26 need an edit); 0 stored correct | synthetic |
| Serial | 0 stored wrong; 30 offered to confirm, all need an edit | synthetic |
| Purchase date | 24 correct, 6 wrong | synthetic |
| Stated warranty months | 16 correct, 14 wrong | synthetic |
| Category | 26 correct, 4 missing | synthetic |
| Hard-to-read photos (10) | no text read; 9/10 can be sent to the vision tier after redaction; vision accuracy **unmeasured** (no API key) | synthetic |
| Marketplace invoices (4) | expected brand or suggestion, product, model (now incl. "HL7756/00") or blank, invoice no, date on all 4 | synthetic |
| OEM registry | 209 names; verified list 160 brand names, 178 brand-domain pairs, 122 distinct domains; 5 manually confirmed; 12 shared-brand families | - |
| Terms cache (local `data/app.db`) | 3 rows: 2 with a real source (Epson), 1 default-rules row | - |
| Real invoices | **not measured yet** | - |
| OpenAI vs Mistral on invoices | **not measured** (no keys locally; the local venv also lacks the `openai` package) | - |

## Known issues

- **Start-up schema upgrade on Postgres:** first run in production with this deploy (adds 5 nullable cache
  columns and 2 tables). If it failed, the app still runs with the terms cache and knowledge base off and
  `/admin/terms-cache/stats` shows the error; check that block once.
- **Provider fallback is live.** Production has both OpenAI and Mistral configured, so a failing provider's
  redacted request goes to the other one. Set `AI_PROVIDER_FALLBACK=0` to turn it off.
- **Exposed database password:** a screenshot in this conversation showed the production Postgres password
  in a connection URL. Rotate it in Railway (owner action).
- **Rate limiting:** anonymous clients are keyed on the first `X-Forwarded-For` entry. Whether Railway's
  proxy replaces or appends that header decides whether a client can dodge the limit. Unconfirmed.
- **Local setup:** the local `.venv` has no `openai` package, so OpenAI paths (and `--provider openai`)
  cannot run locally until `pip install -r requirements.txt`.
- **Registry:**
  - Still to review: Godrej, Toshiba, Hitachi, Polar, Pigeon, Prestige, Philips/Versuni, Sansui,
    Kelvinator, Pioneer, Orient Fans.
  - `honda2wheelersindia.com` and `ushainternational.com` are registry-only (failed the automated check).
- **OCR and extraction:**
  - Synthetic set: 6 wrong dates and 14 wrong stated durations; 10 hard photos read nothing.
  - On local Windows, Paddle 3.x fails and Tesseract is used.
- **Operational:**
  - The bare domain without www is a registrar parking page.
  - `/health` does not exist; use `/api/health`.
  - The first `/health/ocr` after a deploy takes about a minute.

## Next steps

1. Owner puts invoices in `real_invoices/`, runs `python scripts/run_real_invoices.py` (add
   `--provider both` once keys are in the local `.env` and `pip install -r requirements.txt` is done), and
   marks `review.md`. `expected.csv` is optional.
2. Rotate the production Postgres password; check the `schema` block of `/admin/terms-cache/stats`; do a
   real sign-in.
3. Start adding hand-checked entries to the knowledge base (`POST /admin/knowledge-base`).
4. Optional: add a Mistral vision / OCR provider for unreadable photos (what is needed is in MEMORY.md 94).
