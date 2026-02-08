"""Manual test of the extraction and warranty update pipeline."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.db import SessionLocal
from app.db_models import WarrantyDB, ParsedFieldDB
from app.services.ingestion import extract_product_fields

# Sample OCR text from the invoice
sample_text = """Zenith Home Appliances
GST Invoice (Synthetic)  www.zenith-home.test
GSTIN: 27AAACZ9999Z1Z5
Address: Unit 9, Industrial Estate, Andheri East, Mumbai
400093, Maharashtra, India
Support: care@zenith-home.test | +91-22-5000-0000
Invoice Type: Tax Invoice
Invoice No: ZHA/2025-26/INV/7781
Date: 15-Nov-2025
Place of Supply: Maharashtra (27)
Bill To
Test Customer
Description
HSN/SAC
Qty
Unit Price
1. TurboWash Pro 2000 Front Load Washing Machine - 8kg, Inverter Motor, Steam Clean
85044000
1
42,000"""

print("=== Testing Extraction ===")
fields, confidence, alternatives = extract_product_fields(sample_text)
print(f"Fields: {fields}")
print(f"Confidence: {confidence}")

print("\n=== Finding Latest Warranty with NULL brand ===")
db = SessionLocal()
warranty = db.query(WarrantyDB).filter(WarrantyDB.brand == None).order_by(WarrantyDB.created_at.desc()).first()
if warranty:
    print(f"Found warranty: {warranty.id}")
    print(f"  Current Brand: {warranty.brand}")
    print(f"  Current Date: {warranty.purchase_date}")
    
    # Try to update it
    print("\n=== Attempting Manual Update ===")
    if fields.get("brand"):
        warranty.brand = fields["brand"]
        print(f"  Set brand to: {fields['brand']}")
    if fields.get("purchase_date"):
        from datetime import datetime
        try:
            pd = datetime.fromisoformat(fields["purchase_date"])
            warranty.purchase_date = pd
            print(f"  Set purchase_date to: {pd}")
        except Exception as e:
            print(f"  Date parse error: {e}")
    
    db.add(warranty)
    db.commit()
    db.refresh(warranty)
    print(f"\n=== After Update ===")
    print(f"  Brand: {warranty.brand}")
    print(f"  Date: {warranty.purchase_date}")
else:
    print("No warranty with NULL brand found")
    
db.close()
