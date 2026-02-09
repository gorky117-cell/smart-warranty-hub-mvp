import os
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from .connection_registry import registry
from .audit import log_action

_OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract").lower()
_OCR_MIN_TEXT_CHARS = int(os.getenv("OCR_MIN_TEXT_CHARS", "200"))
_OCR_ENGINE_TTL_SEC = int(os.getenv("OCR_ENGINE_TTL_SEC", "900"))

_paddle_engine: Optional[object] = None
_paddle_last_used: float = 0.0


def _now() -> float:
    return time.time()


def _resolve_engine() -> str:
    connector = registry.get("ocr-default") or next(
        (c for c in registry.list("ocr").values()), None
    )
    if connector:
        engine = connector.metadata.get("engine")
        if engine:
            return str(engine).lower()
    return _OCR_ENGINE


def _should_unload(last_used: float) -> bool:
    if not last_used:
        return False
    return (_now() - last_used) > _OCR_ENGINE_TTL_SEC


def get_paddle() -> Tuple[Optional[object], Optional[str]]:
    global _paddle_engine, _paddle_last_used
    if _paddle_engine is not None and _should_unload(_paddle_last_used):
        _paddle_engine = None
    if _paddle_engine is not None:
        return _paddle_engine, None
    try:
        from paddleocr import PaddleOCR  # type: ignore
        # use_angle_cls=True loads lighter model?
        # lang='en'
        _paddle_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        _paddle_last_used = _now()
        return _paddle_engine, None
    except Exception as exc:  # pragma: no cover - runtime safeguard
        return None, f"PaddleOCR init failed: {exc}"


def _tesseract_ready() -> Tuple[bool, Optional[str]]:
    try:
        import pytesseract  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return False, f"Tesseract unavailable: {exc}"
    try:
        _ = pytesseract.get_tesseract_version()
        return True, None
    except Exception as exc:
        return False, f"Tesseract unavailable: {exc}"


def _ocr_tesseract(img: Image.Image) -> str:
    try:
        import pytesseract
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return f"[Tesseract Error: {e}]"


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


def run_tesseract_ocr(image_path: Path) -> Tuple[Optional[str], Optional[str]]:
    ok, err = _tesseract_ready()
    if not ok:
        return None, err
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img)
        text = (text or "").strip()
        return text if text else None, None
    except Exception as exc:  # pragma: no cover - runtime safeguard
        return None, f"Tesseract OCR failed: {exc}"


def _extract_pdf_text(path_obj: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return None, f"PDF reader unavailable: {exc}"
    try:
        reader = PdfReader(str(path_obj))
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        text = "\n".join(chunks).strip()
        return text if text else None, None
    except Exception as exc:
        return None, f"PDF text extraction failed: {exc}"


def _maybe_ocr_pdf(path_obj: Path) -> Tuple[Optional[str], Optional[str]]:
    # Try pymupdf (fitz) first, then fall back to pdf2image
    try:
        import fitz  # pymupdf
        import tempfile
        import os as _os
        
        doc = fitz.open(str(path_obj))
        all_text = []
        for page_num in range(min(3, len(doc))):  # Limit to first 3 pages
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            
            # Create temp file path without keeping it open (Windows compat)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
            _os.close(tmp_fd)  # Close immediately so pix.save can write
            
            try:
                pix.save(tmp_path)
                
                engine = _resolve_engine()
                if engine == "paddle":
                    text, err = run_paddle_ocr(Path(tmp_path))
                else:
                    text, err = run_tesseract_ocr(Path(tmp_path))
                
                if text:
                    all_text.append(text)
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
        
        doc.close()
        combined = "\n".join(all_text).strip()
        return (combined if combined else None), None
    except ImportError:
        pass  # Fall through to pdf2image
    except Exception as exc:
        return None, f"PDF OCR via pymupdf failed: {exc}"
    except ImportError:
        pass  # Fall through to pdf2image
    except Exception as exc:
        return None, f"PDF OCR via pymupdf failed: {exc}"
    
    # Fallback to pdf2image (requires poppler)
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception:
        return None, "PDF OCR unavailable (install pdf2image/poppler or pymupdf)."
    try:
        images = convert_from_path(str(path_obj), first_page=1, last_page=1)
        if not images:
            return None, "PDF OCR failed: no pages rendered."
        image = images[0]
        engine = _resolve_engine()
        if engine == "paddle":
            return None, "PDF OCR with Paddle not supported (image path required)."
        try:
            import pytesseract  # type: ignore
        except Exception as exc:
            return None, f"Tesseract unavailable: {exc}"
        text = pytesseract.image_to_string(image)
        text = (text or "").strip()
        return text if text else None, None
    except Exception as exc:
        return None, f"PDF OCR failed: {exc}"


def extract_text_with_meta(image_path: str, min_chars: int | None = None) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Try text extraction first; OCR only if text is too short.
    Returns (text, error, meta).
    """
    path_obj = Path(image_path)
    if not path_obj.exists():
        return None, f"File not found: {image_path}", {"ocr_used": False, "method": "missing"}

    min_chars = _OCR_MIN_TEXT_CHARS if min_chars is None else min_chars
    suffix = path_obj.suffix.lower()

    if suffix in {".txt", ".md", ".log", ".json"}:
        try:
            text = path_obj.read_text(encoding="utf-8", errors="ignore").strip()
            return (text if text else None), None, {"ocr_used": False, "method": "text"}
        except Exception as exc:
            return None, f"Text read failed: {exc}", {"ocr_used": False, "method": "text"}

    if suffix == ".pdf":
        text, err = _extract_pdf_text(path_obj)
        if text and len(text) >= min_chars:
            return text, None, {"ocr_used": False, "method": "pdf"}
        ocr_text, ocr_err = _maybe_ocr_pdf(path_obj)
        if ocr_text:
            return ocr_text, None, {"ocr_used": True, "method": "pdf_ocr"}
        return text, ocr_err or err or "PDF text extraction produced no content.", {"ocr_used": False, "method": "pdf"}

    engine = _resolve_engine()
    if engine == "paddle":
        text, err = run_paddle_ocr(path_obj)
    else:
        text, err = run_tesseract_ocr(path_obj)

    if text:
        log_action("ocr_call", f"engine={engine} path={image_path}")
        return text, None, {"ocr_used": True, "method": engine}
    return None, err or "OCR produced no text", {"ocr_used": True, "method": engine}


def extract_text(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    text, err, _meta = extract_text_with_meta(image_path)
    return text, err


def health() -> Tuple[bool, str]:
    engine = _resolve_engine()
    if engine == "paddle":
        engine_obj, err = get_paddle()
        if err:
            return False, err
        return engine_obj is not None, "PaddleOCR ready" if engine_obj else "PaddleOCR unavailable"
    ok, err = _tesseract_ready()
    return ok, "Tesseract ready" if ok else (err or "Tesseract unavailable")
