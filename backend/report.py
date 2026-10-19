"""Verification report (PDF) with hash, flags, custody trail and a BSA s.63 Part A draft."""
import io
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LEVEL = {"HIGH": colors.HexColor("#B3342F"), "MEDIUM": colors.HexColor("#C98A1B"), "LOW": colors.HexColor("#4F7A64")}


def build_pdf(result, trail) -> bytes:
    s = getSampleStyleSheet()
    small = s["BodyText"].clone("small", fontSize=8, leading=10)
    P = lambda t: Paragraph(escape(str(t)), small)
    el = [Paragraph("PramaanLens Verification Report", s["Title"]),
          Paragraph("Screening aid, not an expert opinion. It does not declare a screenshot genuine or fake.", s["Italic"]),
          Spacer(1, 10), P(f"File: {result['filename']}"), P(f"Case ID: {result['case_id']}"), P(f"SHA-256: {result['sha256']}"),
          Spacer(1, 10), Paragraph("Risk flags: what to verify first", s["Heading2"])]
    rows = [["Check", "Observation", "Flag", "Action", "Linked to"]]
    for f in result["flags"]:
        link = f"region {f['region']}" if f["region"] else f["field"]
        rows.append([P(f["check"]), P(f["observation"]), P(f["level"]), P(f["action"]), P(link)])
    if len(rows) == 1:
        rows.append([P("-"), P("No rule fired. This is not proof of authenticity."), P("-"), P("Verify on original device"), P("-")])
    t = Table(rows, colWidths=[70, 190, 45, 110, 80], repeatRows=1)
    st = [("GRID", (0, 0), (-1, -1), .4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14283D")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    st += [("TEXTCOLOR", (2, i + 1), (2, i + 1), LEVEL.get(f["level"], colors.black)) for i, f in enumerate(result["flags"])]
    t.setStyle(TableStyle(st))
    el += [t, Spacer(1, 12), Paragraph("Custody log", s["Heading2"])]
    el += [P(f"{ts}  {ev}  {d}") for ts, ev, d in trail]
    el += [Spacer(1, 12), Paragraph("Draft for expert review: BSA 2023, s.63(4), Part A", s["Heading2"]),
           P(f"Hash algorithm: SHA-256. Hash value: {result['sha256']}. Part B must be completed and signed by a qualified expert.")]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=30, rightMargin=30).build(el)
    return buf.getvalue()
