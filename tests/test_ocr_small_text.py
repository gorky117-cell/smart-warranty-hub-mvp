"""Backlog #16: small text is enlarged before Tesseract; large text and unreadable photos are left alone."""
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services import ocr

SAMPLES = Path("test_data/ingestion_ocr_samples")


def _text_image(font_px, size=(1400, 600), background="white"):
    img = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=font_px)
    for n, line in enumerate(["Invoice No: INV-2025-0001", "Date: 06-Jan-2025", "Warranty: 36 months"]):
        draw.text((40, 40 + n * font_px * 3), line, fill="black", font=font)
    return img


def test_line_height_is_measured():
    small, large = ocr.text_line_height(_text_image(10)), ocr.text_line_height(_text_image(30))
    assert small and large and small < ocr.TESSERACT_SMALL_TEXT_PX <= large
    assert ocr.text_line_height(Image.new("RGB", (800, 600), "white")) is None


def test_small_text_is_enlarged_large_text_is_not():
    small = _text_image(10)
    prepared = ocr.prepare_for_tesseract(small)
    assert prepared.size[0] > small.size[0] and prepared.mode == "L"
    assert prepared.size[0] <= small.size[0] * 3
    large = _text_image(30)
    assert ocr.prepare_for_tesseract(large) is large
    blank = Image.new("RGB", (800, 600), "white")
    assert ocr.prepare_for_tesseract(blank) is blank


def test_enlarging_stays_under_the_pixel_cap():
    big_small_text = _text_image(9, size=(4000, 3000))
    prepared = ocr.prepare_for_tesseract(big_small_text)
    assert prepared.size[0] * prepared.size[1] <= ocr._TESSERACT_MAX_PIXELS


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
@pytest.mark.parametrize("sample,months,day", [("S001", "36", "06-Jan-2025"), ("S009", "36", "15-Feb-2025"), ("S024", "12", "01-May-2025")])
def test_small_text_samples_read_correctly(sample, months, day):
    text, _err, meta = ocr.extract_text_with_meta(str(SAMPLES / f"{sample}.png"))
    assert meta["engine"] == "tesseract" or meta.get("method") in ("paddle", "tesseract_fallback")
    assert f"{months} months" in text and day.replace("-", "") in text.replace("-", "").replace(" ", "")
