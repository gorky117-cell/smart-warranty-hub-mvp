# Warranty Search Flow (OCR -> Terms)

This is the production lookup sequence after a user uploads an invoice/warranty artifact.

## Runtime Flow

1. OCR + extraction
- Parse invoice text and extract `brand`, `model_code`, `product_name`, `region`.

2. Internal DB first (fast path)
- Check existing warranty records for same brand + model/product.
- If found, use stored terms and avoid web search.

3. Terms cache fallback
- Check `WarrantyTermsCacheDB` for fresh terms by brand/category/region.
- If found, return cached terms.

4. Strict domain preflight (new)
- Build candidate domains for brand:
  - verified domains first (`data/oem_verified.json`)
  - then official OEM domains (`data/oem_domains.json`)
- Run DNS + HTTPS reachability checks.
- In strict mode, if no alive domain is found, skip external search calls.

5. Search queries
- Run `site:domain` queries on preflight-alive domains.
- Use provider order from `TERMS_SEARCH_AUTO_ORDER`.
- Broad (non-site) queries run only when explicitly allowed.

6. Parse + persist
- Parse HTML/PDF terms.
- Extract `duration_months`, `terms`, `exclusions`, `claim_steps`.
- Store source URL + raw text in cache and update warranty summary.

## New Strict Controls

- `TERMS_PREFLIGHT_STRICT=true`
  - Skip provider calls if no domain passes preflight.
- `TERMS_PREFLIGHT_MAX_DOMAINS=4`
  - Max domains to test per request.
- `TERMS_PREFLIGHT_TIMEOUT_SEC=4`
  - Timeout for DNS/HTTPS reachability checks.
- `TERMS_ALLOW_BROAD_FALLBACK=false`
  - Allow non-`site:` queries only when set `true`.

## Product List: Is It Required?

No, not required for lookup to work.

It is recommended because it improves OCR cleanup and query quality when model extraction is weak:
- Better brand normalization (`MI` -> `Xiaomi`)
- Better product labeling (`air fryer`, `water purifier`, `inverter AC`)
- Better query precision when model code is missing

Recommended source files:
- `data/domain_catalog_exhaustive_verified.json`
- `data/google_cse_seed_domains_top50_verified.txt`
- Optional: a curated product vocabulary list for OCR normalization.
