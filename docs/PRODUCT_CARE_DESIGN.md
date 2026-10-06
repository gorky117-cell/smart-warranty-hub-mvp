# Product-specific care - design and v1 (run 3, item 9)

## Goal
For each brand + model, show care advice taken from the brand's own user manual and official FAQ, next to
the tips already derived from the product's own warranty exclusions. Every tip shows where it came from;
nothing is invented. Each model is researched once and saved.

## What v1 does (built)
- Table `care_guides` (one row per brand + scope + source page): `company`, `product_scope`
  (`model:<key>` or `line:<product line>`, the same keys as the verified knowledge base), `source_kind`
  (`manual` or `faq`), `source_url`, `source_title`, `tips` (`text`, `quote`, `page`), `checked_by`,
  `checked_at`, `knowledge_base_id` (link to the hand-checked warranty-terms entry for the same product).
- `POST /admin/care-guides` (admin only) saves what an admin read:
  - the company must be in the OEM registry and the page on its verified or manually confirmed official
    domain (same check as the knowledge base);
  - a model or product line is required, never brand-wide;
  - each tip needs the exact sentence from the page (`quote`); the tip text may shorten it but every
    content word must appear in the quote (`care_guides.grounded_tip`), so a tip cannot add a claim.
  - Saving the same page again replaces its tips, so each model is researched once.
- Customers: `/recommendations?warranty_id=...` adds the saved tips (model first, else product line) to
  "How to look after it", each with "From <Brand>'s user manual, page N" linked to the page and the quote.
- No crawler and no fetching in v1.

## Planned sources (not crawled - needs the owner's approval first)
Only the brand's own pages on its verified official domain. Before any automated fetching, for each site:
read its terms of use and robots.txt, and fetch only pages they allow, at a low rate, with a named
user agent. Until then, guides are entered by hand from pages a person opened.

| Brand (test mix) | Verified domain(s) in the registry | Planned pages | Terms / robots checked (2026-10-06, docs/CARE_SOURCES_CHECK.md) |
|---|---|---|---|
| Samsung | samsung.com | /in/support/ model pages: user manual PDF, "Troubleshooting" FAQ | No reuse without permission |
| Xiaomi (Redmi, POCO) | mi.com, xiaomi.com | mi.com/in/support: user guides, FAQ | Unknown (robots blocked) |
| LG | lg.com (manually confirmed) | lg.com/in/support: manuals, help library | No without written consent |
| Sony | sony.co.in (manually confirmed) | sony.co.in support: manuals, FAQ | Unknown (blocked) |
| HP | hp.com | support.hp.com: product manuals, "Document" FAQs | No copying; linking allowed |
| Voltas | voltas.com | user manuals / FAQ pages | Unknown (robots allows AI crawlers; terms not found) |
| IFB | ifbappliances.com | user manuals / FAQ | Unclear - read by a person |
| Racold | racold.com | product manuals / FAQ | Unknown |
| Epson | epson.co.in, epson.com | product support: user's guide, FAQ | No without consent |
| Apple | apple.com | support.apple.com: user guides, support articles | No (automated access forbidden) |
| Philips | philips.co.in, philips.com | product support: user manual, FAQ | Unclear - read by a person |
| Havells, Lenovo, Daikin, Canon, Brother | see registry | manuals / FAQ | Unknown (see the check) |

Bajaj (fixed 2026-10-06): the bare name "Bajaj" no longer has official domains; a Bajaj appliance resolves to
Bajaj Electricals (bajajelectricals.com), a two-wheeler to Bajaj Auto, and Bajaj Finserv never.

## v2 (not built)
1. After approval, a fetcher limited to the approved pages above that saves the page text and fingerprint
   and proposes tips (each sentence that gives an instruction: "do not", "always", "clean", "keep") for an
   admin to accept; nothing goes to customers without the accept step.
2. Re-check guides when the page fingerprint changes (as the knowledge base does for terms).
3. Care reminders from guide tips that state an interval ("clean the filter every two weeks").
