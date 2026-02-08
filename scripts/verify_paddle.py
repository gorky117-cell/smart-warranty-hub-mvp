import sys
import os

try:
    print("Importing PaddleOCR...")
    from paddleocr import PaddleOCR
    print("PaddleOCR imported successfully.")
    
    # Initialize to check if models download/load ok
    # use_angle_cls=True, lang='en' matches ocr.py
    ocr = PaddleOCR(use_angle_cls=True, lang='en') 
    print("PaddleOCR initialized.")
    
    # Optional: Quick test on dummy image if possible, but init is usually the hurdle
    print("✅ PASS: PaddleOCR is ready.")
    
except ImportError:
    print("❌ FAIL: paddleocr not installed.")
except Exception as e:
    print(f"❌ FAIL: PaddleOCR init error: {e}")
