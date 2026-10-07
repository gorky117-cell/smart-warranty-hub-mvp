# Backlog (2026-10-07)

Open work in priority order. Tags: **[NEEDS-KEYS]** needs API keys, real invoices or production data (cannot be
done in the cloud session); **[GAURAV]** needs the owner's decision or manual work. No tag: code work the cloud
session can do (one branch per batch, `cloud/batch-N`).

## Now
0. Forgot password + e-mail (cloud batch 1, branch `cloud/batch-1`):
   - [x] Resend or SMTP chosen by config, tags app=swh / type=<message>, Reply-To, text + HTML, no addresses in logs.
   - [x] "Forgot password?" link, same answer for unknown e-mails, hashed one-time 30-minute links, older links
     retired, plain pages for expired/used links, every session signed out, rate limits per client and account.
   - [x] Railway variable list: docs/EMAIL_SETUP.md.
   - [GAURAV] Review and merge the pull request (after a production backup); set the Railway variables in
     docs/EMAIL_SETUP.md; send yourself a reset link and follow the checks there.
1. [NEEDS-KEYS] Signed-in production checks: another user's `/notifications?user_id=...` and
   `/recommendations?user_id=...` answer 403; the `schema` block of `/admin/terms-cache/stats`; an uploaded
   invoice still opens under My documents after a redeploy.
2. [GAURAV] Rotate the production Postgres password (it appeared in a screenshot earlier).
3. [GAURAV] Fill the knowledge base with the top 30 pairs (docs/KB_WORKSHEET.md) on /ui/admin/knowledge-base;
   open the "browser" links (LG, Sony, Dell, OPPO) yourself.
4. [GAURAV] Confirm the official sites to add: Godrej Appliances (godrejenterprises.com), Prestige
   (ttkprestige.com, shop.ttkprestige.com); check Acer (acer.com) in a browser. Then add them in code.
5. [NEEDS-KEYS] Real invoices: run `scripts/run_real_invoices.py` on your invoices and mark `review.md` (real
   accuracy is not measured yet).

## Next
6. [x] A better confirm step for models/serials read from scans/photos (cloud batch 2): the characters to check
   are highlighted; when exactly one O/0, I/1, S/5, B/8 reading is a known model it is offered pre-filled (still
   confirmed); models confirmed or typed by 2+ different customers for a brand count as known, so repeat
   products need no confirmation. Next: measure how many confirmations remain on real invoices [NEEDS-KEYS].
7. [NEEDS-KEYS] Keys: vision tier accuracy for unreadable photos and OpenAI-vs-Mistral comparison need API keys in
   the local `.env` (and `pip install -r requirements.txt` for the `openai` package).
8. [GAURAV] Brand permissions for showing their wording (reuse policy), or legal advice on short quotes in
   care guides (docs/CARE_SOURCES_CHECK.md).
9. [GAURAV] Decide whether to ask the Department of Consumer Affairs for a Right to Repair data feed;
   then connect it as the partner feed (`services/partner_feed.py`).
10. Warranty card upload as an add-on - only after invoice-only works well (single-entry rule).
11. Care guides v2 (fetcher) - only after brand permission.

## Done in cloud batch 3 (branch `cloud/batch-3`)
- [x] Amazon 2017 invoice: date after headings, seller from "Sold By", model from bracketed specs, price /
  capacity / stars / type, delivery city+state with consent, duplicate invoices, customer screens, estimates
  without numbers, Voltas diagnosis (docs/VOLTAS_DIAGNOSIS.md), risk wording. (Question packs are owned by
  `desktop/batch-3`; this branch only asks its approved packs.)

## Known gaps
23. "Please check these details" (model/serial to confirm) still sits inside the collapsed "More product details"
    on the dashboard; move it next to the 5 lines like the duplicate and region notices.
24. [x] Reminders, notifications and the claim PDF use only confirmed end dates (cloud batch 3 review):
    warranty_card.confirmed_end_date; estimated/unknown -> "Check your warranty card", no expiry reminder.
22. ACs, fridges and washing machines share the invoice category "appliance" (default 24 months for all); give each
    product line its own category for defaults and lookups (docs/VOLTAS_DIAGNOSIS.md).
20. [x] Per-user password salt (cloud batch 2): new hashes `pbkdf2_sha256$200000$<salt>$<hash>`; old shared-salt
    hashes still verify and are upgraded on the next sign-in. Accounts that never sign in again keep the old
    hash (still safe to verify; weaker only if the database leaks).
21. [x] Rate limits survive deploys (cloud batch 2): hits stored in the database (table rate_limit_hits, keys
    hashed), shared by all instances; memory fallback if the database fails; RATE_LIMIT_BACKEND=memory for the
    old behaviour.
12. Brand-specific code kept on purpose: Redmi/POCO -> Xiaomi table, marketing-series names for models,
    Samsung-style section headings for multi-product pages, phone words galaxy/iphone/sm-, Epson serial rule.
13. [x] Review crawler and issue feeds use the robots check (cloud batch 2): robots_guard, failing closed (the
    crawler used to read pages when robots.txt could not be read, and REVIEW_ROBOTS_RESPECT=false switched the
    check off; both removed). Web search: provider APIs (Bing, Brave, Google, Serper, SerpAPI) are API calls under
    their own terms, not page reads, so robots.txt does not apply; the result pages are read only through the
    crawler, which now checks robots.txt.
14. [GAURAV] Sites that answer 403 to robots.txt (mi.com, sony.co.in, lenovo.com seen) cannot be re-verified or
    read automatically - accept, or ask those brands.
15. [NEEDS-KEYS] Rate limiting keys anonymous users on the first `X-Forwarded-For` entry; confirm Railway's header
    behaviour.
16. [x] Synthetic 50-sample set (cloud batch 2, Tesseract): small text is enlarged before OCR -> dates 30/30 (4 wrong
    before), stated durations 30/30 (14 wrong before), invoice numbers 30/30 (0 before); global check unchanged.
    Still open: the 10 blurred, tilted "hard" photos read nothing (enlarging gives garbage such as "14 months" for
    24, so nothing is safer: the customer gets "We couldn't read this invoice"); Paddle (production's first
    engine) not measured here.
17. Registry review: Toshiba, Hitachi, Polar, Pigeon, Philips/Versuni, Sansui, Kelvinator, Pioneer,
    Orient Fans; `honda2wheelersindia.com`, `ushainternational.com` are registry-only.
18. [GAURAV] The bare domain without www is a registrar parking page.
19. Paddle 3.x fails on local Windows (Tesseract used); first `/health/ocr` after a deploy takes ~1 min.
