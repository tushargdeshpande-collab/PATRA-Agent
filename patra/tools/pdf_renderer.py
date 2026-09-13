from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

def render_resume_pdf(markdown: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ResumeH1", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, textColor=HexColor("#12304A"), spaceAfter=5))
    styles.add(ParagraphStyle(name="ResumeH2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, textColor=HexColor("#155E75"), spaceBefore=9, spaceAfter=4))
    styles.add(ParagraphStyle(name="ResumeH3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=9.5, spaceBefore=5, spaceAfter=2))
    styles.add(ParagraphStyle(name="ResumeBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.7, leading=11.2, spaceAfter=3))
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=14*mm, bottomMargin=14*mm, title="PATRA verified role-specific resume")
    story = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 2.5))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], styles["ResumeH1"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:].upper(), styles["ResumeH2"]))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], styles["ResumeH3"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["ResumeBody"]))
        else:
            story.append(Paragraph(line, styles["ResumeBody"]))
    doc.build(story)
    return output_path
