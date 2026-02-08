"""Test script to verify the complete upload-to-extraction pipeline works."""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.db import SessionLocal
from app.db_models import WarrantyDB, ParsedFieldDB

print("=== Checking Latest 5 Warranties (with extracted data) ===")
db = SessionLocal()

# Get the 5 most recent warranties
warranties = db.query(WarrantyDB).order_by(WarrantyDB.created_at.desc()).limit(5).all()

for w in warranties:
    print(f"\nID: {w.id}")
    print(f"  Brand: {w.brand}")
    print(f"  Product: {w.product_name}")
    print(f"  Model: {w.model_code}")
    print(f"  Serial: {w.serial_no}")
    print(f"  Purchase Date: {w.purchase_date}")
    print(f"  Created: {w.created_at}")
    print("-" * 40)

# Count how many warranties have extracted data
total = db.query(WarrantyDB).count()
with_brand = db.query(WarrantyDB).filter(WarrantyDB.brand != None).count()
with_date = db.query(WarrantyDB).filter(WarrantyDB.purchase_date != None).count()

print(f"\n=== Summary ===")
print(f"Total warranties: {total}")
print(f"With Brand extracted: {with_brand}")
print(f"With Date extracted: {with_date}")

db.close()
