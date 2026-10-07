# Why terms for Voltas window ACs were not found (batch 3 item 8, 2026-10-07)

This was a read-only check. One robots.txt request and one page read were planned; the cloud session's network
blocks voltas.com (proxy error), so neither ran. Nothing was crawled. The trace below ran on a scratch
database with the network switched off, which is the same state as a lookup that finds no source.

## Result of the lookup

`lookup_terms(brand="Voltas", product="Voltas 1.5 Ton 3 Star Window AC", category="appliance", region="IN")`
returned `internal://default_rules`: "Standard coverage for 24 months from purchase date." Customers saw this
as an estimate. Since batch 3 item 7, an estimate no longer shows a period. ACs get the "shorter period on the
whole unit, longer on the main part" sentence instead.

## Each possible cause, checked

| Possible cause | Finding |
|---|---|
| No registry entry | **Not the cause.** `data/oem_domains.json` and `data/oem_verified.json` list `Voltas -> voltas.com`. The 2026-10-03 domain check passed (DNS ok, HTTPS 200, same-brand redirects, brand evidence in the title). |
| robots.txt | **Not the cause.** docs/CARE_SOURCES_CHECK.md: voltas.com allows everything and explicitly allows GPTBot, CCBot, ClaudeBot and AnthropicAI. The worksheet records the terms page as "ok" (robots allowed, 200) on 2026-10-06. |
| JavaScript-only page | **Not checked from here** (the network is blocked). The `/pages/...` address is the usual pattern of a storefront that renders its pages on the server, so a JavaScript-only page is unlikely. The owner should open it in a browser with JavaScript off. |
| Category mismatch | **Partly.** The invoice reader labels ACs "appliance" (fridges and washing machines too), so the default for "appliance" (24 months) was used. The product-line logic does recognise the item as `air_conditioner`, so a real Voltas AC page would not be rejected as the wrong product. Window and split ACs share the `air_conditioner` line. |
| **No source to read** | **The cause.** Brand pages are only read (1) from the knowledge base, (2) from saved official copies, or (3) from pages discovery finds. (1) is empty: the Voltas link is in docs/KB_WORKSHEET.md row 11 but has not been entered. (2) has no Voltas entry. (3) has two inputs. `data/warranty_sources.json` lists only Acmeco, Epson, Quickfix and Samsung. The web-search providers need an API key, and none is set (MEMORY 89.4). So discovery returned 0 candidates and the lookup fell through to the estimate. |

## Also worth knowing

- **This invoice is from April 2017.** Even with the brand's terms, the page shows today's terms, which may
  differ from those in force in 2017. Any short unit warranty and a typical 5-year compressor period ended
  before 2023.
- **The same gap applies to every brand** that has no knowledge-base entry and no curated source, whenever no
  search key is set.

## What fixes it (no crawling needed)

1. **[GAURAV]** Enter Voltas on `/ui/admin/knowledge-base` from the worksheet link
   (`https://www.voltas.com/pages/terms-conditions-product-warranty`). Give the unit and compressor periods per
   product line (window and split if they differ), with the page as the source. This is backlog item 3.
2. **[NEEDS-KEYS]** Optional: set one search provider key so discovery can find official pages for brands
   that are not in the knowledge base yet.
3. Code (later batch): give ACs their own category in the invoice reader instead of "appliance", so defaults
   and lookups are per product line.
