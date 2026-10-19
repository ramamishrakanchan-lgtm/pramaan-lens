"""
report_pdf.py - Pramaan Lens verification report (PDF)

Pure reportlab. Built-in fonts only. No network calls, so the
"nothing leaves this machine" promise stays true.

Usage (from your Streamlit app):

    from report_pdf import build_report_pdf

    build_report_pdf(
        "report.pdf",
        file_name="IMG-20260525-WA0078.jpg",
        case_id="d4b96e341964",
        sha256="d4b96e34...",
        flags=[{"check": "Metadata", "observation": "...", "severity": "LOW",
                "action": "...", "linked_to": "EXIF"}],
        custody_log=[("2026-10-19 13:16:19", "UPLOAD_SEALED", "IMG-...jpg sha256=..."),
                     ("2026-10-19 13:16:25", "ANALYSED", "1 flags, ocr_words=344")],
    )

Internal values such as "ocr_words" are never printed in the report.
"""
import re
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------
# Look and feel
# --------------------------------------------------------------------------
NAVY = colors.HexColor("#12284C")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D9DEE7")
PANEL = colors.HexColor("#F4F6FA")

# severity -> (strong colour, soft background, plain label)
SEVERITY = {
    "HIGH": (colors.HexColor("#B3261E"), colors.HexColor("#FDECEA"), "High risk"),
    "MEDIUM": (colors.HexColor("#9A5B00"), colors.HexColor("#FFF3DC"), "Medium risk"),
    "LOW": (colors.HexColor("#1B6E35"), colors.HexColor("#E6F4EA"), "Low risk"),
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _styles():
    base = dict(fontName="Helvetica", textColor=INK, leading=13.5, fontSize=9.5)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": "Helvetica-Bold",
                                            "fontSize": 20, "leading": 24, "textColor": NAVY}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": "Helvetica-Bold",
                                      "fontSize": 12, "leading": 15, "textColor": NAVY}),
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8.5, "leading": 11.5,
                                            "textColor": MUTED}),
        "label": ParagraphStyle("label", **{**base, "fontName": "Helvetica-Bold",
                                            "fontSize": 7.5, "leading": 10, "textColor": MUTED}),
        "mono": ParagraphStyle("mono", **{**base, "fontName": "Courier-Bold",
                                          "fontSize": 9, "leading": 12}),
        "mono_s": ParagraphStyle("mono_s", **{**base, "fontName": "Courier",
                                              "fontSize": 8.3, "leading": 11}),
        "card_title": ParagraphStyle("card_title", **{**base, "fontName": "Helvetica-Bold",
                                                      "fontSize": 10.5, "leading": 13}),
        "badge": ParagraphStyle("badge", **{**base, "fontName": "Helvetica-Bold", "fontSize": 8,
                                            "leading": 10, "alignment": TA_CENTER,
                                            "textColor": colors.white}),
        "th": ParagraphStyle("th", **{**base, "fontName": "Helvetica-Bold", "fontSize": 8.5,
                                      "textColor": colors.white}),
        "td": ParagraphStyle("td", **{**base, "fontSize": 9, "leading": 12}),
        "tile_num": ParagraphStyle("tile_num", **{**base, "fontName": "Helvetica-Bold",
                                                  "fontSize": 22, "leading": 26,
                                                  "alignment": TA_CENTER}),
        "tile_lab": ParagraphStyle("tile_lab", **{**base, "fontSize": 8.5, "leading": 11,
                                                  "alignment": TA_CENTER, "textColor": MUTED}),
        "notice": ParagraphStyle("notice", **{**base, "fontSize": 9, "leading": 12.5,
                                              "textColor": colors.HexColor("#5A3E00")}),
        "bullet": ParagraphStyle("bullet", **{**base, "leftIndent": 10, "bulletIndent": 0,
                                              "spaceAfter": 2}),
    }


S = _styles()

# --------------------------------------------------------------------------
# Plain-language helpers
# --------------------------------------------------------------------------
def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


# What a check means, in words a non-technical reader understands.
_MEANINGS = [
    (r"\b(metadata|exif|xmp)\b",
     "Photos normally carry hidden details such as camera model and capture time. "
     "WhatsApp and most chat apps remove these details when an image is forwarded, "
     "so missing metadata is common and is not, by itself, a sign of editing."),
    (r"\b(ela|compression|ui consistency)\b",
     "The tool compared how different parts of the image are compressed. Screenshots "
     "often show uneven compression naturally, so this is a weak signal on its own."),
    (r"\b(date|time|timestamp)\b",
     "The date or time visible in the screenshot was compared with the date you "
     "provided. A difference needs to be explained, but it can have innocent causes "
     "such as time zones or a changed device clock."),
]
_DEFAULT_MEANING = ("This point cannot be settled from the image alone. "
                    "Compare it with the original chat on the original device.")


def _meaning_for(flag):
    if flag.get("meaning"):
        return flag["meaning"]
    text = f"{flag.get('check', '')} {flag.get('observation', '')}".lower()
    for pattern, meaning in _MEANINGS:
        if re.search(pattern, text):
            return meaning
    return _DEFAULT_MEANING


def _clean_detail(text):
    """Remove internal values that mean nothing to a reader."""
    text = re.sub(r",?\s*ocr_words\s*=\s*\d+", "", text or "")
    text = re.sub(r"\s*sha256\s*=\s*[0-9a-fA-F]{64}", "", text)
    return text.strip(" ,;")


def humanize_custody(event, detail, file_name):
    """Turn a raw log line into (event title, plain description)."""
    key = (event or "").strip().upper()
    if key == "UPLOAD_SEALED":
        return ("Screenshot received and sealed",
                f'File "{file_name}" was received. Its SHA-256 fingerprint was recorded '
                "so that any later change to the file can be detected.")
    if key == "ANALYSED":
        m = re.search(r"(\d+)\s+flags?", detail or "")
        if m:
            n = int(m.group(1))
            outcome = f"{_plural(n, 'point was', 'points were')} flagged for verification."
        else:
            outcome = "No points were flagged."
        return ("Automated analysis completed", outcome)
    title = (event or "Event").replace("_", " ").strip().capitalize()
    return (title, _clean_detail(detail) or "-")


def _p(text, style="body"):
    return Paragraph(escape(str(text)), S[style])


def _section(number, title):
    t = Table([[Paragraph(f"{number}. {escape(title)}", S["h2"])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    t.spaceBefore = 12
    t.spaceAfter = 6
    t.keepWithNext = True
    return t

# --------------------------------------------------------------------------
# Page furniture: header band, footer, "Page X of Y"
# --------------------------------------------------------------------------
class _ReportCanvas(canvas.Canvas):
    def __init__(self, *args, case_id="", **kwargs):
        super().__init__(*args, **kwargs)
        self._case_id = case_id
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total):
        self.saveState()
        self.setFillColor(NAVY)
        self.rect(0, PAGE_H - 16 * mm, PAGE_W, 16 * mm, stroke=0, fill=1)
        self.setFillColor(colors.white)
        self.setFont("Helvetica-Bold", 13)
        self.drawString(MARGIN, PAGE_H - 10.5 * mm, "Pramaan Lens")
        self.setFont("Helvetica", 9)
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 10.2 * mm, "Screenshot Verification Report")

        self.setStrokeColor(LINE)
        self.setLineWidth(0.6)
        self.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7.5)
        self.drawString(MARGIN, 9.5 * mm,
                        f"Case ID {self._case_id}   |   Screening aid - not an expert opinion")
        self.drawRightString(PAGE_W - MARGIN, 9.5 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()

# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------
def _notice_box():
    box = Table(
        [[Paragraph(
            "<b>Please read first.</b> This report is a screening aid, not an expert opinion. "
            "It does not declare a screenshot genuine or fake. It lists points that should be "
            "verified on the original device.", S["notice"])]],
        colWidths=[CONTENT_W],
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E8C56B")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#E0A800")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return box


def _case_table(file_name, case_id, generated_at, n_flags):
    rows = [
        ["FILE NAME", file_name],
        ["CASE ID", case_id],
        ["REPORT GENERATED", generated_at],
        ["AUTOMATED RESULT", f"{_plural(n_flags, 'point', 'points')} to verify"],
    ]
    data = [[Paragraph(a, S["label"]), _p(b)] for a, b in rows]
    t = Table(data, colWidths=[40 * mm, CONTENT_W - 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _summary_text(high, med, low):
    total = high + med + low
    if total == 0:
        return ("The automated checks did not raise any points. This does not confirm that "
                "the screenshot is authentic. Verification on the original device is still "
                "recommended.")
    if high or med:
        return (f"The automated checks raised {_plural(total, 'point', 'points')} "
                f"({high} high, {med} medium, {low} low). Please review the high and medium "
                "risk points first (Section 3) and confirm them on the original device.")
    return (f"The automated checks raised no high or medium risk points. "
            f"{_plural(low, 'low-risk observation was', 'low-risk observations were')} noted "
            "for information (Section 3). This does not confirm that the screenshot is "
            "authentic. It only means the automated checks found nothing strongly "
            "suspicious. Verification on the original device is still recommended.")


def _tiles(high, med, low):
    gap = 3 * mm
    w = (CONTENT_W - 2 * gap) / 3

    def tile(count, key):
        fg, bg, label = SEVERITY[key]
        num = Paragraph(str(count), ParagraphStyle("n", parent=S["tile_num"], textColor=fg))
        return [num, Paragraph(label, S["tile_lab"])], bg, fg

    cells, spec = [], []
    for i, (cnt, key) in enumerate(((high, "HIGH"), (med, "MEDIUM"), (low, "LOW"))):
        content, bg, fg = tile(cnt, key)
        col = i * 2
        cells.append(content)
        if i < 2:
            cells.append("")
        spec += [("BACKGROUND", (col, 0), (col, 0), bg),
                 ("LINEABOVE", (col, 0), (col, 0), 2.5, fg)]
    t = Table([cells], colWidths=[w, gap, w, gap, w])
    t.setStyle(TableStyle(spec + [
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _hash_box(sha256):
    t = Table([[Paragraph("SHA-256", S["label"])], [Paragraph(escape(sha256), S["mono"])]],
              colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (0, 0), (0, -1), 3, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
    ]))
    return t


def _flag_card(flag):
    sev = str(flag.get("severity", "LOW")).upper()
    fg, bg, label = SEVERITY.get(sev, SEVERITY["LOW"])
    label_w = 36 * mm

    rows = [[Paragraph(label.upper(), S["badge"]),
             Paragraph(escape(str(flag.get("check", "Check"))), S["card_title"])]]
    for lab, value in (("WHAT WAS FOUND", flag.get("observation")),
                       ("WHAT THIS MEANS", _meaning_for(flag)),
                       ("WHAT TO DO NEXT", flag.get("action")),
                       ("LINKED TO", flag.get("linked_to"))):
        if value:
            rows.append([Paragraph(lab, S["label"]), _p(value)])

    t = Table(rows, colWidths=[label_w, CONTENT_W - label_w])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), bg),
        ("BACKGROUND", (0, 0), (0, 0), fg),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether([t, Spacer(1, 6)])


def _custody_table(custody_log, file_name):
    data = [[Paragraph("TIME", S["th"]), Paragraph("EVENT", S["th"]),
             Paragraph("WHAT HAPPENED", S["th"])]]
    for ts, event, detail in custody_log:
        title, desc = humanize_custody(event, detail, file_name)
        data.append([Paragraph(f'<font name="Courier">{escape(str(ts))}</font>', S["td"]),
                     Paragraph(f"<b>{escape(title)}</b>", S["td"]),
                     _p(desc, "td")])
    t = Table(data, colWidths=[44 * mm, 46 * mm, CONTENT_W - 90 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PANEL]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _part_a(file_name, case_id, sha256):
    rows = [
        ("Hash algorithm", Paragraph("SHA-256", S["td"])),
        ("Hash value", Paragraph(escape(sha256), S["mono_s"])),
        ("File name", _p(file_name, "td")),
        ("Case ID", _p(case_id, "td")),
    ]
    data = [[Paragraph(a.upper(), S["label"]), b] for a, b in rows]
    t = Table(data, colWidths=[38 * mm, CONTENT_W - 38 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _part_b():
    fields = [("Name of expert", 11), ("Qualification and designation", 11),
              ("Organisation", 11), ("Expert's observations", 26),
              ("Place and date", 11), ("Signature and seal", 18)]
    data = [[Paragraph(f.upper(), S["label"]), ""] for f, _ in fields]
    t = Table(data, colWidths=[52 * mm, CONTENT_W - 52 * mm],
              rowHeights=[h * mm for _, h in fields])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t

# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def build_report_pdf(out_path, *, file_name, case_id, sha256, flags, custody_log,
                     generated_at=None):
    """
    flags:       list of dicts with keys check, observation, severity (LOW/MEDIUM/HIGH),
                 action, linked_to. Optional key "meaning" overrides the plain-language text.
    custody_log: list of (timestamp, event_code, detail) tuples.
    """
    flags = list(flags or [])
    custody_log = list(custody_log or [])
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in flags:
        counts[str(f.get("severity", "LOW")).upper()] = counts.get(
            str(f.get("severity", "LOW")).upper(), 0) + 1
    high, med, low = counts["HIGH"], counts["MEDIUM"], counts["LOW"]

    doc = BaseDocTemplate(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=24 * mm, bottomMargin=20 * mm,
        title=f"Pramaan Lens Verification Report - {case_id}",
        author="Pramaan Lens",
        subject="Screenshot verification report (screening aid)",
    )
    frame = Frame(MARGIN, 20 * mm, CONTENT_W, PAGE_H - 44 * mm, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    story = [
        Paragraph("Screenshot Verification Report", S["title"]),
        Spacer(1, 8),
        _notice_box(),
        Spacer(1, 10),
        _case_table(file_name, case_id, generated_at, len(flags)),

        _section(1, "Summary"),
        _tiles(high, med, low),
        Spacer(1, 8),
        Paragraph(escape(_summary_text(high, med, low)), S["body"]),

        _section(2, "File fingerprint (SHA-256)"),
        Paragraph(
            "A SHA-256 value is a digital fingerprint of the file. If even one pixel of the "
            "file changes, the fingerprint changes completely. It was recorded when the file "
            "was uploaded, so anyone can later check that the file has not been altered.",
            S["body"]),
        Spacer(1, 6),
        _hash_box(sha256),
        Spacer(1, 6),
        Paragraph("<b>How to re-check:</b> run one of these on the same file and compare the "
                  "result with the value above.", S["small"]),
        Spacer(1, 2),
        Paragraph("Windows: certutil -hashfile \"" + escape(file_name) + "\" SHA256", S["mono_s"]),
        Paragraph("Linux / macOS: sha256sum \"" + escape(file_name) + "\"", S["mono_s"]),

        _section(3, "Points to verify first"),
    ]

    if flags:
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for f in sorted(flags, key=lambda x: order.get(str(x.get("severity", "LOW")).upper(), 3)):
            story.append(_flag_card(f))
    else:
        story.append(Paragraph("No points were flagged by the automated checks.", S["body"]))

    story += [
        _section(4, "Chain of custody"),
        _custody_table(custody_log, file_name),
        Spacer(1, 3),
        Paragraph("Times are as recorded by the system running Pramaan Lens.", S["small"]),

        _section(5, "Limitations"),
        Paragraph("This report is produced by automated checks and should be read with care.",
                  S["body"]),
        Spacer(1, 3),
    ]
    for line in (
        "It does not declare any screenshot genuine or fake.",
        "A screenshot can only be confirmed by checking the original chat on the original device.",
        "Low-risk points are shown for transparency and are often normal for forwarded images.",
        "The expert section below is intentionally blank and must be completed by a qualified expert.",
    ):
        story.append(Paragraph(escape(line), S["bullet"], bulletText="\u2022"))

    story += [
        CondPageBreak(120 * mm),
        _section(6, "Draft certificate for expert review"),
        Paragraph("<b>Draft for expert review:</b> Bharatiya Sakshya Adhiniyam (BSA) 2023, "
                  "section 63(4).", S["body"]),
        Spacer(1, 8),
        Paragraph("<b>Part A - Hash details</b>", S["body"]),
        Spacer(1, 4),
        _part_a(file_name, case_id, sha256),
        Spacer(1, 12),
        KeepTogether([
            Paragraph("<b>Part B - To be completed and signed by a qualified expert</b>",
                      S["body"]),
            Spacer(1, 4),
            _part_b(),
        ]),
    ]

    doc.build(story, canvasmaker=lambda *a, **k: _ReportCanvas(*a, case_id=case_id, **k))
    return out_path

# --------------------------------------------------------------------------
# Demo: python report_pdf.py  ->  sample_report.pdf
# --------------------------------------------------------------------------
if __name__ == "__main__":
    sha = "d4b96e34196455a265f6353a77d622315c01853396a21cda17d15a238fd03a63"
    name = "IMG-20260525-WA0078.jpg"
    log = [
        ("2026-10-19 13:16:19", "UPLOAD_SEALED", f"{name} sha256={sha}"),
        ("2026-10-19 13:16:25", "ANALYSED", "1 flags, ocr_words=344"),
    ]
    demo_flags = [{
        "check": "Metadata",
        "observation": "No EXIF/XMP found. Forwarding strips metadata, so this is neutral.",
        "severity": "LOW",
        "action": "Request the original file if available.",
        "linked_to": "EXIF",
    }]
    build_report_pdf("sample_report.pdf", file_name=name, case_id=sha[:12], sha256=sha,
                     flags=demo_flags, custody_log=log, generated_at=log[-1][0])
    print("Wrote sample_report.pdf")
