# Care sources: robots.txt and terms of use (read-only check, 2026-10-06)

What was done: one GET of each site's `/robots.txt` and of its terms-of-use page (if one could be found at
the usual addresses), then a search of the terms text for clauses on robots/scraping/automated access,
copying, reproduction and commercial use. **No manual, FAQ or support page was fetched; nothing was
crawled.** Quotes are kept short; read the full terms before deciding.

"robots.txt allows" means the planned support/manual paths are not disallowed for a generic crawler.
It does not grant any right to copy or reuse content - that is what the terms decide.

## Result per source

| Brand | robots.txt | Terms of use | May we crawl and reuse? |
|---|---|---|---|
| Samsung (samsung.com/in) | Allows /in/support/ for all agents (incl. named AI crawlers) | Legal page: users may save content to their own equipment but "not ... transfer ... to third parties" | **No** for reuse without permission (redistribution not allowed) |
| Xiaomi (mi.com) | Could not be read (403 to our check) | User agreement read; no clause about site content reuse found | **Unknown** - not cleared |
| LG (lg.com/in) | Allows /in/support/ paths | Copy "for personal, non-commercial use" only; no copying "for commercial use without the express written consent of LG" | **No** without LG's written consent |
| Sony (sony.co.in) | Could not be read (403) | Not found / blocked | **Unknown** - not cleared |
| HP (hp.com, support.hp.com) | Allows support paths; named AI crawlers not blocked from them | "You may link to, but may not copy, any Materials"; reproduction prohibited without consent | **No copying; linking is allowed** |
| Voltas (voltas.com) | Allows everything, and explicitly allows GPTBot, CCBot, ClaudeBot, AnthropicAI | Not found at the usual addresses | **Unknown** - robots friendly, terms not read |
| IFB (ifbappliances.com) | Allows /support, /faqs, /manuals | Terms page found; no clause on copying or automated access found by the search | **Unclear** - needs a person to read the page |
| Racold (racold.com) | Allows all (2-line file) | Not found | **Unknown** |
| Epson (epson.co.in) | Allows /Support/ paths | No distributing/reproducing without consent; download "for your non-commercial, personal use only" | **No** without Epson's consent |
| Apple (support.apple.com) | Allows /en-in/guide/ and /docs/ | Forbids any "robot", "spider" or other automatic device to access, copy or monitor any portion of the site | **No** (automated access forbidden) |
| Philips (philips.co.in) | Allows support paths | Terms page found; clause found only about software redistribution | **Unclear** - needs a person to read |
| Havells (havells.com) | Allows support paths, crawl-delay 10 s | Not found | **Unknown** |
| Lenovo (lenovo.com) | Could not be read (403) | Only the trademark page was read (product names may be used to refer to products) | **Unknown** for content |
| Daikin (daikinindia.com) | Allows all | Address tried returned a 404 page | **Unknown** |
| Canon (in.canon) | Allows /en/support, crawl-delay 30 s | Not found | **Unknown** |
| Brother (brother.in) | Allows /support (blocks only PerplexityBot) | Not found | **Unknown** |

## Summary

- **Cleared for automated crawling and reuse: none.** robots.txt alone allows the paths on 12 of 16 hosts,
  but every terms page that could be read either forbids copying/commercial reuse (Samsung, LG, HP, Epson)
  or forbids automated access outright (Apple). 5 hosts could not be checked (Xiaomi, Sony, Lenovo: robots
  blocked; several terms pages not found).
- **What this means for v1 (already built):** care guides are entered by a person, each tip a short quote
  with a link to the brand's page. Linking is explicitly allowed by HP; short quotes for information may
  still need the brands' permission or legal advice - an owner decision, not settled here.
- **Before any crawler (v2):** written permission from each brand, or a licensed data source; Voltas
  (robots welcomes AI crawlers) is the first candidate to ask, once its terms are found and read.
