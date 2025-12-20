# OCR and layout-aware NLP options

Recommended open-source engines you can plug into `app/services/ocr.py`:

- PaddleOCR (default hook): Accurate, multilingual, tables/forms. Install: `pip install paddleocr==2.7.0.2 paddlepaddle` (use platform-specific paddlepaddle wheel).
- DocTR: TensorFlow/PyTorch OCR with detection + recognition. Install: `pip install python-doctr[torch]`.
- EasyOCR: Lightweight, quick start. Install: `pip install easyocr`.

Layout-aware extraction for receipts/warranty docs:
- LayoutLMv3 / LayoutXLM: `pip install transformers pillow` then use a token-classification pipeline with document images.
- Donut: end-to-end image-to-sequence for receipts/invoices. `pip install transformers sentencepiece`.
- TrOCR: image-to-text that can precede regex/rule extraction.

How to wire:
- Update `extract_text` in `app/services/ocr.py` to call your preferred engine.
- After OCR, `extract_product_fields` (ingestion.py) still runs heuristics for brand/model/serial/purchase date/coverage; you can replace it with a fine-tuned LayoutLM or Donut parser when available.
