from pathlib import Path
from typing import Optional, Tuple

from .connection_registry import registry
from .audit import log_action

_paddle_engine = None


def get_paddle() -> Tuple[Optional[object], Optional[str]]:
    global _paddle_engine
    if _paddle_engine is not None:
        return _paddle_engine, None
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return None, f"PaddleOCR unavailable: {exc}"
    try:
        _paddle_engine = PaddleOCR(use_angle_cls=True, lang="en")
        return _paddle_engine, None
    except Exception as exc:  # pragma: no cover - runtime safeguard
        return None, f"PaddleOCR init failed: {exc}"


def run_paddle_ocr(image_path: Path) -> Tuple[Optional[str], Optional[str]]:
    engine, err = get_paddle()
    if err:
        return None, err
    try:
        result = engine.ocr(str(image_path), cls=True)
        lines = []
        for page in result:
            for line in page:
                if line and len(line) > 1 and line[1]:
                    lines.append(line[1][0])
        text = "\n".join(lines).strip()
        return text if text else None, None
    except Exception as exc:  # pragma: no cover - runtime safeguard
        return None, f"PaddleOCR failed: {exc}"


def extract_text(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Try OCR on an image or PDF path. Returns (text, error).
    """
    path_obj = Path(image_path)
    if not path_obj.exists():
        return None, f"File not found: {image_path}"

    # Preferred connector route
    connector = registry.get("ocr-default") or next(
        (c for c in registry.list("ocr").values()), None
    )
    if connector:
        engine = connector.metadata.get("engine", "paddleocr")
        if engine == "paddleocr":
            text, err = run_paddle_ocr(path_obj)
            if text:
                log_action("ocr_call", f"engine=paddleocr path={image_path}")
                return text, None
            return None, err or "OCR produced no text"
        # Future engines can be added here

    # Fallback to PaddleOCR attempt even if no connector is registered.
    text, err = run_paddle_ocr(path_obj)
    if text:
        return text, None
    return None, err or "OCR produced no text"


def health() -> Tuple[bool, str]:
    engine, err = get_paddle()
    if err:
        return False, err
    return engine is not None, "PaddleOCR ready" if engine else "PaddleOCR unavailable"
