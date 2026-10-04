"""Background Paddle warm-up at start-up (consolidated run P1.3): never blocks, time-limited, logged."""

import logging
import threading
import time

from app.services import ocr


def test_warmup_returns_immediately_and_records_duration(monkeypatch, capsys):
    release = threading.Event()

    def slow_paddle(_path):
        release.wait(5)
        return "OCR 2468", None

    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "paddle")
    monkeypatch.setattr(ocr, "run_paddle_ocr", slow_paddle)
    t0 = time.perf_counter()
    worker = ocr.start_paddle_warmup(timeout_sec=5)
    assert time.perf_counter() - t0 < 0.5  # start-up is never held up
    assert ocr.paddle_warmup_status["status"] == "running"
    release.set()
    worker.join(5)
    assert ocr.paddle_warmup_status["status"] == "ok" and ocr.paddle_warmup_status["seconds"] >= 0
    assert "PaddleOCR warm-up finished in" in capsys.readouterr().out


def test_warmup_warns_when_it_exceeds_the_time_limit(monkeypatch, caplog):
    release = threading.Event()
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "paddle")
    monkeypatch.setattr(ocr, "run_paddle_ocr", lambda _p: (release.wait(5), (None, "PaddleOCR init failed: x"))[1])
    caplog.set_level(logging.INFO, logger=ocr.logger.name)
    worker = ocr.start_paddle_warmup(timeout_sec=0.1)
    deadline = time.time() + 3
    while ocr.paddle_warmup_status["status"] != "slow" and time.time() < deadline:
        time.sleep(0.02)
    assert ocr.paddle_warmup_status["status"] == "slow"
    assert any("still running after" in r.getMessage() for r in caplog.records)
    release.set()
    worker.join(5)
    assert ocr.paddle_warmup_status["status"] == "failed"
    ocr._clear_paddle_backoff()


def test_warmup_skipped_when_paddle_is_not_the_engine(monkeypatch):
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "tesseract")
    assert ocr.start_paddle_warmup() is None and ocr.paddle_warmup_status["status"] == "skipped"
    monkeypatch.setattr(ocr, "_resolve_engine", lambda: "paddle")
    monkeypatch.setenv("OCR_WARMUP", "0")
    assert ocr.start_paddle_warmup() is None
