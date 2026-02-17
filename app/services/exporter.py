from pathlib import Path
from typing import Tuple

from fpdf import FPDF


def export_warranty_txt(summary: str) -> bytes:
    return summary.encode("utf-8")


def export_warranty_html(summary: str) -> bytes:
    html = f"<html><body><pre>{summary}</pre></body></html>"
    return html.encode("utf-8")


def _pdf_safe_text(text: str) -> str:
    # FPDF core fonts are Latin-1; replace unsupported chars instead of failing with 500.
    return (text or "").encode("latin-1", errors="replace").decode("latin-1")


def export_warranty_pdf(summary: str, title: str = "Warranty Summary") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=_pdf_safe_text(title))
    pdf.ln(4)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, txt=_pdf_safe_text(summary))
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", errors="replace")
    return bytes(out)
