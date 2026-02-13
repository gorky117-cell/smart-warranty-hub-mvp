# Domain Catalogs (India, Verified)

This project now includes a broad, category-wise domain catalog for:
- Mobile phones and accessories
- TV / home theater
- Laptops / PC
- Home and kitchen appliances
- AC / air / water / cleaning
- Wearables / watches / glasses
- EV / automotive / batteries
- Retail and review sources (India)

## Files

- `data/domain_catalog_exhaustive_verified.json`
  - Category-wise domains
  - Only domains that passed verification are included
  - Includes `all_verified_domains` and generation metadata

- `data/domain_catalog_exhaustive_verify_report.json`
  - Full verification audit rows for each checked candidate
  - Contains per-domain DNS/HTTPS status and errors

- `data/google_cse_seed_domains_top50_verified.txt`
  - Balanced top-50 verified domains for Google CSE limits

- `data/google_cse_seed_domains.txt`
  - Previous top-40 CSE seed list

## Verification Rule

Domains are verified with:
- DNS resolution check
- HTTPS GET check (2xx / 3xx / 4xx treated as reachable)
- Retry attempts for transient failures

Only verified domains are included in `domain_catalog_exhaustive_verified.json`.

