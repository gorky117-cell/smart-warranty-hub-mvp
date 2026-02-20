# Terms NLP Enrichment (Phase 3) Runbook

## What was implemented
- Deterministic parser remains primary in `app/services/warranty_parser.py`.
- Optional NLP enrichment (Mistral) is applied only for low-confidence parses.
- Enrichment merges missing fields without overriding deterministic duration when already present.
- Section normalization/dedup is applied for `terms`, `exclusions`, and `claim_steps`.

## Runtime controls
- `TERMS_NLP_ENRICH_ENABLED=1` enables fallback enrichment (default is enabled in code).
- `TERMS_NLP_ENRICH_ENABLED=0` disables enrichment fully.
- `TERMS_NLP_MIN_CONFIDENCE=0.45` (or higher) to control when enrichment is triggered.
- `TERMS_NLP_MAX_CHARS=3000` input cap for enrichment prompt.
- `MISTRAL_API_KEY` required for live enrichment.

## Saved artifacts
- KPI report: `data/terms_nlp_eval_50.json`
- Synthetic cases: `test_data/terms_nlp_cases_50.json`
- Synthetic sample HTML files: `test_data/terms_nlp_samples/`
- Evaluator script: `scripts/eval_terms_nlp_phase3.py`

## Re-run command
```bash
python scripts/eval_terms_nlp_phase3.py --rows 50 --out data/terms_nlp_eval_50.json --cases-out test_data/terms_nlp_cases_50.json --samples-dir test_data/terms_nlp_samples
```

## Current KPI result (50 cases)
- Duration exact match: `100%`
- Section completeness: `100%`
- Low-confidence enrich success: `100%`
- High-confidence skip-enrich: `100%`
- Deterministic duration preserved: `100%`
- Enrichment calls: `30` (expected: 20 low-confidence + 10 partial cases)

## Simple meaning
- Strong pages are parsed directly (fast and stable).
- Weak pages get NLP help.
- Existing reliable values are not overwritten.
