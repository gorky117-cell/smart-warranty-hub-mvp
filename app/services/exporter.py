from pathlib import Path
from typing import Tuple

from fpdf import FPDF


def export_warranty_txt(summary: str) -> bytes:
    return summary.encode("utf-8")


def export_warranty_html(summary: str) -> bytes:
    html = f"<html><body><pre>{summary}</pre></body></html>"
    return html.encode("utf-8")


def export_warranty_pdf(summary: str, title: str = "Warranty Summary") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=title)
    pdf.ln(4)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, txt=summary)
    # FPDF returns a bytearray when dest="S"; convert to immutable bytes.
    out = pdf.output(dest="S")
    return bytes(out)
