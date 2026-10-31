"""Printable A4 practice papers with embedded, shaped Indic fonts."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from backend.practice_paper import PracticePaper

FONT_DIR = Path(__file__).parent / "assets" / "fonts"


@lru_cache(maxsize=1)
def _register_fonts():
    for suffix in ("", "Devanagari", "Kannada"):
        name = f"NotoSans{suffix}"
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / f"{name}-Regular.ttf")))


def _text(value: str) -> str:
    """Treat generated text literally, and shape each script with a supporting font."""
    original = value
    value = escape(value).replace("\n", "<br/>")
    scripts = [
        (r"[\u0900-\u097f][\u0900-\u097f\u200c\u200d]*", "NotoSansDevanagari"),
        (r"[\u0c80-\u0cff][\u0c80-\u0cff\u200c\u200d]*", "NotoSansKannada"),
    ]
    present = [(pattern, font) for pattern, font in scripts if re.search(pattern, value)]
    # Indic Noto fonts also cover Latin and punctuation. Keep a whole sentence in
    # one font so shaping preserves spaces and punctuation across script boundaries.
    if len(present) == 1 and all(
        char in "\n\r\t" or ord(char) in pdfmetrics.getFont(present[0][1]).face.charToGlyph
        for char in original
    ):
        return f'<font name="{present[0][1]}">{value}</font>'
    for pattern, font in present:
        value = re.sub(pattern, lambda match: f'<font name="{font}">{match.group()}</font>', value)
    return value


def paper_pdf(paper: PracticePaper, *, answers: bool = False) -> bytes:
    """Render an independent student paper or parent answer key entirely in memory."""
    _register_fonts()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=48, leftMargin=48,
        topMargin=44, bottomMargin=48, title=paper.title,
        author="Study Planner",
    )
    body = ParagraphStyle("body", fontName="NotoSans", fontSize=11, leading=19,
                          shaping=1, spaceAfter=8)
    title = ParagraphStyle("title", parent=body, fontSize=19, leading=27, spaceAfter=12)
    meta = ParagraphStyle("meta", parent=body, fontSize=9, leading=15,
                          textColor=colors.HexColor("#475569"))
    label = ParagraphStyle("label", parent=body, fontSize=10, leading=15,
                           textColor=colors.HexColor("#334155"), spaceAfter=5)
    story = [
        Paragraph(_text("ANSWER KEY" if answers else "PRACTICE PAPER"), label),
        Paragraph(_text(paper.title), title),
        Paragraph(_text(f"{paper.subject}  |  {paper.grade}  |  {paper.difficulty}"), meta),
        Paragraph("Topics:", meta),
        *[Paragraph(_text(f"- {topic}"), meta) for topic in paper.topics],
        Paragraph(f"Time: {paper.duration_minutes} minutes  |  Total marks: {len(paper.questions)} (1 per question)", meta),
        HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")), Spacer(1, 14),
    ]
    if not answers:
        story += [Paragraph("Name: _________________________    Date: __________________", body),
                  Paragraph(_text(paper.instructions), body), Spacer(1, 8)]
    for i, question in enumerate(paper.questions, 1):
        block = [Paragraph(f"Question {i}  -  1 mark", label),
                 Paragraph(_text(question.question), body)]
        if len(paper.topics) > 1:
            block.append(Paragraph(_text(f"Topic: {question.topic}"), meta))
        if answers:
            block.append(Paragraph(_text(f"Answer: {question.answer}"), body))
        else:
            for _ in range(2):
                block += [Spacer(1, 15), HRFlowable(width="100%", color=colors.HexColor("#cbd5e1"), thickness=0.5)]
        block.append(Spacer(1, 16))
        story.append(KeepTogether(block))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("NotoSans", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(48, 26, "Study Planner | " + ("Answer key" if answers else "Practice paper"))
        canvas.drawRightString(A4[0] - 48, 26, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
