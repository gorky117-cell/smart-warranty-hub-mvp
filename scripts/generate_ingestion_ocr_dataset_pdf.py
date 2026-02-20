"""Generate a labeled 50-sample synthetic PDF dataset for ingestion extraction.

This variant avoids local image OCR dependencies by embedding selectable PDF text.

Output:
  - test_data/ingestion_ocr_samples_pdf/*.pdf
  - test_data/ingestion_ocr_50_labeled_pdf.csv
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import fitz


OUT_DIR = Path("test_data") / "ingestion_ocr_samples_pdf"
CSV_OUT = Path("test_data") / "ingestion_ocr_50_labeled_pdf.csv"

FIELDNAMES = [
    "sample_id",
    "file_path",
    "case_type",
    "is_warranty_invoice",
    "brand",
    "model_code",
    "purchase_date",
    "serial_no",
    "invoice_no",
    "coverage_months",
    "product_category",
    "notes",
]

PRODUCTS = [
    ("Samsung", "Galaxy S24", "mobile"),
    ("Apple", "iPhone 15", "mobile"),
    ("LG", "OLED55C3", "electronics"),
    ("Sony", "BRAVIA-X90", "electronics"),
    ("Whirlpool", "WM-8KG-PRO", "appliance"),
    ("Bosch", "FR-320L-INV", "appliance"),
    ("Ather", "450X-BATT", "ev"),
    ("Tata", "NEXON-EV-BATT", "ev"),
]

NON_WARRANTY_MERCHANTS = [
    "Sweet Corner",
    "Fresh Grocery Mart",
    "City Bakery",
    "Veggie World",
    "Quick Snacks Point",
]


def _seed() -> None:
    random.seed(42)


def _date_for_index(index: int) -> date:
    return date(2025, 1, 1) + timedelta(days=index * 5)


def _invoice_no(prefix: str, index: int) -> str:
    return f"{prefix}-{2025 + (index % 2)}-{index:04d}"


def _serial(index: int) -> str:
    return f"SN{index:03d}X{1000 + index}"


def _to_noisy_line(line: str) -> str:
    text = line
    for a, b in [(":", " : "), ("Warranty", "Warr anty"), ("Invoice", "Invo1ce"), ("Model", "Mode1")]:
        text = text.replace(a, b)
    if random.random() < 0.4:
        text = text.replace(" ", "  ")
    return text


def _write_pdf(text_lines: list[str], path: Path, hard_ocr: bool = False) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4-ish
    y = 56
    for line in text_lines:
        line_to_write = _to_noisy_line(line) if hard_ocr else line
        page.insert_text((48, y), line_to_write, fontsize=11)
        y += 20
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()


def _normal_row(sample_id: str, index: int, hard_ocr: bool = False) -> dict[str, str]:
    brand, product_name, category = PRODUCTS[index % len(PRODUCTS)]
    model_code = f"{product_name[:6].upper().replace('-', '')}-{index:03d}"
    purchase_iso = _date_for_index(index).isoformat()
    invoice_no = _invoice_no("INV", index)
    serial_no = _serial(index)
    coverage = str(random.choice([12, 24, 36]))
    file_path = OUT_DIR / f"{sample_id}.pdf"

    image_date = _date_for_index(index).strftime("%d-%b-%Y")
    lines = [
        f"{brand} Authorized Store",
        "TAX INVOICE",
        f"Invoice No: {invoice_no}",
        f"Date: {image_date}",
        f"Product: {product_name}",
        f"Brand: {brand}",
        f"Model: {model_code}",
        f"Serial: {serial_no}",
        f"Warranty: {coverage} months manufacturer warranty",
        "Customer Copy",
    ]
    _write_pdf(lines, file_path, hard_ocr=hard_ocr)

    return {
        "sample_id": sample_id,
        "file_path": str(file_path).replace("\\", "/"),
        "case_type": "hard_ocr" if hard_ocr else "normal",
        "is_warranty_invoice": "1",
        "brand": brand,
        "model_code": model_code,
        "purchase_date": purchase_iso,
        "serial_no": serial_no,
        "invoice_no": invoice_no,
        "coverage_months": coverage,
        "product_category": category,
        "notes": "synthetic_warranty_invoice_pdf",
    }


def _non_warranty_row(sample_id: str, index: int) -> dict[str, str]:
    merchant = NON_WARRANTY_MERCHANTS[index % len(NON_WARRANTY_MERCHANTS)]
    bill_no = _invoice_no("BILL", 400 + index)
    bill_date = _date_for_index(60 + index).strftime("%d-%m-%Y")
    file_path = OUT_DIR / f"{sample_id}.pdf"
    lines = [
        merchant,
        "RETAIL BILL",
        f"Bill No: {bill_no}",
        f"Date: {bill_date}",
        "Items: sweets, snacks, grocery",
        "Qty: 5",
        "Total: 650",
        "Thank you, visit again",
    ]
    _write_pdf(lines, file_path, hard_ocr=False)
    return {
        "sample_id": sample_id,
        "file_path": str(file_path).replace("\\", "/"),
        "case_type": "non_warranty",
        "is_warranty_invoice": "0",
        "brand": "",
        "model_code": "",
        "purchase_date": "",
        "serial_no": "",
        "invoice_no": "",
        "coverage_months": "",
        "product_category": "",
        "notes": "synthetic_non_warranty_bill_pdf",
    }


def main() -> int:
    _seed()
    rows: list[dict[str, str]] = []

    for idx in range(1, 31):
        rows.append(_normal_row(f"S{idx:03d}", idx, hard_ocr=False))
    for idx in range(31, 41):
        rows.append(_normal_row(f"S{idx:03d}", idx, hard_ocr=True))
    for idx in range(41, 51):
        rows.append(_non_warranty_row(f"S{idx:03d}", idx))

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated pdf samples: {OUT_DIR}")
    print(f"Generated labels: {CSV_OUT}")
    print(f"Rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
