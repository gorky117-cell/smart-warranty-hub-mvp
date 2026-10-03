"""Paddle back-off (fix run B2): after a failure Paddle is skipped for OCR_ENGINE_TTL_SEC."""

from pathlib import Path

import pytest

from app.services import ocr


@pytest.fixture(autouse=True)
def _reset():
    ocr._clear_paddle_backoff()
    ocr._health_cache = None
    yield
    ocr._clear_paddle_backoff()
    ocr._health_cache = None


class _BrokenEngine:
    calls = 0

    def ocr(self, *_a, **_k):
        _BrokenEngine.calls += 1
        raise RuntimeError("NotFoundError: OneDnnContext does not have the input Filter.")


def test_inference_failure_skips_paddle_until_ttl(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(ocr, "_now", lambda: clock["t"])
    monkeypatch.setattr(ocr, "_OCR_ENGINE_TTL_SEC", 900)
    init_calls = []
    monkeypatch.setattr(ocr, "get_paddle", lambda: (init_calls.append(1) or _BrokenEngine(), None))
    _BrokenEngine.calls = 0

    text, err = ocr.run_paddle_ocr(Path("x.png"))
    assert text is None and "PaddleOCR failed" in err
    assert ocr.paddle_backoff_remaining() == 900

    clock["t"] += 600
    text, err = ocr.run_paddle_ocr(Path("x.png"))
    assert err.startswith("PaddleOCR skipped for 300s")
    assert len(init_calls) == 1 and _BrokenEngine.calls == 1  # not retried

    clock["t"] += 301
    ocr.run_paddle_ocr(Path("x.png"))
    assert len(init_calls) == 2  # retried after the TTL


def test_init_failure_also_backs_off(monkeypatch):
    monkeypatch.setattr(ocr, "get_paddle", lambda: (None, "PaddleOCR init failed: Descriptors cannot be created directly"))
    ocr.run_paddle_ocr(Path("x.png"))
    assert ocr.paddle_backoff_remaining() > 0
    assert ocr.run_paddle_ocr(Path("x.png"))[1].startswith("PaddleOCR skipped")


def test_skipped_paddle_goes_straight_to_tesseract(monkeypatch, caplog):
    monkeypatch.setattr(ocr, "get_paddle", lambda: (_BrokenEngine(), None))
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("text", None))
    ocr._run_image_ocr_with_meta(Path("a.png"), "paddle")  # first failure
    caplog.clear()
    text, err, meta = ocr._run_image_ocr_with_meta(Path("b.png"), "paddle")
    assert text == "text" and meta["engine"] == "tesseract" and meta["method"] == "tesseract_fallback"
    assert "skipped" in meta["paddle_error"]
    assert "trying Tesseract fallback" not in caplog.text  # no warning per upload while skipped


def test_health_probe_still_really_tries_paddle(monkeypatch):
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "paddle")
    monkeypatch.setattr(ocr, "find_spec", lambda _n: object())
    monkeypatch.setattr(ocr, "get_paddle", lambda: (_BrokenEngine(), None))
    monkeypatch.setattr(ocr, "run_tesseract_ocr", lambda _p: ("OCR 2468", None))
    ocr._mark_paddle_failed("old failure")
    _BrokenEngine.calls = 0
    report = ocr.health_report(force=True)
    assert _BrokenEngine.calls == 1
    assert report["ok"] is False and report["paddle_backoff_sec"] > 0
