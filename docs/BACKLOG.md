# Backlog (2026-10-06)

Open work, from MEMORY.md and STATUS.md. Owner decisions first; then product work; then known gaps.

## Waiting for the owner
- Approve the push of the local commits after `7971a633` (backup first).
- Signed-in checks in production: another user's `/notifications?user_id=...` and `/recommendations?user_id=...`
  answer 403; the `schema` block of `/admin/terms-cache/stats`; an uploaded invoice still opens under
  My documents after a redeploy.
- Confirm official sites to add: Godrej Appliances (godrejenterprises.com), Prestige (ttkprestige.com,
  shop.ttkprestige.com); Acer (acer.com) could not be reached from here - verify in a browser.
- Brand permissions for showing their wording (reuse policy) or legal advice on short quotes in care guides
  (docs/CARE_SOURCES_CHECK.md).
- Whether to ask the Department of Consumer Affairs about a data feed from the Right to Repair portal.
- Rotate the production Postgres password (it appeared in a screenshot earlier).

## Product
- Fill the knowledge base with the top 30 pairs (docs/KB_WORKSHEET.md) on /ui/admin/knowledge-base.
- Warranty card upload as an add-on (after invoice-only works well; single-entry rule).
- Partner feed: connect a real feed (placeholder in `services/partner_feed.py`).
- Real-invoice accuracy: run `scripts/run_real_invoices.py` on the owner's invoices and mark `review.md`.
- OCR'd codes: a better confirm step for models/serials read from scans/photos (now all "please confirm").
- Vision tier for unreadable photos: accuracy unmeasured (needs an API key locally).
- Care guides v2 (fetcher) only after brand permission.

## Known gaps
- Brand-specific code kept on purpose: Redmi/POCO -> Xiaomi table, marketing-series names for models,
  Samsung-style section headings for multi-product pages, phone words galaxy/iphone/sm-, Epson serial rule.
- Sites that block robots.txt (mi.com, sony.co.in, lenovo.com answered 403 to our checks) cannot be
  re-verified or read automatically.
- Review crawler (off in production), issue feeds and web search do not go through the robots check (not brand
  sites).
- Rate limiting keys anonymous users on the first `X-Forwarded-For` entry; Railway's header behaviour is
  unconfirmed.
- Synthetic set: wrong dates (6) and stated durations (14) on hard photos; 10 hard photos read nothing.
- Registry review list: Toshiba, Hitachi, Polar, Pigeon, Philips/Versuni, Sansui, Kelvinator, Pioneer, Orient Fans;
  `honda2wheelersindia.com`, `ushainternational.com` are registry-only.
- Operational: the bare domain without www is a parking page; first `/health/ocr` after a deploy takes ~1 minute.
- Local: Paddle 3.x fails on Windows (Tesseract is used); the local venv lacks the `openai` package.
