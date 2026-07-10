from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import date
from pathlib import Path

out = Path(__file__).resolve().parents[1] / "docs" / "OEM_Intelligence_Flow_Simple.pdf"
c = canvas.Canvas(str(out), pagesize=A4)
width, height = A4

y = height - 2*cm

c.setFont("Helvetica-Bold", 18)
c.drawString(2*cm, y, "Smart Warranty Hub: Easy OEM Intelligence Flow")

y -= 0.8*cm
c.setFont("Helvetica", 10)
c.drawString(2*cm, y, f"Prepared on: {date.today().isoformat()}")

y -= 1.0*cm
c.setFont("Helvetica-Bold", 13)
c.drawString(2*cm, y, "1) What data is used")

y -= 0.6*cm
c.setFont("Helvetica", 11)
items1 = [
    "- User invoice and product details",
    "- OEM issue feed and official updates",
    "- Peer web reviews and sentiment trends",
    "- User behavior and usage signals",
    "- Region policies (country/market rules)",
]
for it in items1:
    c.drawString(2.3*cm, y, it)
    y -= 0.5*cm

y -= 0.2*cm
c.setFont("Helvetica-Bold", 13)
c.drawString(2*cm, y, "2) How prediction works (simple)")

y -= 0.6*cm
c.setFont("Helvetica", 11)
items2 = [
    "Step A: System reads invoice and warranty terms.",
    "Step B: It adds OEM signals, peer web signals, behavior, and region rules.",
    "Step C: AI risk engine creates risk score + early warning forecast.",
    "Step D: User gets preventive guidance; OEM gets dashboard insights.",
]
for it in items2:
    c.drawString(2.3*cm, y, it)
    y -= 0.5*cm

y -= 0.2*cm
c.setFont("Helvetica-Bold", 13)
c.drawString(2*cm, y, "3) OEM action cycle")

y -= 0.6*cm
c.setFont("Helvetica", 11)
items3 = [
    "- Weekly analysis: check trends and risk movement.",
    "- Monthly dispatch: send recommendation only if signal is strong.",
    "- If signal is weak: do not spam user; notify OEM as 'not conclusive'.",
    "- All actions are logged for trace and KPI tracking.",
]
for it in items3:
    c.drawString(2.3*cm, y, it)
    y -= 0.5*cm

y -= 0.2*cm
c.setFont("Helvetica-Bold", 13)
c.drawString(2*cm, y, "4) Charts OEM can understand quickly")

y -= 0.6*cm
c.setFont("Helvetica", 11)
items4 = [
    "- Risk Distribution Chart (low / medium / high)",
    "- Forecast Trend Chart (future risk direction)",
    "- Behavior Snapshot Chart (care / responsiveness)",
    "- Top Peer Keywords and Issues panel",
]
for it in items4:
    c.drawString(2.3*cm, y, it)
    y -= 0.5*cm

y -= 0.2*cm
c.setFont("Helvetica-Bold", 13)
c.drawString(2*cm, y, "5) One-line summary for OEM")

y -= 0.6*cm
c.setFont("Helvetica-Oblique", 11)
summary = "We combine user, OEM, web-peer, behavior, and region signals to predict issues early and trigger safe, timed OEM actions."
c.drawString(2.3*cm, y, summary)

y -= 1.0*cm
c.setFont("Helvetica", 9)
c.drawString(2*cm, y, "Source reference: MEMORY.md, OEM dashboard, OEM dispatch docs.")

c.save()
print(out)
