import sys
import os

# Add project root to path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import SessionLocal, DB_URL, engine
from app.db_models import WarrantyDB, ParsedFieldDB, PipelineJobDB

def debug_warranties():
    print(f"--- Debugging Warranties ---")
    print(f"Connecting to: {DB_URL}")
    print(f"Engine URL: {engine.url}")
    
    db = SessionLocal()
    try:
        warranties = db.query(WarrantyDB).all()
        if not warranties:
            print("No warranties found in DB.")
        
        for w in warranties:
            print(f"\nID: {w.id}")
            print(f"Product: {w.product_name}")
            print(f"Brand: {w.brand}")
            print(f"Model: {w.model_code}")
            print(f"Serial: {w.serial_no}")
            print(f"Purchase Date: {w.purchase_date}")
            print(f"Coverage: {w.coverage_months} months")
            
            # Check parsed fields
            parsed = db.query(ParsedFieldDB).filter_by(warranty_id=w.id).all()
            if parsed:
                print(f"  [Parsed Fields Found]: {len(parsed)} entries")
                for p in parsed:
                    print(f"    - Raw Text Len: {len(p.raw_text) if p.raw_text else 0}")
                    print(f"    - Confidence: {p.confidence}")
            else:
                print(f"  [!] No ParsedFieldDB records found.")

            # Check jobs
            jobs = db.query(PipelineJobDB).filter_by(warranty_id=w.id).all()
            if jobs:
                print(f"  [Pipeline Jobs]:")
                for j in jobs:
                    print(f"    - Job {j.id}: Status='{j.status}', Error='{j.error}'")
            else:
                print(f"  [!] No Pipeline Jobs found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_warranties()
