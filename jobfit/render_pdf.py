"""Harvard-style, ATS-friendly resume PDF.

ATS choices: single column, real (selectable) text in reading order, standard
section headings, no tables/images/text boxes/headers/footers, simple bullets,
an embedded serif font when one is available.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import black
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, HRFlowable, KeepTogether, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer)

from .resume import SECTION_TITLES

FONT_CANDIDATES = [
    # (regular, bold, italic, bold-italic)
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf",
     "C:/Windows/Fonts/timesi.ttf", "C:/Windows/Fonts/timesbi.ttf"),
    ("/System/Library/Fonts/Supplemental/Times New Roman.ttf",          # macOS 10.15+
     "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
     "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
     "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf"),
    ("/Library/Fonts/Times New Roman.ttf", "/Library/Fonts/Times New Roman Bold.ttf",  # older macOS
     "/Library/Fonts/Times New Roman Italic.ttf", "/Library/Fonts/Times New Roman Bold Italic.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf"),
]


def _register_font() -> tuple[str, str, str, bool]:
    for paths in FONT_CANDIDATES:
        if all(Path(p).exists() for p in paths):
            names = ("ResumeSerif", "ResumeSerif-Bold", "ResumeSerif-Italic", "ResumeSerif-BoldItalic")
            for n, p in zip(names, paths):
                if n not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(n, p))
            pdfmetrics.registerFontFamily(names[0], normal=names[0], bold=names[1],
                                          italic=names[2], boldItalic=names[3])
            return names[0], names[1], names[2], True
    return "Times-Roman", "Times-Bold", "Times-Italic", False  # built-in fallback


REG, BOLD, ITAL, UNICODE_OK = _register_font()


def _t(text: str) -> str:
    text = str(text or "")
    if not UNICODE_OK:  # built-in Type1 fonts only cover cp1252; transliterate the rest
        out = []
        for ch in text:
            try:
                ch.encode("cp1252")
                out.append(ch)
            except UnicodeEncodeError:
                out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode())
        text = "".join(out)
    return escape(text)


class LeftRight(Flowable):
    """One line: left text and right-aligned text (e.g. company / location)."""

    def __init__(self, left: str, right: str, font: str, size: float, right_font: str | None = None):
        super().__init__()
        self.left, self.right = left, right
        self.font, self.size = font, size
        self.right_font = right_font or font

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.size * 1.25
        return self.width, self.height

    def draw(self):
        c = self.canv
        right_w = pdfmetrics.stringWidth(self.right, self.right_font, self.size)
        left = self.left
        max_left = self.width - right_w - 12
        while left and pdfmetrics.stringWidth(left, self.font, self.size) > max_left:
            left = left[:-1]
        c.setFont(self.font, self.size)
        c.drawString(0, self.size * 0.25, left)
        c.setFont(self.right_font, self.size)
        c.drawRightString(self.width, self.size * 0.25, self.right)


def _plain(text: str) -> str:
    """Text for canvas drawString (no XML escaping, same character policy)."""
    t = _t(text)
    return t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def render_resume_pdf(r: dict, path: Path, page_size: str = "letter") -> None:
    size = 10.5
    styles = {
        "name": ParagraphStyle("name", fontName=BOLD, fontSize=17, leading=20, alignment=TA_CENTER),
        "contact": ParagraphStyle("contact", fontName=REG, fontSize=size, leading=size * 1.3,
                                  alignment=TA_CENTER, spaceAfter=4),
        "heading": ParagraphStyle("heading", fontName=BOLD, fontSize=11, leading=13, spaceBefore=8),
        "body": ParagraphStyle("body", fontName=REG, fontSize=size, leading=size * 1.25),
        "bullet": ParagraphStyle("bullet", fontName=REG, fontSize=size, leading=size * 1.25),
    }

    doc = SimpleDocTemplate(
        str(path), pagesize=A4 if page_size.upper() == "A4" else LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=f"{r['name']} - Resume", author=r["name"], subject="Resume", creator="jobfit",
    )
    story: list = [
        Paragraph(_t(r["name"]), styles["name"]),
        Paragraph(" &nbsp;|&nbsp; ".join(_t(c) for c in r["contact"]), styles["contact"]),
    ]

    def heading(title: str):
        return [Paragraph(_t(title.upper()), styles["heading"]),
                HRFlowable(width="100%", thickness=0.6, color=black, spaceBefore=1, spaceAfter=3)]

    def bullets(items: list[str]):
        if not items:
            return []
        return [ListFlowable(
            [ListItem(Paragraph(_t(b), styles["bullet"]), leftIndent=12, value="•") for b in items],
            bulletType="bullet", start="•", leftIndent=12, bulletFontName=REG, bulletFontSize=size,
        )]

    for section in r["section_order"]:
        block: list = []
        if section == "summary" and r["summary"]:
            block = [Paragraph(_t(r["summary"]), styles["body"])]
        elif section == "experience" and r["experience"]:
            for e in r["experience"]:
                entry = [
                    LeftRight(_plain(e["company"]), _plain(e["location"]), BOLD, size, REG),
                    LeftRight(_plain(e["title"]), _plain(e["dates"]), ITAL, size, REG),
                ] + bullets(e["bullets"]) + [Spacer(1, 4)]
                block.append(KeepTogether(entry[:3]))
                block += entry[3:]
        elif section == "education" and r["education"]:
            for e in r["education"]:
                block += [KeepTogether([
                    LeftRight(_plain(e["institution"]), _plain(e["location"]), BOLD, size, REG),
                    LeftRight(_plain(e["degree"]), _plain(e["dates"]), ITAL, size, REG),
                ] + bullets(e["details"]))] + [Spacer(1, 3)]
        elif section == "certifications" and r["certifications"]:
            for c in r["certifications"]:
                left = c["name"] + (f", {c['issuer']}" if c["issuer"] else "")
                block.append(LeftRight(_plain(left), _plain(c["date"]), REG, size))
        elif section == "projects" and r["projects"]:
            for p in r["projects"]:
                block += [LeftRight(_plain(p["name"]), _plain(p["date"]), BOLD, size, REG)] + \
                         bullets(p["bullets"]) + [Spacer(1, 3)]
        elif section == "skills" and r["skills"]:
            block = [Paragraph(f"<b>{_t(label)}:</b> {_t(', '.join(items))}", styles["body"])
                     for label, items in r["skills"]]
        if block:
            story += heading(SECTION_TITLES[section]) + block

    doc.build(story)
