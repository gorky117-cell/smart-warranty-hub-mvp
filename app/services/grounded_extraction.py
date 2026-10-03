"""Grounded AI extraction of model code, serial number and invoice number (work plan step 9).

Prepared, **not active**: runs only when `GROUNDED_AI_EXTRACTION=1` and a provider is configured
(the default provider is the optional OpenAI lane in `openai_intelligence`, which itself needs
`OPENAI_ENABLED=1` and `OPENAI_API_KEY`). No key or provider is enabled by this module.

Flow:
1. `redact_invoice_text()` removes customer name/address blocks, address-like lines, phone numbers,
   e-mail addresses and PIN codes before any text leaves the machine.
2. The provider returns, per field, `{"value", "source_line", "confidence"}`.
3. `validate_ai_fields()` keeps a value only if: the source line appears verbatim in the text that was
   sent, the value appears in that line and in the original OCR text, confidence >= the minimum, and
   the field-specific plausibility rules pass (serial: letters+digits or a Luhn-valid IMEI, not an
   invoice header or date; invoice number: has a digit, not a date, HSN/SAC, GSTIN or phone number;
   model code: has a digit, not a date/HSN/spec fragment). Everything else is discarded.
4. `apply_grounded_extraction()` overlays validated values on the deterministic fields; when AI finds
   nothing valid the deterministic value (or blank) is kept.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

AI_FIELDS = ("model_code", "serial_no", "invoice_no")
MIN_CONFIDENCE = float(os.getenv("GROUNDED_AI_MIN_CONFIDENCE", "0.5"))
MAX_INPUT_CHARS = int(os.getenv("GROUNDED_AI_MAX_INPUT_CHARS", "6000"))
REDACTED = "[REDACTED]"

Provider = Callable[[str], Optional[Dict[str, Any]]]


def enabled() -> bool:
    return os.getenv("GROUNDED_AI_EXTRACTION", "0").strip().lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------- redaction

_PARTY_LABEL_RE = re.compile(
    r"^\s*(bill(?:ed)?\s*to|ship(?:ped)?\s*to|sold\s*to|deliver(?:y)?\s*to|buyer|consignee|customer(?:\s*name)?|"
    r"name|billing\s*address|shipping\s*address|address)\b\s*[:\-]?",
    re.IGNORECASE,
)
_BLOCK_END_RE = re.compile(
    r"\b(invoice|inv\b|date|gstin|order|item|description|sl\b|s\.?\s*no|qty|quantity|hsn|sac|product|model|serial|"
    r"imei|warranty|amount|total|rate|seller|sold\s*by)\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE_RE = re.compile(r"(?<![\w])(?:\+?91[\s\-]?)?(?:0\d{2,4}[\s\-]?\d{6,8}|[6-9]\d{4}[\s\-]?\d{5})(?![\w])")
_PIN_RE = re.compile(r"(?<!\d)\d{3}\s?\d{3}(?!\d)")


def redact_invoice_text(text: str) -> Tuple[str, Dict[str, int]]:
    """Strip customer name, address and phone details. Returns (redacted_text, counts)."""
    from .ingestion import _has_product_signal, _looks_like_address_text  # local import: ingestion is heavy

    counts = {"party_lines": 0, "address_lines": 0, "phones": 0, "emails": 0, "pins": 0}
    out: List[str] = []
    in_block = 0
    for line in (text or "").splitlines():
        stripped = line.strip()
        if _PARTY_LABEL_RE.match(stripped):
            label = _PARTY_LABEL_RE.match(stripped).group(0)
            out.append(f"{label} {REDACTED}".strip())
            counts["party_lines"] += 1
            in_block = 4  # following lines up to 4 belong to the name/address block
            continue
        block_ends = _BLOCK_END_RE.search(stripped) or _has_product_signal(stripped)
        if in_block and stripped and not block_ends:
            out.append(REDACTED)
            counts["party_lines"] += 1
            in_block -= 1
            continue
        in_block = 0
        if stripped and _looks_like_address_text(stripped):
            out.append(REDACTED)
            counts["address_lines"] += 1
            continue
        line, n = _EMAIL_RE.subn(REDACTED, line)
        counts["emails"] += n
        line, n = _PHONE_RE.subn(REDACTED, line)
        counts["phones"] += n
        if re.search(r"\b(pin|pincode|postal|zip)\b", line, re.IGNORECASE):
            line, n = _PIN_RE.subn(REDACTED, line)
            counts["pins"] += n
        out.append(line)
    return "\n".join(out), counts


# --------------------------------------------------------------------------- validation

_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$", re.IGNORECASE)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).lower()


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _is_hsn_like(value: str, line: str) -> bool:
    return bool(re.fullmatch(r"\d{4,8}", value)) and bool(re.search(r"\b(hsn|sac)\b", line, re.IGNORECASE))


def _plausible(field: str, value: str, line: str) -> Optional[str]:
    """Return a rejection reason, or None when the value is plausible for the field."""
    from .ingestion import _is_spec_only, _plausible_serial, parse_date_from_text

    if field == "serial_no":
        if re.fullmatch(r"\d{15}", value):
            return None if _luhn_ok(value) else "imei_checksum"
        if not 6 <= len(value) <= 24:
            return "serial_length"
        return None if _plausible_serial(value) else "serial_implausible"
    if not re.search(r"\d", value):
        return "no_digit"
    if parse_date_from_text(value):
        return "looks_like_date"
    if _is_hsn_like(value, line):
        return "hsn_or_sac_code"
    if field == "invoice_no":
        if _GSTIN_RE.match(value):
            return "gstin"
        if _PHONE_RE.fullmatch(value):
            return "phone_number"
        return None if 3 <= len(value) <= 30 else "invoice_length"
    if field == "model_code":
        if _is_spec_only(value):
            return "spec_fragment"
        return None if 2 <= len(value) <= 30 else "model_length"
    return "unknown_field"


def validate_ai_fields(
    ocr_text: str,
    sent_text: str,
    payload: Optional[Dict[str, Any]],
    min_confidence: float = MIN_CONFIDENCE,
) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, str]]:
    """Keep only grounded, plausible values. Returns (fields, confidence, rejections)."""
    fields: Dict[str, str] = {}
    confidence: Dict[str, float] = {}
    rejected: Dict[str, str] = {}
    sent_lines = {_norm(line) for line in (sent_text or "").splitlines() if line.strip()}
    sent_norm = _norm(sent_text)
    ocr_norm = _norm(ocr_text)
    for field in AI_FIELDS:
        item = (payload or {}).get(field) or {}
        if not isinstance(item, dict):
            rejected[field] = "malformed"
            continue
        value = " ".join(str(item.get("value") or "").split())
        line = " ".join(str(item.get("source_line") or "").split())
        if not value:
            continue  # AI reports the field absent: nothing to keep
        try:
            score = float(item.get("confidence"))
        except (TypeError, ValueError):
            rejected[field] = "no_confidence"
            continue
        if not line:
            rejected[field] = "no_source_line"
        elif _norm(line) not in sent_lines and _norm(line) not in sent_norm:
            rejected[field] = "source_line_not_in_text"
        elif value.lower() not in line.lower():
            rejected[field] = "value_not_in_source_line"
        elif value.lower() not in ocr_norm:
            rejected[field] = "value_not_in_ocr_text"
        elif score < min_confidence:
            rejected[field] = "low_confidence"
        else:
            reason = _plausible(field, value, line)
            if reason:
                rejected[field] = reason
            else:
                fields[field] = value.upper() if field != "invoice_no" else value
                confidence[field] = round(min(max(score, 0.0), 0.9), 3)
    return fields, confidence, rejected


# --------------------------------------------------------------------------- provider

_PROMPT = (
    "From the invoice text, extract model_code, serial_no and invoice_no. For each return an object with "
    "value, source_line and confidence (0-1). source_line must be copied exactly, character for character, "
    "from one line of the text. If a field is not printed in the text, return an empty value and empty "
    "source_line. Never guess or reformat values. Text marked [REDACTED] is removed personal data."
)


def _openai_provider(redacted_text: str) -> Optional[Dict[str, Any]]:
    from .openai_intelligence import _get_client, _OPENAI_MODEL, _response_text

    client, err = _get_client()
    if err or client is None:
        return None
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": {"type": "string"}, "source_line": {"type": "string"}, "confidence": {"type": "number"}},
        "required": ["value", "source_line", "confidence"],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {field: item for field in AI_FIELDS},
        "required": list(AI_FIELDS),
    }
    try:
        response = client.responses.create(
            model=_OPENAI_MODEL,
            instructions=_PROMPT,
            input=redacted_text[:MAX_INPUT_CHARS],
            temperature=0,
            max_output_tokens=300,
            text={"format": {"type": "json_schema", "name": "grounded_invoice_ids", "strict": True, "schema": schema}},
        )
        payload = json.loads(_response_text(response))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def apply_grounded_extraction(
    ocr_text: str,
    fields: Dict[str, Any],
    confidence: Dict[str, Any],
    alternatives: Dict[str, Any],
    provider: Optional[Provider] = None,
    force: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Overlay validated AI values for AI_FIELDS. No-op unless enabled (or ``force`` in tests)."""
    if not (force or enabled()) or not (ocr_text or "").strip():
        return fields, confidence, alternatives
    redacted, counts = redact_invoice_text(ocr_text)
    sent = redacted[:MAX_INPUT_CHARS]
    payload = (provider or _openai_provider)(sent)
    meta: Dict[str, Any] = {"redactions": counts, "provider_returned": payload is not None}
    if payload is None:
        alternatives = dict(alternatives or {})
        alternatives["grounded_ai"] = meta
        return fields, confidence, alternatives
    ai_fields, ai_confidence, rejected = validate_ai_fields(ocr_text, sent, payload)
    fields = dict(fields)
    confidence = dict(confidence)
    for key, value in ai_fields.items():
        fields[key] = value
        confidence[key] = ai_confidence[key]
    meta.update({"accepted": sorted(ai_fields), "rejected": rejected})
    alternatives = dict(alternatives or {})
    alternatives["grounded_ai"] = meta
    return fields, confidence, alternatives
