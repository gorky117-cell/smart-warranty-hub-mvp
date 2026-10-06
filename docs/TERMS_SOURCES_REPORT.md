# Warranty terms: sources, own-words display, knowledge-base priorities (2026-10-06)

## Source order (built)
1. **Partner feed** - placeholder; no partner connected, returns nothing.
2. **Verified knowledge base** - hand-entered facts (admin screen /ui/admin/knowledge-base), model first,
   then product line; never brand-wide.
3. **Saved official terms** - another saved product's terms or the terms cache, only when they came from the
   brand's verified official site, for the same product line.
4. **Brand website** - read only where robots.txt allows (robots_guard); facts shown in SWH's words with the
   source link and the date checked.
5. **"Estimated, please check"** - typical terms for the category plus a link to the brand's own site.

Customers never see the brand's sentences: terms, exclusions and claim steps are SWH-worded facts. A brand's
own wording would be shown only with permission in data/brand_reuse_policy.json (none today).

## What each source covers today
| Source | Brands | Categories | Notes |
|---|---|---|---|
| Partner feed | none | none | placeholder |
| Knowledge base | production: not known from here (no admin login used); locally only test entries | - | owner/admin adds entries on the new screen; the screen shows the count |
| Saved official terms / cache | production: not known from here | - | grows as customers upload invoices for brands with readable official pages |
| Brand website | registry: 209 names; 160 with a verified site, 5 manually confirmed. robots.txt checked for 16 sites on 2026-10-06: support pages allowed on 12; mi.com, sony.co.in, lenovo.com returned 403 (now treated as "not allowed"); canon.co.in served a web page instead | any category the page covers; product sections are split only on pages using the heading words seen on Samsung's page (mobile, TV & AV, PC & office, home appliances, ...) | robots is now re-checked live (24 h cache) before every page read |
| "Estimated, please check" | every brand without the above, including unknown brands | defaults by category: mobile 12, electronics 12, appliance 24, EV 36, general 12 months | link to the brand's site when it has a verified one |

## Where the brand's own wording can still appear
| Place | Who sees it | Status |
|---|---|---|
| Dashboard: What is covered, Warranty facts, Easy summary, Your warranty in 5 lines, care tips, notifications | customers | SWH wording only (facts) |
| Download summary (txt/html/pdf) and claim PDF summary page | customers | SWH wording only; the claim PDF also attaches the customer's own invoice |
| Care guides (admin-entered quotes) | customers | hidden unless the brand's policy is summary_ok (tip, no quote) or full_text_ok (quote) |
| AI summary text (GET /warranties/{id}/summary "summary") | not shown on the page (hidden element) | built from SWH-worded facts; may add context from the RAG store (saved summaries) |
| Older pages (/ui/warranty-tabs, /ui/react-dashboard, /ui/console) | logged-in users | use the same API, so SWH wording |
| Admin: GET /admin/warranties/{id}/oem-text, knowledge-base re-check reviews, terms-cache stats | admins only | the brand's wording as stored, for checking |
| Database (warranties, terms cache) | nobody directly | keeps the brand's wording as read, for re-checks and facts |

## Top 30 brand + category pairs to add to the knowledge base first
Not measured: SWH has no real-invoice volume data yet. This order is an estimate from the Indian market
(brands that sell the most units in each category) across the requested categories. "Site" = verified official
site in the registry (needed before an entry can be saved).

| # | Brand | Category | Site |
|---|---|---|---|
| 1 | Samsung | Phone | samsung.com |
| 2 | Xiaomi (Redmi, POCO) | Phone | mi.com |
| 3 | vivo | Phone | vivo.com |
| 4 | OPPO | Phone | oppo.com |
| 5 | realme | Phone | realme.com |
| 6 | Apple | Phone | apple.com |
| 7 | OnePlus | Phone | oneplus.com |
| 8 | Samsung | TV | samsung.com |
| 9 | LG | TV | lg.com |
| 10 | Sony | TV | sony.co.in |
| 11 | Voltas | AC | voltas.com |
| 12 | LG | AC | lg.com |
| 13 | Daikin | AC | daikinindia.com |
| 14 | Lloyd (Havells) | AC | lloydindia.in |
| 15 | LG | Fridge | lg.com |
| 16 | Samsung | Fridge | samsung.com |
| 17 | Whirlpool | Fridge | whirlpool.in |
| 18 | Godrej Appliances | Fridge | **none verified** - verify the domain first |
| 19 | LG | Washing machine | lg.com |
| 20 | Samsung | Washing machine | samsung.com |
| 21 | IFB | Washing machine | ifbappliances.com |
| 22 | Racold | Geyser | racold.com |
| 23 | AO Smith | Geyser | aosmithindia.com |
| 24 | Havells | Geyser | havells.com |
| 25 | HP | Laptop | hp.com |
| 26 | Lenovo | Laptop | lenovo.com |
| 27 | Dell | Laptop | dell.com |
| 28 | HP | Printer | hp.com |
| 29 | Epson | Printer | epson.co.in |
| 30 | Bajaj Electricals | Small appliance (mixer, fan, iron) | bajajelectricals.com |

Next in line: Asus and Acer laptops (Acer has no verified site), Canon and Brother printers, Philips, Prestige
(no verified site) and Havells small appliances, Haier fridges, Blue Star ACs, Crompton geysers, Motorola phones,
Xiaomi and TCL TVs.
