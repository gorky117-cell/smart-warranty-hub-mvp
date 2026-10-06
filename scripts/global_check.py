"""Run 3 item 11: synthetic global test set (GLOBAL RULE) with a per-category and per-warranty-type report.

Synthetic data only (no real invoices). Products: 9 categories x 3 brands = 27. Each product gets a
marketplace invoice and a shop invoice, each as a text PDF, a scanned PDF (image only, no text layer) and a
phone photo (tilted, blurred JPEG): 162 documents. Every document goes through the app's own text reading
(`ocr.extract_text_with_meta`) and field extraction (`ingestion.extract_product_fields`); the checks are
brand, model, invoice number, purchase date, product type, short name and serial/IMEI.

Warranty types are checked with `warranty_card.detect_types` / `five_lines` on synthetic terms and invoices.

    python scripts/global_check.py            # all formats, writes docs/GLOBAL_CHECK.md
    python scripts/global_check.py --text-only
"""
from __future__ import annotations

import io
import re
import sys
import tempfile
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# category -> product line expected from the taxonomy
CATEGORIES = {
    "phone": "smartphone", "laptop": "laptop", "TV": "tv", "fridge": "fridge", "AC": "air_conditioner",
    "washing machine": "washing_machine", "geyser": "water_heater", "small appliance": "kitchen_appliance",
    "printer": "printer",
}
# (category, brand, marketplace title, shop item text, model printed, expected model, serial)
PRODUCTS = [
    ("phone", "Samsung", "Samsung Galaxy M17e 5G (Blitz Blue, 6GB RAM, 128GB Storage) | 50MP Camera", "Samsung Galaxy M17e 5G Mobile Phone SM-M175F", "SM-M175F", "SM-M175F", "352099001761481"),
    ("phone", "Xiaomi", "Redmi 13C (Starry Black, 4GB RAM, 128GB Storage)", "Redmi 13C Mobile Phone 4/128", None, "13C", "865432061234562"),
    ("phone", "Apple", "Apple iPhone 15 (128 GB) - Black", "Apple iPhone 15 128GB Black MTP03HN/A", "MTP03HN/A", "MTP03HN/A", "356789104512343"),
    ("laptop", "HP", "HP Laptop 15s, 12th Gen Intel Core i5-1235U, 16GB DDR4, 512GB SSD", "HP Laptop 15s-fq5111TU i5 16GB 512GB", "15s-fq5111TU", "15S-FQ5111TU", "5CD3141XYZ"),
    ("laptop", "Lenovo", "Lenovo IdeaPad Slim 3 Intel Core i5 12th Gen Laptop 82RK00VWIN", "Lenovo IdeaPad Slim 3 Laptop 82RK00VWIN", "82RK00VWIN", "82RK00VWIN", "PF4ABC12"),
    ("laptop", "Dell", "Dell Inspiron 3520 Laptop, Intel Core i3-1215U, 8GB, 512GB", "Dell Inspiron 3520 Laptop D560896WIN9B", "D560896WIN9B", "D560896WIN9B", "7XK2LM3"),
    ("TV", "Sony", "Sony Bravia 139 cm (55 inches) 4K Ultra HD Smart LED Google TV KD-55X74L (Black)", "Sony Bravia 55 inch LED TV KD-55X74L", "KD-55X74L", "KD-55X74L", "5012345A"),
    ("TV", "LG", "LG 108 cm (43 inches) 4K Ultra HD Smart LED TV 43UR7500PSC", "LG 43 inch Smart LED TV 43UR7500PSC", "43UR7500PSC", "43UR7500PSC", "308MAKH12345"),
    ("TV", "Samsung", "Samsung 80 cm (32 Inches) HD Smart LED TV UA32T4380AKXXL", "Samsung 32 inch Smart LED TV UA32T4380AKXXL", "UA32T4380AKXXL", "UA32T4380AKXXL", "0C1A3CBR12345X"),
    ("fridge", "LG", "LG 242 L 3 Star Frost-Free Smart Inverter Double Door Refrigerator (GL-T292RPZY, Dazzle Steel)", "LG Double Door Refrigerator GL-T292RPZY 242L", "GL-T292RPZY", "GL-T292RPZY", "407KRAB12345"),
    ("fridge", "Whirlpool", "Whirlpool 184 L 3 Star Direct-Cool Single Door Refrigerator (205 WDE CLS 3S)", "Whirlpool Single Door Refrigerator 205 WDE CLS 3S", None, None, "WRF1234567"),
    ("fridge", "Godrej", "Godrej 236 L 2 Star Inverter Frost Free Double Door Refrigerator RF EON 236B", "Godrej Double Door Refrigerator RF EON 236B", None, None, "GDJ12345678"),
    ("AC", "Voltas", "Voltas 1.5 Ton 3 Star Inverter Split AC (Copper, 183V Vectra Elite, White)", "Voltas 1.5 Ton Inverter Split AC 183V Vectra Elite", "183V", None, "VOL183V12345"),
    ("AC", "Daikin", "Daikin 1.5 Ton 3 Star Inverter Split AC (Copper, FTKL50U)", "Daikin 1.5 Ton Inverter Split AC FTKL50U", "FTKL50U", "FTKL50U", "E012345"),
    ("AC", "LG", "LG 1.5 Ton 5 Star AI DUAL Inverter Split AC (Copper, TS-Q19YNZE)", "LG 1.5 Ton Dual Inverter Split AC TS-Q19YNZE", "TS-Q19YNZE", "TS-Q19YNZE", "312TKAB45678"),
    ("washing machine", "IFB", "IFB 7 Kg 5 Star Front Load Washing Machine (Senator WXS, Silver)", "IFB Front Load Washing Machine Senator WXS 7kg", None, None, "IFB2023A12345"),
    ("washing machine", "Bosch", "Bosch 7 kg 5 Star Inverter Front Load Washing Machine WAJ2416WIN", "Bosch Front Load Washing Machine WAJ2416WIN", "WAJ2416WIN", "WAJ2416WIN", "FD9912345"),
    ("washing machine", "Samsung", "Samsung 7 kg 5 star Fully-Automatic Top Load Washing Machine WA70BG4542BD", "Samsung Top Load Washing Machine WA70BG4542BD", "WA70BG4542BD", "WA70BG4542BD", "0LKX5ABC12345"),
    ("geyser", "Racold", "Racold Eterno Pro 25L Vertical Storage Water Heater (Geyser)", "Racold Eterno Pro 25L Water Heater Geyser", None, None, "RC25L123456"),
    ("geyser", "AO Smith", "AO Smith HSE-VAS-X-015 Storage 15 Litre Vertical Water Heater (Geyser)", "AO Smith Water Heater Geyser HSE-VAS-X-015 15L", "HSE-VAS-X-015", "HSE-VAS-X-015", "AOS12345678"),
    ("geyser", "Havells", "Havells Monza EC 15L Storage Water Heater Geyser", "Havells Monza EC 15L Water Heater Geyser GHWAMECWH015", "GHWAMECWH015", "GHWAMECWH015", "HV12345678"),
    ("small appliance", "Bajaj", "Bajaj GX 3701 750W Mixer Grinder with 3 Jars (White)", "Bajaj Mixer Grinder GX 3701 750W", "GX 3701", None, None),
    ("small appliance", "Philips", "Philips HL7756/00 Mixer Grinder, 750W, 3 Jars (Black)", "Philips Mixer Grinder HL7756/00 750W", "HL7756/00", "HL7756/00", None),
    ("small appliance", "Prestige", "Prestige Iris 750 Watt Mixer Grinder with 4 Jars", "Prestige Iris 750W Mixer Grinder 41382", "41382", None, None),
    ("printer", "Epson", "Epson EcoTank L3250 A4 Wi-Fi All-in-One Ink Tank Printer", "Epson EcoTank L3250 Printer", "L3250", "L3250", "XAHT699208"),
    ("printer", "HP", "HP Smart Tank 580 All-in-One WiFi Colour Printer 1F3Y2A", "HP Smart Tank 580 Printer 1F3Y2A", "1F3Y2A", "1F3Y2A", "CN12345678"),
    ("printer", "Canon", "Canon PIXMA MegaTank G3010 All-in-One Wireless Ink Tank Colour Printer", "Canon PIXMA G3010 Ink Tank Printer", "G3010", "G3010", "KMFA12345"),
]
SELLERS = ["Appario Retail Private Ltd", "Darshita Etel Private Limited", "RetailNet", "Cloudtail India Pvt Ltd"]
SHOPS = ["Vijay Sales", "Poorvika Mobiles Pvt Ltd", "Sharma Electronics", "Reliance Digital Retail Ltd", "Croma - Infiniti Retail Ltd"]


def invoices_for(i: int, product) -> dict:
    category, brand, title, shop_item, _model, _exp_model, serial = product
    bought = date(2025, 1 + i % 12, 1 + (i * 3) % 27)
    serial_line = (f"IMEI: {serial}" if category == "phone" else f"Serial No: {serial}") if serial else ""
    inv_m = f"BLR{7 + i % 3}-{1000000 + i * 7919}"
    marketplace = "\n".join(x for x in [
        "Tax Invoice/Bill of Supply/Cash Memo",
        "(Original for Recipient)",
        "Sold By :",
        SELLERS[i % len(SELLERS)],
        "Plot No 12, Industrial Area, Bengaluru, Karnataka, 560067",
        "GST Registration No: 29AAHCD1234E1Z5",
        f"Order Number: 408-{1000000 + i}-{8000000 + i}",
        f"Order Date: {bought.strftime('%d.%m.%Y')}",
        f"Invoice Number : {inv_m}",
        f"Invoice Date : {bought.strftime('%d.%m.%Y')}",
        "Sl. Description Unit Price Qty Net Amount",
        f"1 {title} | B0CMTVYV{i:02d} ( X0011PGZ{i:02d} )",
        "HSN:85171300",
        serial_line,
        "1 Rs.24,999.00",
    ] if x)
    inv_s = f"SH/{bought.year}/{4500 + i}"
    shop = "\n".join(x for x in [
        SHOPS[i % len(SHOPS)].upper(),
        "MG Road, Pune 411001   Ph: 020-2612345",
        "GSTIN: 27ABCDE1234F1Z5",
        f"Bill No: {inv_s}    Date: {bought.strftime('%d/%m/%Y')}",
        "Sl  Item                                   Qty   Amount",
        f"1   {shop_item}   1   24999.00",
        serial_line,
        "Total: 24999.00",
        "Warranty as per manufacturer terms",
    ] if x)
    return {"marketplace": (marketplace, inv_m, bought), "shop": (shop, inv_s, bought)}


# --- documents ----------------------------------------------------------------------------------------------

def text_pdf(text: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for line in text.splitlines():
        pdf.cell(0, 6, text=line.encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _image(text: str, photo: bool):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    lines = text.splitlines()
    font = ImageFont.load_default(size=30)
    image = Image.new("RGB", (1700, 60 + 46 * len(lines)), (238, 236, 230) if photo else "white")
    draw = ImageDraw.Draw(image)
    for n, line in enumerate(lines):
        draw.text((40, 30 + 46 * n), line, fill=(30, 30, 30), font=font)
    if photo:
        image = image.rotate(1.2, expand=True, fillcolor=(210, 208, 200)).filter(ImageFilter.GaussianBlur(0.7))
    return image


def scanned_pdf(text: str) -> bytes:
    import fitz

    buf = io.BytesIO()
    _image(text, photo=False).save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(20, 20, 575, 822), stream=buf.getvalue(), keep_proportion=True)
    return doc.tobytes()


def phone_photo(text: str) -> bytes:
    buf = io.BytesIO()
    _image(text, photo=True).save(buf, format="JPEG", quality=70)
    return buf.getvalue()


FORMATS = {"text PDF": (".pdf", text_pdf), "scanned PDF": (".pdf", scanned_pdf), "phone photo": (".jpg", phone_photo)}


# --- checks --------------------------------------------------------------------------------------------------

def _norm(code) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def _is_spec(code) -> bool:
    """A value that is a size, capacity or processor rather than a model ("I5-1235U", "EC15L", "750W")."""
    value = str(code or "").upper()
    return bool(value) and bool(re.fullmatch(r"I[3579]-?\d{4,5}[A-Z]{0,2}|[A-Z]{0,3}\d+(?:\.\d+)?(?:L|KG|W|GB|TB|MAH|V|HZ)", value))


def check_document(product, kind: str, text: str, invoice_no: str, bought: date, ocr_meta=None) -> dict:
    from app.services.ingestion import extract_product_fields, from_ocr, is_listing_code, route_confusable_codes
    from app.services.product_naming import short_name
    from app.services.terms_cache import product_line

    category, brand, title, shop_item, _printed, expected_model, serial = product
    # A model code is expected only where this invoice prints it; otherwise any non-listing, non-spec value
    # (or none) passes.
    printed = title if kind == "marketplace" else shop_item
    if expected_model and _norm(expected_model) not in _norm(printed):
        expected_model = None
    fields, conf, alts = extract_product_fields(text or "")
    # As the pipeline does: codes from a scan or photo with O/0, I/1, S/5, B/8 become "please confirm".
    fields, conf, alts = route_confusable_codes(fields, conf, alts, ocr=from_ocr(ocr_meta))
    model = fields.get("model_code")
    line = product_line(model, fields.get("product_name"))
    name = short_name(fields.get("brand"), fields.get("product_name"), model)
    serial_value = fields.get("serial_no") or (alts.get("serial_suggestion") or {}).get("value")
    results = {
        "brand": fields.get("brand") == brand,
        # Pass = stored right, or not stored and offered to confirm; stored wrong = fail.
        "model": (not is_listing_code(model)) and not _is_spec(model)
        and ((_norm(expected_model) in _norm(model)) if (expected_model and model)
             else (not expected_model or (alts.get("model_suggestion") or {}).get("status") == "pending")),
        "invoice number": fields.get("invoice_no") == invoice_no.upper(),
        "purchase date": fields.get("purchase_date") == bought.isoformat(),
        "product type": line == CATEGORIES[category],
        "short name": bool(name) and brand.split()[0].lower() in name.lower() and "wty_" not in name,
        "serial": ((fields.get("serial_no") == serial) if fields.get("serial_no")
                   else (alts.get("serial_suggestion") or {}).get("status") == "pending") if serial else True,
    }
    confirm = {f: (alts.get(f"{f}_suggestion") or {}).get("status") == "pending" for f in ("model", "serial")}
    stored_wrong = {
        "model": bool(expected_model and model and _norm(expected_model) not in _norm(model)),
        "serial": bool(serial and fields.get("serial_no") and fields.get("serial_no") != serial),
    }
    return {"results": results, "fields": fields, "name": name, "line": line, "confirm": confirm,
            "stored_wrong": stored_wrong}


def run_documents(formats) -> list:
    from app.services.ocr import extract_text_with_meta

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, product in enumerate(PRODUCTS):
            for style, (text, invoice_no, bought) in invoices_for(i, product).items():
                for fmt in formats:
                    suffix, make = FORMATS[fmt]
                    path = Path(tmp) / f"doc_{i}_{style}_{fmt.replace(' ', '_')}{suffix}"
                    path.write_bytes(make(text))
                    read, err, meta = extract_text_with_meta(str(path))
                    check = check_document(product, style, read or "", invoice_no, bought, ocr_meta=meta)
                    rows.append({"category": product[0], "brand": product[1], "style": style, "format": fmt,
                                 "engine": (meta or {}).get("engine"), **check})
    return rows


# --- warranty types -------------------------------------------------------------------------------------------

def _w(**kw):
    base = dict(id="wty_gc", brand="LG", product_name="LG Double Door Refrigerator", model_code="GL-T292RPZY", serial_no="",
                purchase_date=datetime(2026, 1, 10), coverage_months=12, expiry_date=None, alternatives={},
                terms=["LG warrants the product against manufacturing defects for 12 months from purchase."],
                exclusions=["Damage due to voltage fluctuation is not covered."],
                claim_steps=["Repairs are carried out at an LG authorized service center."])
    base.update(kw)
    return SimpleNamespace(**base)


TODAY = date(2026, 10, 5)
WARRANTY_TYPES = [
    # (type, product, how it is given, check)
    ("standard", "fridge", dict(), lambda c: c["lines"][0]["text"].startswith("Covered until 10 Jan 2027") and not c["extras"]),
    ("part periods (compressor)", "fridge", dict(terms=["1 year comprehensive warranty.", "The compressor is covered for 10 years."]),
     lambda c: any(x["text"] == "Compressor: 10 years" for x in c["extras"])),
    ("part periods (accessories)", "phone", dict(brand="Samsung", product_name="Galaxy M17e", model_code="SM-M175F",
                                                 terms=["Accessories such as the charger are covered for 6 months."]),
     lambda c: any(x["text"] == "Accessories: 6 months" for x in c["extras"])),
    ("extended plan shown separately", "laptop", dict(brand="HP", product_name="HP Laptop 15s", model_code="15s-fq5111TU",
                                                      invoice="1 HP Laptop 15s\n2 HP Care Pack Extended Warranty 2 Years 3,499.00"),
     lambda c: c["lines"][0]["text"].startswith("Covered until 10 Jan 2027") and any(x["type"] == "extended_plan" for x in c["extras"])),
    ("pro-rata", "inverter battery", dict(brand="Luminous", product_name="Luminous Inverter Battery", model_code="RC18000",
                                          terms=["Warranty: 36 months (18 months free replacement + 18 months pro-rata)."]),
     lambda c: any(x["type"] == "pro_rata" for x in c["extras"])),
    ("starts at installation", "AC", dict(brand="Voltas", product_name="Voltas Split AC", model_code="183V",
                                         terms=["The warranty period starts from the date of installation."]),
     lambda c: "please confirm the installation date" in c["lines"][0]["text"] and c["lines"][0]["confirm"]),
    ("starts at purchase", "TV", dict(brand="Sony", product_name="Bravia TV", model_code="KD-55X74L",
                                      terms=["Warranty is valid for 12 months from the date of purchase."]),
     lambda c: "installation" not in c["lines"][0]["text"]),
    ("registration required", "water purifier", dict(brand="Kent", product_name="Kent RO Water Purifier", model_code="Grand Plus",
                                                     terms=["Product registration within 30 days is mandatory to avail the warranty."]),
     lambda c: any(x["type"] == "registration_required" for x in c["extras"])),
    ("on-site", "washing machine", dict(brand="IFB", product_name="IFB Front Load Washing Machine", model_code="Senator WXS",
                                        terms=["Service will be provided at your home by an authorized technician."]),
     lambda c: any(x["type"] == "on_site" for x in c["extras"])),
    ("carry-in", "phone", dict(brand="Xiaomi", product_name="Redmi 13C", model_code="13C",
                               claim_steps=["Carry-in warranty: bring the product to the nearest service centre."]),
     lambda c: c["lines"][3]["text"].startswith("If it breaks: Carry-in warranty")),
    ("seller warranty vs brand warranty", "small appliance", dict(brand="Bajaj", product_name="Bajaj Mixer Grinder", model_code="GX 3701",
                                                                  invoice="Warranty provided by the seller: 6 months shop warranty"),
     lambda c: any(x["type"] == "seller_warranty" for x in c["extras"])),
    ("no warranty", "printer", dict(brand="Epson", product_name="Epson L3250 Printer", model_code="L3250", coverage_months=None,
                                    invoice="Item sold as is. No warranty."),
     lambda c: c["lines"][0]["text"] == "Your invoice says there is no warranty for this product."),
    ("refurbished", "phone", dict(brand="Apple", product_name="Apple iPhone 12 (Renewed)", model_code="MGJ53HN/A",
                                  invoice="Apple iPhone 12 (Renewed) 64GB - seller warranty 6 months"),
     lambda c: any(x["type"] == "refurbished" for x in c["extras"])),
    ("international", "camera", dict(brand="Canon", product_name="Canon EOS 1500D Camera", model_code="EOS 1500D",
                                     invoice="Canon EOS 1500D - International warranty card included"),
     lambda c: any(x["type"] == "international" for x in c["extras"])),
    ("unknown brand -> Estimated, please check", "small appliance",
     dict(brand=None, product_name="Zyxor Mixer Grinder", model_code="ZX-500", evidence={"status": "estimated"}),
     lambda c: c["estimated"] and c["lines"][1].get("tag") == "Estimated, please check"),
]


def run_warranty_types() -> list:
    from app.services.ingestion import extract_product_fields
    from app.services.warranty_card import five_lines

    rows = []
    for kind, product, given, check in WARRANTY_TYPES:
        given = dict(given)
        invoice = given.pop("invoice", "")
        evidence = given.pop("evidence", {"status": "confirmed"})
        card = five_lines(_w(**given), evidence, None, invoice_text=invoice, today=TODAY)
        ok = bool(check(card))
        rows.append({"type": kind, "product": product, "ok": ok, "card": card})
    # Unknown brand on a real invoice text: never stored as a brand, only offered to confirm.
    fields, _c, alts = extract_product_fields("Sharma Electronics\nBill No: SH/2026/12  Date: 01/02/2026\n1 Zyxor Mixer Grinder ZX-500 750W 1 2499.00")
    rows.append({"type": "unknown brand on the invoice is not guessed", "product": "small appliance",
                 "ok": "brand" not in fields, "card": {"suggestion": alts.get("brand_suggestion")}})
    return rows


def report(doc_rows: list, type_rows: list, seconds: float) -> str:
    checks = list(doc_rows[0]["results"]) if doc_rows else []
    out = ["# Global check (run 3, item 11)", "",
           f"Synthetic data only. {len(PRODUCTS)} products ({len(CATEGORIES)} categories x 3 brands), "
           f"{len(doc_rows)} documents, {len(type_rows)} warranty-type cases. Measured {date.today().isoformat()} in "
           f"{seconds:.0f} s with `python scripts/global_check.py`.", ""]

    def table(title, key):
        groups = defaultdict(list)
        for row in doc_rows:
            groups[row[key]].append(row)
        out.extend([f"## By {title}", "", f"| {title} | docs | " + " | ".join(checks) + " | all checks |",
                    "|---|---|" + "---|" * (len(checks) + 1)])
        for name, rows in groups.items():
            cells = [f"{sum(r['results'][c] for r in rows)}/{len(rows)}" for c in checks]
            whole = sum(all(r["results"].values()) for r in rows)
            out.append(f"| {name} | {len(rows)} | " + " | ".join(cells) + f" | {whole}/{len(rows)} |")
        out.append("")

    for title, key in (("category", "category"), ("brand", "brand"), ("invoice type", "style"), ("format", "format")):
        table(title, key)
    out.extend(["## Warranty types", "", "| type | product | result |", "|---|---|---|"])
    for row in type_rows:
        out.append(f"| {row['type']} | {row['product']} | {'pass' if row['ok'] else 'FAIL'} |")
    out.extend(["", "## Codes: stored wrong vs offered to confirm (by format)", "",
                "| format | model stored wrong | model offered to confirm | serial stored wrong | serial offered to confirm |",
                "|---|---|---|---|---|"])
    for fmt in dict.fromkeys(r["format"] for r in doc_rows):
        rows = [r for r in doc_rows if r["format"] == fmt]
        out.append(f"| {fmt} | {sum(r['stored_wrong']['model'] for r in rows)} | {sum(r['confirm']['model'] for r in rows)} | "
                   f"{sum(r['stored_wrong']['serial'] for r in rows)} | {sum(r['confirm']['serial'] for r in rows)} |")
    failures = [r for r in doc_rows if not all(r["results"].values())]
    out.extend(["", f"## Failed documents ({len(failures)})", ""])
    for r in failures:
        bad = [c for c, ok in r["results"].items() if not ok]
        f = r["fields"]
        out.append(f"- {r['category']} / {r['brand']} / {r['style']} / {r['format']}: {', '.join(bad)} "
                   f"(read brand={f.get('brand')!r}, model={f.get('model_code')!r}, invoice={f.get('invoice_no')!r}, "
                   f"date={f.get('purchase_date')!r}, type={r['line']!r}, serial={f.get('serial_no')!r})")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    formats = ["text PDF"] if "--text-only" in argv else list(FORMATS)
    start = time.time()
    doc_rows = run_documents(formats)
    type_rows = run_warranty_types()
    text = report(doc_rows, type_rows, time.time() - start)
    out = ROOT / "docs" / "GLOBAL_CHECK.md"
    if "--no-write" not in argv:
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
