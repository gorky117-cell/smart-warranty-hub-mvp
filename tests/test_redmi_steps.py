"""Run 3 item 3 (Redmi live test, steps B-D), tested on a mix of brands, products and invoice types."""

import io
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF

from app.db import SessionLocal
from app.db_models import DocumentDB, UserDB, WarrantyDB, WarrantyOwnerDB
from app.deps import hash_password
from app.main import app
from app.services import combined_export, customer_content
from app.services.ingestion import extract_product_fields, is_listing_code, luhn_ok
from app.services.warranty_status import compute_warranty_status

AMAZON = """Tax Invoice/Bill of Supply/Cash Memo
(Original for Recipient)
Sold By :
{seller}
Plot No 12, Bengaluru, Karnataka, 560067
Order Number: 408-1234567-8901234
Order Date: 12.03.2024
Invoice Number : BLR7-1234567
Invoice Date : 12.03.2024
Sl. Description Unit Price Qty Net Amount
1 {item} | {asin} ( X0011PGZX7 )
HSN:85171300
{serial_line}
8,999.00 1 8,999.00
"""
FLIPKART = """Tax Invoice
Sold By: {seller}
Order ID: OD430012345678901234
Invoice Number # FAEB2X0123456789
Invoice Date: 05-01-2025
Product Title
{item} FSN: MOBGTAGPAQNVFZZY
{serial_line}
"""
SHOP = """{seller}
INVOICE NO: SHOP/2023/45678   Date: 05/01/2023
Item: {item}
{serial_line}
Total 24999
"""


# --- B: brand from the title, never the seller ---------------------------------------------------------------

@pytest.mark.parametrize("template,seller,item,brand", [
    (AMAZON, "Darshita Etel Private Limited", "Redmi 13C (Starry Black, 4GB RAM, 128GB Storage)", "Xiaomi"),
    (AMAZON, "Appario Retail Private Ltd", "Samsung Galaxy M17e 5G (Blitz Blue, 6GB RAM)", "Samsung"),
    (FLIPKART, "SuperComNet", "POCO X6 Pro 5G (Racing Grey, 256 GB)", "Xiaomi"),
    (FLIPKART, "RetailNet", "LG 242 L 3 Star Frost-Free Double Door Refrigerator", "LG"),
    (SHOP, "POORVIKA MOBILES PVT LTD", "Redmi Note 12 Pro 5G 8/256 Onyx Black", "Xiaomi"),
    (SHOP, "Croma - Infiniti Retail Ltd", "Voltas 1.5 Ton 3 Star Inverter Split AC", "Voltas"),
])
def test_brand_comes_from_the_product_title_not_the_seller(template, seller, item, brand):
    text = template.format(seller=seller, item=item, asin="B0CMTVYVRS", serial_line="")
    fields, _c, alts = extract_product_fields(text)
    assert fields.get("brand") == brand
    assert brand.lower() not in seller.lower()  # the seller never became the brand


def test_redmi_note_keeps_its_series_name():
    fields, _c, _a = extract_product_fields(SHOP.format(seller="Poorvika Mobiles Pvt Ltd", item="Redmi Note 12 Pro 5G 8/256", serial_line=""))
    assert fields["model_code"] == "NOTE 12 PRO"


# --- B: marketplace codes are never a model -----------------------------------------------------------------

@pytest.mark.parametrize("code,listing", [
    ("X0011PGZX7", True), ("B0CMTVYVRS", True), ("MOBGTAGPAQNVFZZY", True),
    ("SM-M175F", False), ("GL-T292RPZY", False), ("KD-55X74L", False), ("L3250", False), ("HL7756/00", False),
])
def test_listing_codes(code, listing):
    assert is_listing_code(code) is listing


@pytest.mark.parametrize("template,item", [
    (AMAZON, "Redmi 13C (Starry Black, 4GB RAM)"),
    (AMAZON, "Philips Hair Dryer"),
    (FLIPKART, "Epson EcoTank Printer"),
])
def test_marketplace_codes_never_stored_as_model(template, item):
    fields, _c, alts = extract_product_fields(template.format(seller="Shop Pvt Ltd", item=item, asin="B0CMTVYVRS", serial_line=""))
    assert not is_listing_code(fields.get("model_code"))
    assert not is_listing_code((alts.get("model_suggestion") or {}).get("value"))


# --- C: IMEI with the Luhn check -----------------------------------------------------------------------------

def test_luhn():
    assert luhn_ok("352099001761481") and not luhn_ok("352099001761482")


@pytest.mark.parametrize("serial_line,stored,evidence", [
    ("IMEI 1: 352099001761481", "352099001761481", None),          # whole IMEI, valid
    ("IMEI/Serial No: 86543206 1234562", "865432061234562", "imei_repaired"),  # split by OCR, valid when joined
    ("IMEI: 8654 3206 1234 562", "865432061234562", "imei_repaired"),
])
def test_imei_stored_when_valid(serial_line, stored, evidence):
    fields, _c, alts = extract_product_fields(AMAZON.format(seller="Shop Pvt Ltd", item="Redmi 13C", asin="B0CMTVYVRS", serial_line=serial_line))
    assert fields.get("serial_no") == stored
    assert alts.get("serial_evidence") == evidence


@pytest.mark.parametrize("serial_line", ["IMEI/Serial No: 86543206 1234567", "IMEI 1: 352099001761482"])
def test_invalid_imei_is_only_a_suggestion(serial_line):
    fields, _c, alts = extract_product_fields(AMAZON.format(seller="Shop Pvt Ltd", item="Redmi 13C", asin="B0CMTVYVRS", serial_line=serial_line))
    assert "serial_no" not in fields
    assert "IMEI check" in alts["serial_suggestion"]["reason"]


def test_letter_serials_of_other_products_still_work():
    fields, _c, _a = extract_product_fields(SHOP.format(seller="Vijay Sales", item="LG Refrigerator GL-T292RPZY", serial_line="Serial No: 407KRAB12345"))
    assert fields["serial_no"] == "407KRAB12345"


# --- C: invoice number vs order ID ---------------------------------------------------------------------------

@pytest.mark.parametrize("template,invoice,order", [
    (AMAZON, "BLR7-1234567", "408-1234567-8901234"),
    (FLIPKART, "FAEB2X0123456789", "OD430012345678901234"),
    (SHOP, "SHOP/2023/45678", None),
])
def test_invoice_number_is_not_the_order_id(template, invoice, order):
    fields, _c, alts = extract_product_fields(template.format(seller="Shop Pvt Ltd", item="Redmi 13C", asin="B0CMTVYVRS", serial_line=""))
    assert fields.get("invoice_no") == invoice
    assert (alts.get("order_id") or [None])[0] == order


def test_order_id_alone_is_never_the_invoice_number():
    fields, _c, alts = extract_product_fields("Order ID: OD430012345678901234\nInvoice No: OD430012345678901234\nRedmi 13C phone")
    assert "invoice_no" not in fields and alts["order_id"] == ["OD430012345678901234"]


# --- D: expired warranty path --------------------------------------------------------------------------------

class _W:
    brand, serial_no = "Xiaomi", ""


def test_expired_says_expired_on_date_and_never_eligible():
    status = compute_warranty_status(purchase_date=datetime(2023, 1, 5), coverage_months=12, expiry_date=None, today=date(2026, 10, 5))
    worded = customer_content.claim_wording(status, _W())
    assert worded["claim_message"] == "Expired on 5 Jan 2024"
    assert worded["claim_eligibility"] == "expired" and "eligib" not in worded["claim_message"].lower()


def test_unknown_dates_ask_to_check():
    status = compute_warranty_status(purchase_date=None, coverage_months=None, expiry_date=None)
    assert customer_content.claim_wording(status, _W())["claim_message"] == "Please check the purchase date on your invoice"


# --- D: combined PDF -----------------------------------------------------------------------------------------

OWNER, OTHER = "pack_owner_user", "pack_other_user"
INVOICE_LINES = [
    "TAX INVOICE",
    "Sold By: Darshita Etel Private Limited, Bengaluru 560067",
    "Invoice Number: BLR7-1234567   Invoice Date: 12.03.2024",
    "",
    "Billing Address:",
    "Asha Verma",
    "Flat 4B, Lotus Residency, 12th Cross",
    "Indiranagar, Bengaluru 560038",
    "Phone: 9876543210",
    "",
    "Description: Redmi 13C (Starry Black, 4GB RAM, 128GB Storage)",
    "Total: 8,999.00",
]


def _text_pdf(lines):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in lines:
        pdf.cell(0, 8, text=line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _photo(lines):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 60 * len(lines) + 80), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    for i, line in enumerate(lines):
        draw.text((40, 40 + 60 * i), line, fill="black", font=font)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def _pdf_text(data):
    import fitz

    return "\n".join(page.get_text() for page in fitz.open(stream=data, filetype="pdf"))


def _setup(invoice_bytes, name, ctype):
    with SessionLocal() as db:
        db.query(DocumentDB).filter(DocumentDB.owner_user_id.in_([OWNER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyOwnerDB).filter(WarrantyOwnerDB.user_id.in_([OWNER, OTHER])).delete(synchronize_session=False)
        db.query(WarrantyDB).filter_by(id="wty_pack_1").delete()
        for user in (OWNER, OTHER):
            if not db.query(UserDB).filter_by(username=user).first():
                db.add(UserDB(username=user, role="user", hashed_password=hash_password("secret123")))
        db.add(WarrantyDB(id="wty_pack_1", brand="Xiaomi", product_name="Redmi 13C", model_code="13C",
                          purchase_date=datetime(2024, 3, 12), coverage_months=12, alternatives={}))
        db.add(WarrantyOwnerDB(user_id=OWNER, warranty_id="wty_pack_1"))
        db.commit()
    client, auth = _client(OWNER)
    if invoice_bytes is not None:
        assert client.post("/warranties/wty_pack_1/documents", files={"file": (name, invoice_bytes, ctype)},
                           data={"kind": "invoice"}, headers=auth).status_code == 200
    return client, auth


def _client(user):
    client = TestClient(app)
    token = client.post("/auth/login", data={"username": user, "password": "secret123"}, headers={"accept": "application/json"}).json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("DOCUMENT_STORE", "db")


def _docs_count():
    with SessionLocal() as db:
        return db.query(DocumentDB).filter_by(owner_user_id=OWNER).count()


def test_pack_with_text_pdf_invoice_and_hidden_address():
    client, auth = _setup(_text_pdf(INVOICE_LINES), "invoice.pdf", "application/pdf")
    before = _docs_count()
    shown = client.get("/warranties/wty_pack_1/export/combined?include_invoice=true", headers=auth)
    assert shown.status_code == 200 and shown.headers["cache-control"] == "private, no-store"
    text = _pdf_text(shown.content)
    assert "Warranty summary" in text and "Lotus Residency" in text and "attached on the next page" in text
    hidden = _pdf_text(client.get("/warranties/wty_pack_1/export/combined?include_invoice=true&hide_address=true", headers=auth).content)
    for private in ("Lotus Residency", "Indiranagar", "9876543210", "Asha Verma"):
        assert private not in hidden  # the text is removed, not just covered
    assert "Darshita Etel" in hidden and "Redmi 13C" in hidden  # seller and item stay
    assert _docs_count() == before  # generated on request, never stored


def test_pack_without_invoice_and_when_no_invoice_saved():
    client, auth = _setup(None, "", "")
    text = _pdf_text(client.get("/warranties/wty_pack_1/export/combined", headers=auth).content)
    assert "not available - add it under My documents" in text
    text = _pdf_text(client.get("/warranties/wty_pack_1/export/combined?include_invoice=false", headers=auth).content)
    assert "Original invoice" not in text


def test_pack_with_text_invoice_hides_the_block():
    client, auth = _setup("\n".join(INVOICE_LINES).encode(), "bill.txt", "text/plain")
    text = _pdf_text(client.get("/warranties/wty_pack_1/export/combined?hide_address=true", headers=auth).content)
    assert "Lotus Residency" not in text and "[hidden]" in text and "Redmi 13C" in text


def test_pack_refuses_to_claim_hidden_when_no_address_found():
    lines = [line for line in INVOICE_LINES if line not in INVOICE_LINES[4:9]]
    client, auth = _setup(_text_pdf(lines), "invoice.pdf", "application/pdf")
    resp = client.get("/warranties/wty_pack_1/export/combined?hide_address=true", headers=auth)
    assert resp.status_code == 422 and "could not find your address" in resp.json()["detail"]


def test_pack_is_owner_only():
    _setup(_text_pdf(INVOICE_LINES), "invoice.pdf", "application/pdf")
    other, auth = _client(OTHER)
    assert other.get("/warranties/wty_pack_1/export/combined", headers=auth).status_code == 404


def test_phone_photo_invoice_address_hidden_with_ocr():
    pytest.importorskip("pytesseract")
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract not installed")
    from PIL import Image

    boxes = combined_export.address_boxes(combined_export._ocr_lines(Image.open(io.BytesIO(_photo(INVOICE_LINES)))))
    assert len(boxes) >= 4  # label + name + 2 address lines (+ phone)
    client, auth = _setup(_photo(INVOICE_LINES), "IMG_2041.jpg", "image/jpeg")
    resp = client.get("/warranties/wty_pack_1/export/combined?hide_address=true", headers=auth)
    assert resp.status_code == 200


def test_dashboard_has_claim_pdf_options():
    client, _ = _client(OWNER)
    client.post("/auth/login", data={"username": OWNER, "password": "secret123"})
    html = client.get("/ui/neo-dashboard").text
    assert 'id="packIncludeInvoice" checked' in html and 'id="packHideAddress"' in html and "Download claim PDF" in html
