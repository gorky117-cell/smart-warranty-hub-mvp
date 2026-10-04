"""Buyer-data redaction applied before any text reaches an AI provider (fix run B1).

`ai_safe(text)` is called at every network boundary to OpenAI, Mistral (chat, terms enrichment,
embeddings/RAG) and Ollama, unconditionally — no flag turns it off. It masks **tokens**, not whole
lines, and only **buyer** details:

- the buyer block: a "Bill to / Ship to / Buyer / Customer / Consignee / Recipient / Deliver to /
  Billing|Shipping address / Name" label and up to 5 following lines (stops at a blank line, a seller,
  invoice, item/table, product or warranty line). Values are masked, labels kept;
- buyer phone numbers, e-mail addresses and GSTINs: on buyer-labelled lines and in the buyer block;
  outside it phones/e-mails are masked unless the line is a seller/support line, or the invoice has a
  buyer label and the line sits in the seller header above it;
- `user=` / `user_id=` / `username=` values in event documents (usernames can be e-mail addresses).

Seller name, address, GSTIN and phone are kept.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

REDACTED = "[REDACTED]"

_BUYER_LABEL_RE = re.compile(
    r"^(?P<label>\s*(?:bill(?:ed)?\s*to|ship(?:ped)?\s*to|sold\s*to|deliver(?:y|ed)?\s*to|"
    r"buyer(?:'s)?(?:\s*(?:name|details|address))?|consignee|recipient|"
    r"customer(?!\s*care)(?:\s*(?:name|details|address))?|billing\s*address|shipping\s*address|"
    r"delivery\s*address|name)\b\s*[:\-]?\s*)(?P<value>.*)$",
    re.IGNORECASE,
)
_BUYER_CUE_RE = re.compile(
    r"\b(bill(?:ed)?\s*to|ship(?:ped)?\s*to|buyer|consignee|recipient|customer(?!\s*care)|deliver(?:y)?\s*to)\b",
    re.IGNORECASE,
)
_SELLER_CUE_RE = re.compile(
    r"\b(sold\s*by|seller|store|retail|mall|dealer|distributor|enterprises|traders|agencies|pvt|private\s+limited|"
    r"ltd|llp|outlet|showroom|customer\s*care|helpline|toll\s*free|support|service\s*cent(?:er|re))\b",
    re.IGNORECASE,
)
_BLOCK_END_RE = re.compile(
    r"\b(invoice|inv\b|order|date|item|description|sl\b|s\.?\s*no|qty|quantity|hsn|sac|product|model|serial|"
    r"imei|warranty|amount|total|rate|sold\s*by|seller|place\s+of\s+supply)\b",
    re.IGNORECASE,
)
_CONTACT_LABEL_RE = re.compile(r"^\s*(phone|mobile|mob|tel|telephone|contact|cell|e-?mail|gstin|gst\s*no|state)\b", re.IGNORECASE)
_INLINE_LABEL_RE = re.compile(r"^(\s*[A-Za-z][A-Za-z .]{1,24}\s*[:\-]\s*)(.*)$")
# A buyer label in the middle of a line (OCR or line joining merged rows): "... TAX INVOICE Bill To: Asha ...".
# Needs ":" or "-" after the label; bare "Name" is not used here ("Product Name:" is not a buyer).
_MID_BUYER_LABEL_RE = re.compile(
    r"\s(?:bill(?:ed)?\s*to|ship(?:ped)?\s*to|sold\s*to|deliver(?:y|ed)?\s*to|buyer(?:'s)?(?:\s*(?:name|details|address))?|"
    r"consignee|customer(?!\s*care)(?:\s*(?:name|details|address))?|billing\s*address|shipping\s*address|delivery\s*address)"
    r"\s*[:\-]",
    re.IGNORECASE,
)
_ITEM_ROW_START_RE = re.compile(r"\s\d{1,3}\s+[A-Z]")


def _mid_value_end(rest: str) -> int:
    """Where the buyer value inside such a line ends: an invoice keyword, or an item row whose text names a
    product or brand ("1 Samsung 55 inch TV"); a house number ("4 MG Road") is not an item row."""
    ends = [m.start() for m in _BLOCK_END_RE.finditer(rest)]
    try:
        from .ingestion import _has_product_signal, _looks_like_address_text

        for m in _ITEM_ROW_START_RE.finditer(rest):
            window = rest[m.start(): m.start() + 60]
            if _has_product_signal(window) and not _looks_like_address_text(window):
                ends.append(m.start())
                break
    except Exception:  # pragma: no cover - ingestion import failure: keyword ends only
        pass
    return min(ends) if ends else len(rest)


def _mask_mid_line_buyer(line: str, counts: Dict[str, int]) -> str:
    label = _MID_BUYER_LABEL_RE.search(line)
    if not label:
        return line
    rest = line[label.end():]
    end = _mid_value_end(rest)
    if not rest[:end].strip():
        return line
    counts["buyer_values"] += 1
    tail = rest[end:].strip()
    return f"{line[:label.end()]} {REDACTED}" + (f" {tail}" if tail else "")

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RE = re.compile(r"(?<![\w/])(?:\+?91[\s\-]?)?(?:0\d{2,4}[\s\-]?\d{6,8}|[6-9]\d{4}[\s\-]?\d{5})(?![\w/])")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b", re.IGNORECASE)
_USER_FIELD_RE = re.compile(r"\b(user(?:_id|name)?)=(\S+)", re.IGNORECASE)


def _mask_tokens(line: str, counts: Dict[str, int], *, gstin: bool) -> str:
    line, n = EMAIL_RE.subn(REDACTED, line)
    counts["emails"] += n
    line, n = PHONE_RE.subn(REDACTED, line)
    counts["phones"] += n
    if gstin:
        line, n = GSTIN_RE.subn(REDACTED, line)
        counts["gstins"] += n
    return line


def _ends_buyer_block(line: str) -> bool:
    """A product/table line ends the buyer block; an address-like line never does."""
    try:
        from .ingestion import _has_product_signal, _looks_like_address_text

        if _looks_like_address_text(line) or _CONTACT_LABEL_RE.match(line):
            return False
        return bool(_BLOCK_END_RE.search(line)) or _has_product_signal(line)
    except Exception:  # pragma: no cover - ingestion import failure must not disable redaction
        return bool(_BLOCK_END_RE.search(line))


def redact_text(text: str) -> Tuple[str, Dict[str, int]]:
    """Mask buyer details in ``text``. Returns (redacted_text, counts)."""
    counts = {"buyer_values": 0, "emails": 0, "phones": 0, "gstins": 0, "user_ids": 0}
    if not text:
        return text or "", counts
    text, n = _USER_FIELD_RE.subn(lambda m: f"{m.group(1)}={REDACTED}", text)
    counts["user_ids"] += n
    lines = text.splitlines()
    has_buyer_label = any(_BUYER_LABEL_RE.match(line) for line in lines)
    first_buyer = next((i for i, line in enumerate(lines) if _BUYER_LABEL_RE.match(line)), len(lines))
    out: List[str] = []
    block = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        label = _BUYER_LABEL_RE.match(line)
        if label:
            value = label.group("value").strip()
            if value:
                counts["buyer_values"] += 1
                out.append(f"{label.group('label').rstrip()} {REDACTED}")
            else:
                out.append(line)
            block = 5
            continue
        if block and stripped and not _ends_buyer_block(stripped):
            inline = _INLINE_LABEL_RE.match(line)
            out.append(f"{inline.group(1).rstrip()} {REDACTED}" if inline else REDACTED)
            counts["buyer_values"] += 1
            block -= 1
            continue
        block = 0
        if _BUYER_CUE_RE.search(line):
            out.append(_mask_tokens(_mask_mid_line_buyer(line, counts), counts, gstin=True))
        elif _SELLER_CUE_RE.search(line) or (has_buyer_label and i < first_buyer):
            out.append(line)  # seller header / support line: keep as is
        else:
            out.append(_mask_tokens(line, counts, gstin=False))
    return "\n".join(out), counts


def ai_safe(text: str) -> str:
    """Redacted copy of ``text`` for sending to an AI provider."""
    return redact_text(text)[0]
