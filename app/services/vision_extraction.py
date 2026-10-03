"""AI vision tier for invoice images where OCR returns little or no text (fix run B10).

Off unless `VISION_AI_EXTRACTION=1` and the OpenAI lane is configured (`OPENAI_ENABLED=1` +
`OPENAI_API_KEY`). Nothing here enables a provider.

1. `redact_image()` locates words with Tesseract on a pre-processed copy (grayscale, 2x upscale,
   autocontrast), rebuilds lines, applies the same buyer rules as `privacy.redact_text` and paints black
   boxes over every masked token. If no word can be located, redaction cannot be guaranteed and the image
   is **not sent** (`reason="no_locatable_text"`).
2. The provider gets the redacted PNG and returns, per field, `{value, source_line, confidence}` where
   `source_line` is the line as printed on the invoice.
3. A value is kept only if it appears inside its quoted source line and confidence >= minimum. If the
   value also appears in the OCR text it is used as a field (capped at 0.6); otherwise it is a **pending
   suggestion** the user confirms (`alternatives.vision_suggestions`). Vision-only values never become
   fields on their own.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .privacy import redact_text

FIELDS = ("brand", "product_name", "model_code", "serial_no", "invoice_no", "purchase_date")
MIN_TEXT_CHARS = int(os.getenv("VISION_MIN_TEXT_CHARS", "60"))
MIN_CONFIDENCE = float(os.getenv("VISION_MIN_CONFIDENCE", "0.5"))
Provider = Callable[[bytes], Optional[Dict[str, Any]]]


def enabled() -> bool:
    return os.getenv("VISION_AI_EXTRACTION", "0").strip().lower() in ("1", "true", "yes")


def needs_vision(text: Optional[str]) -> bool:
    return len((text or "").strip()) < MIN_TEXT_CHARS


def _words_from(img, scale: int, offset: Tuple[int, int], config: str) -> List[Dict[str, Any]]:
    import pytesseract  # type: ignore

    data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
    words = []
    ox, oy = offset
    for i, text in enumerate(data.get("text", [])):
        if not str(text).strip():
            continue
        words.append(
            {
                "text": str(text),
                "conf": float(data.get("conf", [0] * (i + 1))[i] or 0),
                "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
                "box": (
                    ox + data["left"][i] // scale,
                    oy + data["top"][i] // scale,
                    ox + (data["left"][i] + data["width"][i]) // scale,
                    oy + (data["top"][i] + data["height"][i]) // scale,
                ),
            }
        )
    return words


def _locate_words(image) -> List[Dict[str, Any]]:
    """Word boxes in original-image coordinates, from whichever pre-processing finds more words:
    (a) whole page, autocontrast, 2x; (b) crop to the dark-text region, 5x, sharpened, column mode —
    needed for small, blurred, low-contrast phone photos (measured: 0 → ~20 words on S031/S035/S040)."""
    from PIL import Image, ImageFilter, ImageOps

    gray = image.convert("L")
    page = ImageOps.autocontrast(gray)
    best = _words_from(page.resize((page.width * 2, page.height * 2)), 2, (0, 0), "")
    box = gray.point(lambda p: 255 if p < 170 else 0).getbbox()
    if box:
        pad = 20
        x0, y0 = max(0, box[0] - pad), max(0, box[1] - pad)
        crop = ImageOps.autocontrast(gray.crop((x0, y0, min(gray.width, box[2] + pad), min(gray.height, box[3] + pad))), cutoff=1)
        scale = 5
        big = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS).filter(
            ImageFilter.UnsharpMask(radius=3, percent=200)
        )
        cropped = _words_from(big, scale, (x0, y0), "--psm 4")
        if len(cropped) > len(best):
            best = cropped
    return best


def redact_image(image_bytes: bytes) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """Return (redacted_png_or_None, info). None means the image must not be sent."""
    from PIL import Image, ImageDraw

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        words = _locate_words(image)
    except Exception as exc:
        return None, {"reason": f"redaction_failed:{exc.__class__.__name__}"}
    if not words:
        return None, {"reason": "no_locatable_text"}
    lines: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}
    for word in words:
        lines.setdefault(word["line"], []).append(word)
    ordered = [lines[key] for key in sorted(lines)]
    original = "\n".join(" ".join(w["text"] for w in line) for line in ordered)
    redacted, counts = redact_text(original)
    confidences = [w["conf"] for w in words if w["conf"] >= 0]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    # Garbled OCR may misread a "Bill To" label, so buyer rules cannot be trusted: keep only lines that
    # look like invoice/product data and black out every other line completely.
    strict = mean_conf < STRICT_BELOW_CONFIDENCE
    draw = ImageDraw.Draw(image)
    masked = 0
    for line_words, red_line in zip(ordered, redacted.split("\n")):
        line_text = " ".join(w["text"] for w in line_words)
        kept = set(re.findall(r"\S+", red_line))
        line_masked = "[REDACTED]" in red_line
        mask_all = strict and not _looks_like_invoice_data(line_text)
        for word in line_words:
            if mask_all or (line_masked and word["text"] not in kept):
                x0, y0, x1, y1 = word["box"]
                draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill="black")
                masked += 1
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), {
        "reason": "redacted",
        "mode": "strict" if strict else "buyer_rules",
        "mean_ocr_confidence": round(mean_conf, 1),
        "words_located": len(words),
        "tokens_masked": masked,
        "counts": counts,
    }


STRICT_BELOW_CONFIDENCE = float(os.getenv("VISION_STRICT_REDACTION_BELOW_CONF", "70"))
_INVOICE_DATA_RE = re.compile(
    r"\b(inv\w*|date|dt|model|mod\w*|serial|seri\w*|s/?n|imei|warrant\w*|product|prod\w*|brand|qty|hsn|total|tax|gst\w*|"
    r"store|copy|month\w*|year\w*)\b",
    re.IGNORECASE,
)


def _looks_like_invoice_data(line: str) -> bool:
    try:
        from .ingestion import _looks_like_address_text

        if _looks_like_address_text(line):
            return False  # addresses are never kept in strict mode, even with codes like "45A/2"
    except Exception:
        return False
    if _INVOICE_DATA_RE.search(line):
        return True
    if re.search(r"\b(?=[A-Za-z0-9\-/]*\d)(?=[A-Za-z0-9\-/]*[A-Za-z])[A-Za-z0-9\-/]{4,}\b", line):
        return True  # identifier-like token: letters and digits
    if re.search(r"\b\d{1,2}[\s\-/.](?:\d{1,2}|[A-Za-z]{3})[\s\-/.]\d{2,4}\b", line):
        return True  # date
    try:
        from .brand_registry import find_brands

        return bool(find_brands(line))
    except Exception:
        return False


_PROMPT = (
    "This is a photo of a purchase invoice. Black boxes hide personal data. For each of brand, product_name, "
    "model_code, serial_no, invoice_no, purchase_date return an object with value, source_line and confidence "
    "(0-1). source_line must be the full line exactly as printed on the invoice that contains the value. If a "
    "field is not printed, return empty value and empty source_line. Never guess."
)


def _openai_vision_provider(png: bytes) -> Optional[Dict[str, Any]]:
    from .openai_intelligence import _OPENAI_MODEL, _get_client, _response_text

    client, err = _get_client()
    if err or client is None:
        return None
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": {"type": "string"}, "source_line": {"type": "string"}, "confidence": {"type": "number"}},
        "required": ["value", "source_line", "confidence"],
    }
    schema = {"type": "object", "additionalProperties": False, "properties": {f: item for f in FIELDS}, "required": list(FIELDS)}
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    try:
        response = client.responses.create(
            model=_OPENAI_MODEL,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": _PROMPT},
                {"type": "input_image", "image_url": data_url},
            ]}],
            temperature=0,
            max_output_tokens=400,
            text={"format": {"type": "json_schema", "name": "vision_invoice_fields", "strict": True, "schema": schema}},
        )
        payload = json.loads(_response_text(response))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).lower()


def validate_vision_fields(payload: Optional[Dict[str, Any]], ocr_text: str) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Return (grounded_fields, suggestions, rejected)."""
    grounded: Dict[str, str] = {}
    suggestions: Dict[str, Dict[str, Any]] = {}
    rejected: Dict[str, str] = {}
    ocr = _norm(ocr_text)
    for field in FIELDS:
        item = (payload or {}).get(field) or {}
        if not isinstance(item, dict):
            rejected[field] = "malformed"
            continue
        value = " ".join(str(item.get("value") or "").split())
        line = " ".join(str(item.get("source_line") or "").split())
        if not value:
            continue
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            rejected[field] = "no_confidence"
            continue
        if not line:
            rejected[field] = "no_source_line"
        elif value.lower() not in line.lower():
            rejected[field] = "value_not_in_source_line"
        elif "[redacted]" in line.lower():
            rejected[field] = "from_redacted_area"
        elif confidence < MIN_CONFIDENCE:
            rejected[field] = "low_confidence"
        elif ocr and _norm(value) in ocr:
            grounded[field] = value
        else:
            suggestions[field] = {
                "value": value,
                "source_line": line,
                "confidence": round(min(max(confidence, 0.0), 1.0), 3),
                "status": "pending",
                "source": "ai_vision",
            }
    return grounded, suggestions, rejected


def apply_vision_tier(
    image_path: str,
    ocr_text: str,
    fields: Dict[str, Any],
    confidence: Dict[str, Any],
    alternatives: Dict[str, Any],
    provider: Optional[Provider] = None,
    force: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Run the vision tier for a low-text image. No-op unless enabled (or ``force`` in tests)."""
    if not (force or enabled()) or not needs_vision(ocr_text):
        return fields, confidence, alternatives
    if not str(image_path or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
        return fields, confidence, alternatives
    alternatives = dict(alternatives or {})
    try:
        with open(image_path, "rb") as handle:
            raw = handle.read()
    except OSError:
        alternatives["ai_vision"] = {"sent": False, "reason": "image_unreadable"}
        return fields, confidence, alternatives
    png, info = redact_image(raw)
    meta: Dict[str, Any] = {"sent": False, **{k: v for k, v in info.items() if k != "counts"}}
    if png is None:
        alternatives["ai_vision"] = meta
        return fields, confidence, alternatives
    payload = (provider or _openai_vision_provider)(png)
    meta["sent"] = True
    meta["provider_returned"] = payload is not None
    grounded, suggestions, rejected = validate_vision_fields(payload, ocr_text)
    fields = dict(fields)
    confidence = dict(confidence)
    for key, value in grounded.items():
        if not fields.get(key):
            fields[key] = value
            confidence[key] = 0.6
    if suggestions:
        alternatives["vision_suggestions"] = suggestions
    meta.update({"grounded": sorted(grounded), "suggested": sorted(suggestions), "rejected": rejected})
    alternatives["ai_vision"] = meta
    return fields, confidence, alternatives
