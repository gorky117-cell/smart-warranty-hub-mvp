from fpdf import FPDF

# Invoice 1: Full Details
pdf1 = FPDF()
pdf1.add_page()
pdf1.set_font("Helvetica", size=11)
content1 = """
=====================================
         ELECTRA MART INVOICE
=====================================

Invoice No: INV-2026-00145
Date: 22-Jan-2026

BILL TO:
Mr. Raj Kumar
123 MG Road, Bangalore 560001

PRODUCT DETAILS:
-----------------------------------------
Samsung Galaxy S24 Ultra
Model Code: SM-S928BZKGINS
Serial Number: R5CX40VP8LA
Color: Titanium Black
IMEI: 357854326791234

Purchase Price: Rs. 134,999
GST (18%): Rs. 24,299
-----------------------------------------
TOTAL: Rs. 159,298

PAYMENT: Credit Card ****4521

WARRANTY INFORMATION:
- Standard Warranty: 12 Months
- Extended Warranty Available: 24 Months
- Warranty Expiry: 22-Jan-2027
- For claims visit: samsung.com/in/support

Terms:
- Manufacturing defects covered
- Accidental damage NOT covered
- Keep this invoice for warranty claims

Thank you for shopping with us!
=====================================
"""
for line in content1.strip().split('\n'):
    pdf1.cell(0, 6, line, ln=True)
pdf1.output("test_data/invoice_full_details.pdf")
print("Created: invoice_full_details.pdf")

# Invoice 2: Partial Details (no warranty terms)
pdf2 = FPDF()
pdf2.add_page()
pdf2.set_font("Helvetica", size=11)
content2 = """
=====================================
       APPLIANCE WORLD RECEIPT
=====================================

Receipt #: REC-7845
Date of Purchase: 15-Dec-2025

Customer: Priya Sharma
Mobile: 9876543210

ITEM PURCHASED:
-----------------------------------------
LG Front Load Washing Machine
Model: FHV1408ZWW
Serial: 210PACD12345
Capacity: 8 KG
Price: Rs. 45,999
Tax: Rs. 8,279
-----------------------------------------
TOTAL PAID: Rs. 54,278

Payment Mode: UPI

NOTE: Please keep this receipt safe.
For service enquiries: 1800-315-9999

-----------------------------------------
Thank you for your purchase!
=====================================
"""
for line in content2.strip().split('\n'):
    pdf2.cell(0, 6, line, ln=True)
pdf2.output("test_data/invoice_partial_details.pdf")
print("Created: invoice_partial_details.pdf")

# Invoice 3: Minimal Info
pdf3 = FPDF()
pdf3.add_page()
pdf3.set_font("Helvetica", size=11)
content3 = """
=====================================
         QUICK SHOP RECEIPT
=====================================

Date: 10-Jan-2026

Bosch Refrigerator
Rs. 42,500

Serial: BOS-REF-2026-9987

Paid by Cash

Thank you!
=====================================
"""
for line in content3.strip().split('\n'):
    pdf3.cell(0, 6, line, ln=True)
pdf3.output("test_data/invoice_minimal.pdf")
print("Created: invoice_minimal.pdf")

print("\nAll 3 PDFs created in test_data/ folder!")
