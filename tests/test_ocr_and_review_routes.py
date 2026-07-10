from types import SimpleNamespace

from app.main import app
from app.services import ocr


def test_ocr_engine_aliases_are_normalized():
    assert ocr._normalize_engine_name("paddle") == "paddle"
    assert ocr._normalize_engine_name("paddleocr") == "paddle"
    assert ocr._normalize_engine_name("Paddle_OCR") == "paddle"
    assert ocr._normalize_engine_name("pytesseract") == "tesseract"


def test_configured_paddleocr_alias_selects_paddle(monkeypatch):
    connector = SimpleNamespace(metadata={"engine": "paddleocr"})
    monkeypatch.setattr(ocr.registry, "get", lambda _name: connector)
    monkeypatch.setattr(ocr.registry, "list", lambda _kind: {})

    assert ocr._resolve_engine() == "paddle"


def test_paddle_failure_uses_tesseract_fallback(monkeypatch, tmp_path):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"placeholder")
    monkeypatch.setattr(ocr, "run_paddle_ocr", lambda _path: (None, "Paddle unavailable"))
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _path: ("receipt text", None))

    text, error, method = ocr._run_image_ocr(image_path, "paddle")

    assert text == "receipt text"
    assert error is None
    assert method == "tesseract_fallback"


def test_review_crawl_and_stats_have_one_registered_handler_each():
    def handlers_for(path, method):
        return [
            route.endpoint.__name__
            for route in app.routes
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
        ]

    assert handlers_for("/reviews/crawl", "POST") == ["trigger_crawl"]
    assert handlers_for("/reviews/stats", "GET") == ["review_stats"]
