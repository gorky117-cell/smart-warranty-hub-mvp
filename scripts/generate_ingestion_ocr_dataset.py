"""Generate a labeled 50-sample synthetic dataset for ingestion + OCR evaluation.

Output:
  - test_data/ingestion_ocr_samples/*.png
  - test_data/ingestion_ocr_50_labeled.csv
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


OUT_DIR = Path("test_data") / "ingestion_ocr_samples"
CSV_OUT = Path("test_data") / "ingestion_ocr_50_labeled.csv"

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


def _draw_invoice_image(text_lines: list[str], path: Path, hard_ocr: bool = False) -> None:
    width, height = 1400, 1000
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    y = 40
    for line in text_lines:
        draw.text((40, y), line, fill=(20, 20, 20), font=font)
        y += 28

    if hard_ocr:
        img = ImageEnhance.Contrast(img).enhance(0.75)
        img = ImageEnhance.Brightness(img).enhance(0.9)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
        angle = random.choice([-3.0, -2.0, 2.0, 3.0])
        img = img.rotate(angle, expand=True, fillcolor=(255, 255, 255))
        # center crop/pad back to standard size
        canvas = Image.new("RGB", (width, height), color=(255, 255, 255))
        paste_x = max(0, (width - img.width) // 2)
        paste_y = max(0, (height - img.height) // 2)
        canvas.paste(img, (paste_x, paste_y))
        img = canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _normal_row(sample_id: str, index: int, hard_ocr: bool = False) -> dict[str, str]:
    brand, product_name, category = PRODUCTS[index % len(PRODUCTS)]
    model_code = f"{product_name[:6].upper().replace('-', '')}-{index:03d}"
    purchase = _date_for_index(index).isoformat()
    invoice_no = _invoice_no("INV", index)
    serial_no = _serial(index)
    coverage = str(random.choice([12, 24, 36]))

    img_path = OUT_DIR / f"{sample_id}.png"
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
    _draw_invoice_image(lines, img_path, hard_ocr=hard_ocr)

    return {
        "sample_id": sample_id,
        "file_path": str(img_path).replace("\\", "/"),
        "case_type": "hard_ocr" if hard_ocr else "normal",
        "is_warranty_invoice": "1",
        "brand": brand,
        "model_code": model_code,
        "purchase_date": purchase,
        "serial_no": serial_no,
        "invoice_no": invoice_no,
        "coverage_months": coverage,
        "product_category": category,
        "notes": "synthetic_warranty_invoice",
    }


def _non_warranty_row(sample_id: str, index: int) -> dict[str, str]:
    merchant = NON_WARRANTY_MERCHANTS[index % len(NON_WARRANTY_MERCHANTS)]
    invoice_no = _invoice_no("BILL", 400 + index)
    purchase = _date_for_index(60 + index).strftime("%d-%m-%Y")
    img_path = OUT_DIR / f"{sample_id}.png"
    lines = [
        merchant,
        "RETAIL BILL",
        f"Bill No: {invoice_no}",
        f"Date: {purchase}",
        "Items: sweets, snacks, grocery",
        "Qty: 5",
        "Total: 650",
        "Thank you, visit again",
    ]
    _draw_invoice_image(lines, img_path, hard_ocr=False)

    return {
        "sample_id": sample_id,
        "file_path": str(img_path).replace("\\", "/"),
        "case_type": "non_warranty",
        "is_warranty_invoice": "0",
        "brand": "",
        "model_code": "",
        "purchase_date": "",
        "serial_no": "",
        "invoice_no": "",
        "coverage_months": "",
        "product_category": "",
        "notes": "synthetic_non_warranty_bill",
    }


def main() -> int:
    _seed()
    rows: list[dict[str, str]] = []

    # 30 normal samples
    for idx in range(1, 31):
        sample_id = f"S{idx:03d}"
        rows.append(_normal_row(sample_id, idx, hard_ocr=False))

    # 10 hard OCR samples
    for idx in range(31, 41):
        sample_id = f"S{idx:03d}"
        rows.append(_normal_row(sample_id, idx, hard_ocr=True))

    # 10 non-warranty samples
    for idx in range(41, 51):
        sample_id = f"S{idx:03d}"
        rows.append(_non_warranty_row(sample_id, idx))

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated images: {OUT_DIR}")
    print(f"Generated labels: {CSV_OUT}")
    print(f"Rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
