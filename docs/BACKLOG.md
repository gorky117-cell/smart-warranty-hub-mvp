# Backlog (2026-10-06)

Open work in priority order. Tags: **[GAURAV]** needs the owner (a decision, keys, real invoices or a
production check); **[LOCAL]** can be done in code without the owner.

## Now
1. [GAURAV] Signed-in production checks: another user's `/notifications?user_id=...` and
   `/recommendations?user_id=...` answer 403; the `schema` block of `/admin/terms-cache/stats`; an uploaded
   invoice still opens under My documents after a redeploy.
2. [GAURAV] Rotate the production Postgres password (it appeared in a screenshot earlier).
3. [GAURAV] Fill the knowledge base with the top 30 pairs (docs/KB_WORKSHEET.md) on /ui/admin/knowledge-base;
   open the "browser" links (LG, Sony, Dell, OPPO) yourself.
4. [GAURAV] Confirm the official sites to add: Godrej Appliances (godrejenterprises.com), Prestige
   (ttkprestige.com, shop.ttkprestige.com); check Acer (acer.com) in a browser. [LOCAL] then add them.
5. [GAURAV] Real invoices: run `scripts/run_real_invoices.py` on your invoices and mark `review.md` (real
   accuracy is not measured yet).

## Next
6. [LOCAL] A better confirm step for models/serials read from scans/photos (today every confusable code is
   "please confirm": many confirmations).
7. [GAURAV] Keys: vision tier accuracy for unreadable photos and OpenAI-vs-Mistral comparison need API keys in
   the local `.env` (and `pip install -r requirements.txt` for the `openai` package).
8. [GAURAV] Brand permissions for showing their wording (reuse policy), or legal advice on short quotes in
   care guides (docs/CARE_SOURCES_CHECK.md).
9. [GAURAV] Decide whether to ask the Department of Consumer Affairs for a Right to Repair data feed;
   [LOCAL] then connect it as the partner feed (`services/partner_feed.py`).
10. [LOCAL] Warranty card upload as an add-on - only after invoice-only works well (single-entry rule).
11. [LOCAL] Care guides v2 (fetcher) - only after brand permission.

## Known gaps
12. [LOCAL] Brand-specific code kept on purpose: Redmi/POCO -> Xiaomi table, marketing-series names for models,
    Samsung-style section headings for multi-product pages, phone words galaxy/iphone/sm-, Epson serial rule.
13. [LOCAL] Review crawler (off in production), issue feeds and web search do not use the robots check.
14. [GAURAV] Sites that answer 403 to robots.txt (mi.com, sony.co.in, lenovo.com seen) cannot be re-verified or
    read automatically - accept, or ask those brands.
15. [GAURAV] Rate limiting keys anonymous users on the first `X-Forwarded-For` entry; confirm Railway's header
    behaviour.
16. [LOCAL] Hard photos in the synthetic set: 6 wrong dates, 14 wrong stated durations, 10 read nothing.
17. [LOCAL] Registry review: Toshiba, Hitachi, Polar, Pigeon, Philips/Versuni, Sansui, Kelvinator, Pioneer,
    Orient Fans; `honda2wheelersindia.com`, `ushainternational.com` are registry-only.
18. [GAURAV] The bare domain without www is a registrar parking page.
19. [LOCAL] Paddle 3.x fails on local Windows (Tesseract used); first `/health/ocr` after a deploy takes ~1 min.
