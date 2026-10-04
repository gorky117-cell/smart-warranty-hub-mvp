# Smart Warranty Hub - status (2026-10-04, late)

Measured numbers only. **Synthetic** marks results from generated test files, not real customer
invoices. No real-invoice accuracy has been measured yet (see "Next steps").

## Live vs local

- **Live** (https://www.smartwarrantyhub.com, Railway deploys `origin/master`): up to commit `eac60ead`.
  - Fix run 91: redaction before AI calls, Paddle back-off with Tesseract fallback, one risk scorer,
    domain verification, vision tier (off by default), expiry recalculation guard, admin security banner.
  - Follow-up run 92: "From the official <Brand> website" label, Orient Electric fix, manually confirmed
    sites (LG, Sony, Dell, Panasonic, Whirlpool), extraction suggestions, unreadable-invoice message,
    hermetic tests.
  - Consolidated run 93:
    - Paddle kept, with a background warm-up;
    - shared brand names resolved by product;
    - marketplace invoices;
    - unknown brands get "please check";
    - India pages preferred;
    - sign-in stale-cookie fix with a friendly session-expired page;
    - real-invoice runner;
    - STATUS.md.
  - Sign-up rate limit (`eac60ead`).
- **Local only, not pushed.** The push was approved on condition that Railway's health check uses
  `/api/health`. The repo defines no health check, so this can't be confirmed from the files; it has to
  be checked in the Railway dashboard first.
  - `bc85e1ca`: philips.co.in; model codes keep "/" parts.
  - `025e21a8`: MISTRAL_EMBED_MODE is read; the Mistral summary helper redacts on its own.
  - `682af6ad`: OpenAI <-> Mistral fallback; buyer labels in the middle of a line are masked.
  - `557e6c6e`: runner review mode with hand marks, `--provider` comparison, local corrections log.
  - `a5ab512f`: status/MEMORY update.
  - Terms-cache fixes:
    - `a8df141b`: product scope in the key.
    - `2d3926f9`: no reuse of estimates as "confirmed".
    - `9a7de517` + `4ed67981`: newest official entry, metadata, official-only caching.
    - `8f9c94ca`: 30-day expiry and "checked on".
    - `6dc8aa69`: admin counts.
  - `a4ad9b63`: knowledge base v1 (empty).
  - This status update.

Live checks on 2026-10-04 19:27 after the last deploy:

| Check | Result |
|---|---|
| `/api/health` | 200 `{"status":"ok"}` |
| `/health/ocr` | 200 ok; Paddle active |
| Paddle warm-up | finished in 85.3 s; start-up did not wait for it |
| First `/health/ocr` call after deploy | 69.5 s (real OCR with both engines; then cached 10 min) |
| `/login` | 200 |
| http to https | one 301 redirect, no loop |
| Sign-in with an old session cookie | goes back to the form (`error=invalid` for a probe user); no 403 |
| `/login` with an old session cookie | clears it and issues a fresh CSRF token |

A real sign-in was not tested; no production credentials were used (the owner will check).

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
| Test suite | 488 passed, 2 skipped (live-network tests, opt-in with `SWH_LIVE_NETWORK_TESTS=1`) | - |
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

- **Terms cache: fixed locally, live until pushed.** On the live site the key is still brand + coarse
  category + region, a failed refresh hides the last good entry, and other users' default-rule terms can
  show as "Confirmed from saved warranty record". The local fixes also add columns to
  `warranty_terms_cache` at start-up (ADD COLUMN IF NOT EXISTS on Postgres, a path not run locally).
- **When pushed, the provider fallback is live in production.** Production has both OpenAI and Mistral
  configured, so a failing provider's redacted request will go to the other provider. Set
  `AI_PROVIDER_FALLBACK=0` to keep the old behaviour.
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
2. Approve and push the local commits above.
3. Check Railway's health-check path, then approve the push. After deploy, look at
   `/admin/terms-cache/stats` and start adding hand-checked entries to the knowledge base.
4. Optional: add a Mistral vision / OCR provider for unreadable photos (what is needed is in MEMORY.md 94).
