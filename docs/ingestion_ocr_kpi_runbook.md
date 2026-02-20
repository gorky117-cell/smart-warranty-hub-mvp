# Ingestion + OCR (Step 1) KPI Runbook

## What is saved
- Dataset labels: `test_data/ingestion_ocr_50_labeled_pdf.csv`
- Synthetic PDF samples: `test_data/ingestion_ocr_samples_pdf/`
- Latest KPI report (after micro patch v2): `data/ingestion_eval_after_patch_v2_50_pdf.json`
- Previous KPI report (after patch v1): `data/ingestion_eval_after_patch_50_pdf.json`
- Baseline report (before patch): `data/ingestion_eval_current_50_pdf.json`

## How to run again
```bash
python scripts/eval_ingestion_ocr.py --csv test_data/ingestion_ocr_50_labeled_pdf.csv --out data/ingestion_eval_after_patch_v2_50_pdf.json
```

## Current KPI result (50 samples)
- OCR success: `100%`
- Brand F1: `1.00`
- Model code F1: `1.00`
- Purchase date F1: `1.00`
- Serial number F1: `1.00`
- Invoice number F1: `1.00`
- Coverage months F1: `1.00`
- Product category F1: `1.00`

## KPI in simple terms
- `OCR success`: out of all files, how many gave readable text.
- `Precision`: when system predicts a value, how often it is correct.
- `Recall`: out of all true values, how many system found.
- `F1`: balance score of precision + recall (1.0 is best).

## Micro patch done in this step
- Better invoice detection for noisy OCR like `Invo1ce`.
- Removed false extraction from non-warranty retail bills.
- Prevented invalid model token picks like `INVOICE` or `RETAIL`.
- Improved category logic to avoid false `ac` substring matches.
- Added OCR-variant model label handling (`Mode1`) for model extraction.
- Added practical category keywords for appliance/EV patterns used in invoices.
