import re
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from agent import final_state

state = final_state
REPORT = state["report"]
TITLE = state["topic"].title()
SUBTITLES = state["sub_queries"]  # List[str]

# ── layout constants ──────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595 x 842 pt
MARGIN_X       = 50
CONTENT_W      = PAGE_W - 2 * MARGIN_X
BODY_FONT      = "Helvetica"
BODY_SIZE      = 11
LINE_H         = BODY_SIZE + 3   # line height

safe_title = re.sub(r'[\\/*?:"<>|]', "_", TITLE)
fileName = f"{safe_title}.pdf"
pdf = canvas.Canvas(fileName, pagesize=A4)
pdf.setTitle(TITLE)

# ── helpers ───────────────────────────────────────────────────────
def new_page(pdf):
    pdf.showPage()
    return PAGE_H - 50          # top y of new page

def draw_wrapped(pdf, text, x, y, font, size, max_width, color=colors.black):
    """Draw word-wrapped text; returns updated y position, handling page breaks."""
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    lh = size + 3
    for raw_line in text.split("\n"):
        parts = simpleSplit(raw_line if raw_line.strip() else " ", font, size, max_width)
        for part in parts:
            if y < 60:
                y = new_page(pdf)
                pdf.setFont(font, size)
                pdf.setFillColor(color)
            pdf.drawString(x, y, part)
            y -= lh
    return y

# ── TITLE ─────────────────────────────────────────────────────────
y = PAGE_H - 60
pdf.setFont("Helvetica-Bold", 22)
pdf.setFillColor(colors.HexColor("#1a1a2e"))
title_lines = simpleSplit(TITLE, "Helvetica-Bold", 22, CONTENT_W)
for line in title_lines:
    pdf.drawCentredString(PAGE_W / 2, y, line)
    y -= 28

# ── SUBTITLES ─────────────────────────────────────────────────────
y -= 6
pdf.setFont("Helvetica-Oblique", 11)
pdf.setFillColor(colors.HexColor("#444444"))
if isinstance(SUBTITLES, list):
    for idx, sub in enumerate(SUBTITLES, 1):
        sub_text = f"{idx}. {sub}" if not str(sub).startswith(str(idx)) else str(sub)
        sub_lines = simpleSplit(sub_text, "Helvetica-Oblique", 11, CONTENT_W)
        for sl in sub_lines:
            if y < 60:
                y = new_page(pdf)
            pdf.drawString(MARGIN_X, y, sl)
            y -= 15
else:
    y = draw_wrapped(pdf, str(SUBTITLES), MARGIN_X, y,
                     "Helvetica-Oblique", 11, CONTENT_W, colors.HexColor("#444444"))

# ── divider ───────────────────────────────────────────────────────
y -= 8
pdf.setStrokeColor(colors.HexColor("#1a1a2e"))
pdf.setLineWidth(1.2)
pdf.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)
y -= 16

# ── REPORT BODY ───────────────────────────────────────────────────
for raw_line in REPORT.split("\n"):
    line = raw_line.rstrip()

    # section heading: ## or ###
    if line.startswith("### "):
        text  = line[4:].strip()
        font, size, color = "Helvetica-Bold", 12, colors.HexColor("#16213e")
        y -= 4
    elif line.startswith("## "):
        text  = line[3:].strip()
        font, size, color = "Helvetica-Bold", 14, colors.HexColor("#0f3460")
        y -= 8
    elif line.startswith("# "):
        text  = line[2:].strip()
        font, size, color = "Helvetica-Bold", 16, colors.HexColor("#1a1a2e")
        y -= 10
    else:
        # strip markdown bold markers for plain rendering
        text  = line.replace("**", "")
        font, size, color = BODY_FONT, BODY_SIZE, colors.black

    parts = simpleSplit(text if text.strip() else " ", font, size, CONTENT_W)
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    for part in parts:
        if y < 60:
            y = new_page(pdf)
            pdf.setFont(font, size)
            pdf.setFillColor(color)
        pdf.drawString(MARGIN_X, y, part)
        y -= (size + 3)

pdf.save()
print(f"PDF saved as {fileName}")