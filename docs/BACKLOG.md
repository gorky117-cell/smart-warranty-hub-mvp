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
6. A better confirm step for models/serials read from scans/photos (today every confusable code is
   "please confirm": many confirmations).
7. [NEEDS-KEYS] Keys: vision tier accuracy for unreadable photos and OpenAI-vs-Mistral comparison need API keys in
   the local `.env` (and `pip install -r requirements.txt` for the `openai` package).
8. [GAURAV] Brand permissions for showing their wording (reuse policy), or legal advice on short quotes in
   care guides (docs/CARE_SOURCES_CHECK.md).
9. [GAURAV] Decide whether to ask the Department of Consumer Affairs for a Right to Repair data feed;
   then connect it as the partner feed (`services/partner_feed.py`).
10. Warranty card upload as an add-on - only after invoice-only works well (single-entry rule).
11. Care guides v2 (fetcher) - only after brand permission.

## Known gaps
20. Passwords are hashed with PBKDF2 and one app-wide salt (`deps.hash_password`). Move to a per-user salt
    (re-hash on next sign-in) - needs care so existing passwords keep working.
21. Rate limits are kept in memory per process: they reset on every deploy and are not shared if Railway runs
    more than one instance.
12. Brand-specific code kept on purpose: Redmi/POCO -> Xiaomi table, marketing-series names for models,
    Samsung-style section headings for multi-product pages, phone words galaxy/iphone/sm-, Epson serial rule.
13. Review crawler (off in production), issue feeds and web search do not use the robots check.
14. [GAURAV] Sites that answer 403 to robots.txt (mi.com, sony.co.in, lenovo.com seen) cannot be re-verified or
    read automatically - accept, or ask those brands.
15. [NEEDS-KEYS] Rate limiting keys anonymous users on the first `X-Forwarded-For` entry; confirm Railway's header
    behaviour.
16. Hard photos in the synthetic set: 6 wrong dates, 14 wrong stated durations, 10 read nothing.
17. Registry review: Toshiba, Hitachi, Polar, Pigeon, Philips/Versuni, Sansui, Kelvinator, Pioneer,
    Orient Fans; `honda2wheelersindia.com`, `ushainternational.com` are registry-only.
18. [GAURAV] The bare domain without www is a registrar parking page.
19. Paddle 3.x fails on local Windows (Tesseract used); first `/health/ocr` after a deploy takes ~1 min.
