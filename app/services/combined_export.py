"""One PDF for a claim: the warranty summary page followed by the original invoice.

Built in memory when the owner asks for it and never stored. Options:
- include_invoice: append the owner's latest invoice from "My documents" (PDF pages, a photo or a text file).
- hide_address: black out the customer's address block (the lines under "Bill to", "Ship to", "Billing /
  Shipping / Delivery address", "Customer", "Buyer" and phone numbers in that block). Uses the PDF's text
  layer, or OCR for photos and scanned pages. When no address block can be found on an invoice, the PDF is
  not made with that invoice and the caller says so - we never claim an address was hidden when it was not.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional, Tuple

# Labels that start the customer's block. Seller blocks ("Sold by", "Seller") are left as printed.
_ADDRESS_LABEL = re.compile(
    r"^\s*(?:bill(?:ing)?\s*(?:to|address)|ship(?:ping)?\s*(?:to|address)|delivery\s*address|deliver\s*to|"
    r"customer(?:\s*(?:name|address|details))?|buyer(?:\s*(?:name|address|details))?|consignee|recipient\s*address)\b",
    re.IGNORECASE,
)
# A line that starts another section ends the address block.
_SECTION_END = re.compile(
    r"^\s*(?:invoice|order|sold\s*by|seller|gstin?\b|pan\b|place\s*of|state\s*code|sl\.?\s*no|s\.?\s*no|description|"
    r"item|qty|hsn|total|amount|date|payment|terms|warranty)\b",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b")
_BLOCK_LINES = 6

Line = Tuple[str, Tuple[float, float, float, float]]  # text, (x0, y0, x1, y1)


class AddressNotFound(Exception):
    """No customer address block could be found on the invoice."""


def address_boxes(lines: List[Line]) -> List[Tuple[float, float, float, float]]:
    """Boxes to black out: each customer block (label line + up to 6 lines below it in the same column)
    and any phone number line inside it."""
    boxes = []
    ordered = sorted(lines, key=lambda item: (round(item[1][1]), item[1][0]))
    for i, (text, box) in enumerate(ordered):
        if not _ADDRESS_LABEL.match(text):
            continue
        boxes.append(box)
        x0, _y0, x1, y1 = box
        height = max(box[3] - box[1], 1.0)
        last_y = y1
        taken = 0
        for other_text, other in ordered[i + 1:]:
            if other[1] - last_y > 2.5 * height:
                break  # a gap: the block is over
            if other[2] < x0 - 5 or other[0] > max(x1, x0 + 250):
                continue  # another column (e.g. the seller's block printed beside it)
            if _SECTION_END.match(other_text) or (taken and _ADDRESS_LABEL.match(other_text)):
                break
            boxes.append(other)
            last_y = other[3]
            taken += 1
            if taken >= _BLOCK_LINES:
                break
    return boxes


def _pdf_lines(page) -> List[Line]:
    out: List[Line] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if text:
                out.append((text, tuple(line["bbox"])))
    return out


def _ocr_lines(image) -> List[Line]:
    """Line boxes from OCR (pytesseract); empty when OCR is not available."""
    try:
        import pytesseract  # type: ignore

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    grouped = {}
    for i, word in enumerate(data.get("text", [])):
        if not str(word).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        text, (x0, y0, x1, y1) = grouped.get(key, ("", (x, y, x + w, y + h)))
        grouped[key] = ((text + " " + word).strip(), (min(x0, x), min(y0, y), max(x1, x + w), max(y1, y + h)))
    return list(grouped.values())


def _redact_image_bytes(data: bytes) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.open(io.BytesIO(data)).convert("RGB")
    boxes = address_boxes(_ocr_lines(image))
    if not boxes:
        raise AddressNotFound()
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in boxes:
        draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill="black")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _image_page(target, png: bytes) -> None:
    import fitz

    pix = fitz.Pixmap(png)
    page = target.new_page(width=595, height=842)  # A4 in points
    scale = min(555 / pix.width, 802 / pix.height)
    page.insert_image(fitz.Rect(20, 20, 20 + pix.width * scale, 20 + pix.height * scale), stream=png)


def _append_pdf(target, data: bytes, hide_address: bool) -> None:
    import fitz  # PyMuPDF

    source = fitz.open(stream=data, filetype="pdf")
    if not hide_address:
        target.insert_pdf(source)
        return
    found = False
    pages = []  # ("pdf", index) or ("png", bytes)
    for index, page in enumerate(source):
        lines = _pdf_lines(page)
        if lines:
            boxes = address_boxes(lines)
            for box in boxes:
                page.add_redact_annot(fitz.Rect(*box), fill=(0, 0, 0))
            if boxes:
                page.apply_redactions()  # removes the text underneath, not just a black box on top
                found = True
            pages.append(("pdf", index))
        else:  # a scanned page: OCR its image and black out the block on a copy of the image
            png = page.get_pixmap(dpi=200).tobytes("png")
            try:
                png = _redact_image_bytes(png)
                found = True
            except AddressNotFound:
                pass
            pages.append(("png", png))
    if not found:
        raise AddressNotFound()
    for kind, value in pages:
        if kind == "pdf":
            target.insert_pdf(source, from_page=value, to_page=value)
        else:
            _image_page(target, value)


def _append_image(target, data: bytes, hide_address: bool) -> None:
    from PIL import Image

    if hide_address:
        png = _redact_image_bytes(data)
    else:
        out = io.BytesIO()
        Image.open(io.BytesIO(data)).convert("RGB").save(out, format="PNG")
        png = out.getvalue()
    _image_page(target, png)


def _append_text(target, data: bytes, hide_address: bool) -> None:
    import fitz

    lines = data.decode("utf-8", errors="replace").splitlines()
    if hide_address:
        # One "line box" per text line, all in one column, so the same block rule applies.
        boxed = [(line, (0.0, float(i * 10), 300.0, float(i * 10 + 8))) for i, line in enumerate(lines)]
        hidden_tops = {box[1] for box in address_boxes([b for b in boxed if b[0].strip()])}
        if not hidden_tops:
            raise AddressNotFound()
        lines = ["[hidden]" if float(i * 10) in hidden_tops else line for i, line in enumerate(lines)]
    page = target.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(36, 36, 559, 806), "\n".join(lines), fontsize=9)


def build(summary_pdf: bytes, invoice: Optional[Tuple[bytes, str]], *, hide_address: bool) -> bytes:
    """summary_pdf followed by the invoice (bytes, content type); raises AddressNotFound."""
    import fitz

    out = fitz.open(stream=summary_pdf, filetype="pdf")
    if invoice:
        data, content_type = invoice
        if content_type == "application/pdf":
            _append_pdf(out, data, hide_address)
        elif content_type.startswith("image/"):
            _append_image(out, data, hide_address)
        elif content_type == "text/plain":
            _append_text(out, data, hide_address)
    return out.tobytes(garbage=3, deflate=True)
