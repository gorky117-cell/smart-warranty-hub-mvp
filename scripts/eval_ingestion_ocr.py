"""Evaluate ingestion + OCR extraction KPIs from a labeled CSV dataset.

Usage:
  python scripts/eval_ingestion_ocr.py --csv test_data/ingestion_ocr_50_template.csv
  python scripts/eval_ingestion_ocr.py --csv <file> --base-dir . --out data/ingestion_eval.json
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath("."))

from app.services.ingestion import extract_product_fields  # noqa: E402
from app.services.ocr import extract_text  # noqa: E402


FIELDS = [
    "brand",
    "model_code",
    "purchase_date",
    "serial_no",
    "invoice_no",
    "coverage_months",
    "product_category",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate OCR + field extraction KPIs.")
    parser.add_argument("--csv", required=True, help="Path to labeled CSV file.")
    parser.add_argument("--base-dir", default=".", help="Base dir for relative file_path values.")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser.parse_args()


def _to_bool(value: str) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "y")


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return _normalize_text(raw)


def _normalize_field(field: str, value: str) -> str:
    if field == "purchase_date":
        return _normalize_date(value)
    if field == "coverage_months":
        val = str(value or "").strip()
        if not val:
            return ""
        try:
            return str(int(float(val)))
        except ValueError:
            return _normalize_text(val)
    return _normalize_text(value)


def _safe_percent(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 2)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def main() -> int:
    args = _parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        return 2

    base_dir = Path(args.base_dir).resolve()

    tp: Dict[str, int] = {f: 0 for f in FIELDS}
    fp: Dict[str, int] = {f: 0 for f in FIELDS}
    fn: Dict[str, int] = {f: 0 for f in FIELDS}
    latency_ms: List[float] = []

    total_rows = 0
    processed_rows = 0
    missing_files = 0
    ocr_success = 0
    ocr_empty = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            raw_path = str(row.get("file_path", "")).strip()
            if not raw_path:
                continue
            file_path = (base_dir / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path)
            if not file_path.exists():
                missing_files += 1
                continue

            start = time.perf_counter()
            text, ocr_err = extract_text(str(file_path))
            elapsed = (time.perf_counter() - start) * 1000.0
            latency_ms.append(elapsed)
            processed_rows += 1

            if text and str(text).strip():
                ocr_success += 1
            else:
                ocr_empty += 1

            fields: Dict[str, str] = {}
            if text:
                fields, _confidence, _alts = extract_product_fields(text)

            for field in FIELDS:
                exp = _normalize_field(field, str(row.get(field, "")))
                pred = _normalize_field(field, str(fields.get(field, "")))
                exp_present = bool(exp)
                pred_present = bool(pred)
                match = exp_present and pred_present and exp == pred
                if match:
                    tp[field] += 1
                elif pred_present:
                    fp[field] += 1
                if exp_present and not match:
                    fn[field] += 1

            if ocr_err and not text:
                print(f"WARN {row.get('sample_id', '')}: OCR error: {ocr_err}")

    metrics: Dict[str, Dict[str, float]] = {}
    for field in FIELDS:
        precision = tp[field] / (tp[field] + fp[field]) if (tp[field] + fp[field]) else 0.0
        recall = tp[field] / (tp[field] + fn[field]) if (tp[field] + fn[field]) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics[field] = {
            "tp": float(tp[field]),
            "fp": float(fp[field]),
            "fn": float(fn[field]),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    summary = {
        "dataset_rows": total_rows,
        "processed_rows": processed_rows,
        "missing_file_rows": missing_files,
        "ocr_success_rate_pct": _safe_percent(ocr_success, processed_rows),
        "ocr_empty_rate_pct": _safe_percent(ocr_empty, processed_rows),
        "latency_p50_ms": round(_percentile(latency_ms, 0.50), 2),
        "latency_p95_ms": round(_percentile(latency_ms, 0.95), 2),
        "field_metrics": metrics,
    }

    print("\n=== Ingestion + OCR KPI Summary ===")
    print(json.dumps(summary, indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nSaved report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
