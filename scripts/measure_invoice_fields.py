"""Measure invoice field accuracy with real image OCR on the labelled 50-sample set.

Runs the same extraction the invoice pipeline runs on an uploaded image:
``extract_text_with_meta()`` (configured engine, Tesseract fallback) then ``extract_product_fields()``
(which already applies ``sanitize_invoice_identity_fields``). Optional AI enrichment is not used.

Each labelled field is scored exact-match after normalisation (case/whitespace; dates to ISO) as
correct, wrong (a different value was stored) or missing (blank). Samples are synthetic.

Usage:
    python scripts/measure_invoice_fields.py [--csv test_data/ingestion_ocr_50_labeled.csv]
        [--text-cache tests/fixtures/ocr_text_50.json] [--from-cache] [--out report.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ingestion import extract_product_fields, from_ocr, parse_date_from_text, route_confusable_codes  # noqa: E402

FIELDS = ("brand", "model_code", "purchase_date", "serial_no", "invoice_no", "coverage_months", "product_category")


def _norm(field: str, value: Optional[str]) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if field == "purchase_date" and text:
        return parse_date_from_text(text) or text
    return text


def ocr_texts(rows: List[Dict[str, str]], base: Path) -> Dict[str, Dict[str, object]]:
    from app.services.ocr import extract_text_with_meta

    out: Dict[str, Dict[str, object]] = {}
    for row in rows:
        text, err, meta = extract_text_with_meta(str(base / row["file_path"]))
        out[row["sample_id"]] = {"text": text, "error": err, "method": meta.get("method"), "engine": meta.get("engine")}
    return out


def score(rows: List[Dict[str, str]], texts: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    groups: Dict[str, Dict[str, Counter]] = {}
    false_positives: Counter = Counter()
    empty_text: Counter = Counter()
    engines: Counter = Counter()
    for row in rows:
        entry = texts[row["sample_id"]]
        engines[f"{entry.get('method')}/{entry.get('engine')}"] += 1
        text = entry.get("text") or ""
        if not text:
            empty_text[row["case_type"]] += 1
        fields, confidence, alt = extract_product_fields(text)
        # As the upload pipeline does: a code read from a scan or photo with O/0, I/1, S/5, B/8 is asked, not stored.
        fields, confidence, alt = route_confusable_codes(fields, confidence, alt, ocr=from_ocr({"method": entry.get("method")}))
        suggestions = {
            field: (alt or {}).get(key)
            for field, key in (("serial_no", "serial_suggestion"), ("brand", "brand_suggestion"), ("model_code", "model_suggestion"))
        }
        if row["case_type"] == "non_warranty":
            for field in FIELDS:
                if fields.get(field):
                    false_positives[field] += 1
            continue
        group = groups.setdefault(row["case_type"], {field: Counter() for field in FIELDS})
        for field in FIELDS:
            truth = _norm(field, row.get(field))
            if not truth:
                continue
            got = _norm(field, fields.get(field))
            outcome = "correct" if got == truth else ("missing" if not got else "wrong")
            group[field][outcome] += 1
            if field == "serial_no" and got == "takinvoice":
                group[field]["takinvoice"] += 1
            suggestion = suggestions.get(field)
            if suggestion:
                exact = _norm(field, suggestion.get("value")) == truth
                group[field]["suggestion_exact" if exact else "suggestion_needs_edit"] += 1
    return {
        "samples": len(rows),
        "engines": dict(engines),
        "empty_text_by_case": dict(empty_text),
        "fields_by_case": {case: {f: dict(c) for f, c in g.items()} for case, g in groups.items()},
        "non_warranty_false_positive_fields": dict(false_positives),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", default="test_data/ingestion_ocr_50_labeled.csv")
    parser.add_argument("--text-cache", default=None, help="Write (or with --from-cache read) OCR text JSON here")
    parser.add_argument("--from-cache", action="store_true", help="Score cached OCR text instead of running OCR")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows = list(csv.DictReader(open(ROOT / args.csv, encoding="utf-8")))
    if args.from_cache:
        texts = json.loads(Path(args.text_cache).read_text(encoding="utf-8"))["samples"]
    else:
        texts = ocr_texts(rows, ROOT)
        if args.text_cache:
            Path(args.text_cache).write_text(
                json.dumps({"_note": f"OCR text for {args.csv}; synthetic images.", "samples": texts}, indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
    report = score(rows, texts)
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
