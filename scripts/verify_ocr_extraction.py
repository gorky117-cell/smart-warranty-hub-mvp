import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Copied from app/services/ingestion.py to verify logic in isolation
def parse_date_from_text(text: str) -> Optional[str]:
    candidates = re.findall(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", text
    )
    for raw in candidates:
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
    return None

def extract_product_fields(text: str) -> Tuple[Dict[str, str], Dict[str, float]]:
    lowered = text.lower()
    fields: Dict[str, str] = {}
    confidence: Dict[str, float] = {}

    brand_match = re.search(r"brand[:\s]+([a-z0-9 \-]{2,40})", lowered, re.IGNORECASE)
    if brand_match:
        fields["brand"] = brand_match.group(1).strip().title()
        confidence["brand"] = 0.7

    product_match = re.search(r"(product|item|device)(?!\s*details)[:\s]+([a-z0-9 \-]{2,60})", lowered, re.IGNORECASE)
    if product_match:
        fields["product_name"] = product_match.group(2).strip().title()
        confidence["product_name"] = 0.6
        
    purchase_date = parse_date_from_text(text)
    if purchase_date:
        fields["purchase_date"] = purchase_date
        confidence["purchase_date"] = 0.6

    return fields, confidence

def verify_extraction():
    # Mock OCR output (simulating a messy invoice scan)
    mock_ocr_text = """
    TAX INVOICE
    Seller: Electronics World
    Date: 15-08-2025
    Inv No: INV-2025-001
    
    Item Details:
    Product: Samsung Galaxy S24
    Brand: Samsung
    Model: SM-S921B
    Price: 79000
    
    Warranty: 12 months manufacturer warranty
    """
    
    print("--- Verification: OCR Extraction Logic ---")
    print(f"Input Text (Mock OCR):\n{mock_ocr_text}")
    
    fields, confidence = extract_product_fields(mock_ocr_text)
    
    print("\nExtracted Fields:")
    for k, v in fields.items():
        print(f"  - {k}: {v} (Conf: {confidence.get(k)})")
        
    expected = {
        "brand": "Samsung",
        "product_name": "Samsung Galaxy S24", 
        "purchase_date": "2025-08-15"
    }
    
    passed = True
    for k, v in expected.items():
        got = fields.get(k)
        if got != v:
            print(f"❌ Mismatch on {k}:")
            print(f"   Gathered: {repr(got)}")
            print(f"   Expected: {repr(v)}")
            passed = False
            
    if passed:
        print("\n✅ PASS: Extraction Logic Verified")
    else:
        print("\n❌ FAIL: Extraction logic incorrect")

if __name__ == "__main__":
    verify_extraction()
