# Smart Warranty Hub - status (2026-10-04)

Measured numbers only. **Synthetic** marks results from generated test files, not real customer
invoices. No real-invoice accuracy has been measured yet (see "Next steps").

## Live vs local

- **Live** (https://www.smartwarrantyhub.com, Railway deploys `origin/master`): up to commit `25e9d895`.
  - Fix run 91: redaction before AI calls, Paddle back-off with Tesseract fallback, one risk scorer,
    domain verification, vision tier (off by default), expiry recalculation guard, admin security banner.
  - Follow-up run 92: "From the official <Brand> website" label, Orient Electric fix, manually confirmed
    sites (LG, Sony, Dell, Panasonic, Whirlpool), extraction suggestions, unreadable-invoice message,
    hermetic tests.
  - Paddle kept, with a background warm-up at start-up.
- **Local only, not pushed** (awaiting approval):
  - shared brand names resolved by product (`b53433eb`);
  - marketplace invoices (`b147af43`);
  - sign-in stale-cookie fix (`2e472d20`, `7e858a89`);
  - real-invoice runner (`251bc733`);
  - this status update.

Live checks on 2026-10-04 after the last deploy:

| Check | Result |
|---|---|
| `/api/health` | 200 `{"status":"ok"}` |
| `/health/ocr` | 200 ok; Paddle reads the test image |
| Paddle warm-up | finished in 106.5 s; start-up did not wait for it |
| `/login` | 200 |
| http to https | one 301 redirect, no loop |
| Pages behind login | redirect once to `/login?next=...` |

A real sign-in was not tested; no production credentials were used.

## What works

- **Upload pipeline.** Accepts PDF (text layer, or OCR for scans), photos, `.docx` and `.txt`. Paddle OCR
  runs in production with Tesseract as fallback; when Paddle is missing or failing, Tesseract is used.
- **Field extraction.**
  - Brand, product, model, serial, invoice number, date and stated warranty months.
  - Low-confidence brand, model or serial values, misread labels ("Band:", "Modet"), and brands not in
    the registry become **suggestions the customer confirms**. They are never stored as fact.
  - Printed model codes beat marketing names.
  - Marketplace rows (Amazon, Flipkart, Croma, Reliance Digital) are trimmed to the product title. The
    seller is never taken as the brand. *Local only.*
- **Unreadable invoices.** These show "We couldn't read this invoice - retake the photo or enter the
  details", with a details form. No estimated coverage is shown.
- **Warranty terms.**
  - Taken only from registry or verified OEM sites, labelled "From the official <Brand> website", or
    "(manually confirmed)" for the five sites that block automated checks.
  - Shared brand names (Bajaj, Honda, Hero, Yamaha, Hyundai, Usha, Wipro, Nokia, Tata, Kenmore, Havells,
    Crompton) use the right company for the product. Lenders such as Bajaj Finserv are never used.
    *Local only.*
  - Unknown or small brands get "Estimated - please check your warranty card or the seller" and no
    guessed duration. *Local only.*
  - India pages are preferred for global brands. *Local only.*
- **Risk.** One scorer for every endpoint (ML first, heuristic fallback).
- **Notifications.** Expiry reminders; recalculated expiry dates never trigger them.
- **Privacy.** Buyer details are redacted before every AI call; the vision tier sends only redacted
  images.
- **Security.**
  - Admin security banner.
  - HTTPS redirect behind the proxy.
  - CSRF on cookie sessions. A stale or expired session cookie no longer blocks sign-in, and browsers get a
    "session expired" page instead of a raw error. *Local only.*

## Measured numbers

| What | Result | Data |
|---|---|---|
| Test suite | 437 passed, 2 skipped (live-network tests, opt-in with `SWH_LIVE_NETWORK_TESTS=1`) | - |
| Brand (30 labelled invoice photos) | 26 correct, 0 wrong, 4 missing | synthetic |
| Model | 0 stored wrong; 28 offered to confirm (2 exact, 26 need an edit); 0 stored correct | synthetic |
| Serial | 0 stored wrong; 30 offered to confirm, all need an edit | synthetic |
| Purchase date | 24 correct, 6 wrong | synthetic |
| Stated warranty months | 16 correct, 14 wrong | synthetic |
| Category | 26 correct, 4 missing | synthetic |
| Hard-to-read photos (10) | no text read; 9/10 can be sent to the vision tier after redaction; vision accuracy **unmeasured** (no API key) | synthetic |
| Marketplace invoices (4) | expected brand or suggestion, product, model/blank, invoice no, date on all 4 | synthetic |
| OEM registry | 209 names; verified list 160 brand names, 176 brand-domain pairs, 121 distinct domains; 5 manually confirmed; 12 shared-brand families | - |
| Real-invoice runner, 3 files, offline, no AI | text 3/3, fields 1/3, OEM domain 2/3, warranty page 0/3 (offline), duration 2/3, summary 1/3 | synthetic |
| Real invoices | **not measured yet** | - |

## Known issues

- **Live until Part 2 is pushed:**
  - Signing in shows a raw "CSRF token missing or invalid" when the browser holds an old session cookie.
  - Shared brand names can pick up another company's terms.
  - Unknown brands get a guessed default duration (labelled "Estimated").
- **Found by the runner, not fixed:**
  - `philips.co.in` is missing from the registry (only `philips.com`).
  - Model "HL7756/00" is cut at "/".
- **Registry and sites:**
  - Registry names still to review: Godrej, Toshiba, Hitachi, Polar, Pigeon, Prestige, Philips/Versuni,
    Sansui, Kelvinator, Pioneer, Orient Fans (`docs/REGISTRY_REVIEW_2026-10-04.md`).
  - `honda2wheelersindia.com` and `ushainternational.com` failed the automated check, so they are
    registry-only.
- **OCR and extraction:**
  - Synthetic set: 6 wrong dates and 14 wrong stated durations (OCR misreads); 10 hard photos read nothing.
  - On local Windows, Paddle 3.x fails (oneDNN) and Tesseract is used. Production Linux Paddle works.
- **Operational:**
  - The bare domain `smartwarrantyhub.com` (no www) is a registrar parking page, not the app.
  - `/health` does not exist; use `/api/health`.

## Next steps

1. Owner fills `real_invoices/` (git-ignored) and `real_invoices/expected.csv`, then runs
   `python scripts/run_real_invoices.py` (AI is used only if keys are in the local `.env`) and reviews
   `real_invoices/report.md`.
2. Approve and push Part 2 (CSRF fix, shared brands, marketplace invoices) and Part 4.
3. Fix the two runner findings; finish the registry review list.
4. With an API key: measure the vision tier on hard photos and AI enrichment on real invoices.
