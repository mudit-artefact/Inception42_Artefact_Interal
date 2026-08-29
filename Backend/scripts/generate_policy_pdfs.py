"""
Renders every policy PDF from its Markdown source.

This script used to hand-write the policy text in Python, independently of
`data/policies_en/*.md`. The two drifted badly: the Markdown said a medical certificate
was needed from the third consecutive day and the PDF said the fourth, the Markdown
scored the Bradford Factor against one set of bands and the PDF against another, and the
two numbered their sections differently. Because `pdf_page_resolver` looks a section up
in the *PDF* text, a citation built from the Markdown deep-linked the reader to a page
stating something else.

There is now one source of truth. The Markdown is the policy; the PDF is a rendering of
it. Nothing here invents content.

Arabic is rendered with an embedded font, reshaped, and reordered for display. Without
all three, ReportLab silently substitutes its not-def glyph in ZapfDingbats — which is
how every Arabic PDF in this project came to contain no Arabic at all.

    python scripts/generate_policy_pdfs.py            # every language
    python scripts/generate_policy_pdfs.py --language ar
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BACKEND = Path(__file__).resolve().parent.parent
FONT_FILE = BACKEND / "data" / "fonts" / "NotoNaskhArabic-Regular.ttf"
ARABIC_FONT = "NotoNaskh"

BRAND = colors.HexColor("#1F3864")
RULE = colors.HexColor("#B4C6E7")

# The word each language prints before a section number. `pdf_page_resolver` looks for
# one of these followed by the number, which is how a citation finds its page.
SECTION_WORD = {"en": "Section", "ar": "القسم"}


@dataclass(frozen=True)
class Block:
    """One rendered element of a policy: a heading, a paragraph, or a table."""

    kind: str  # "h1" | "h2" | "h3" | "para" | "table" | "rule"
    text: str = ""
    rows: list[list[str]] | None = None


def parse_markdown(markdown: str) -> list[Block]:
    """Turn a policy's Markdown into the blocks the renderer draws. No interpretation."""
    blocks: list[Block] = []
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            blocks.append(Block("table", rows=table_rows))
            table_rows = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells):
                continue  # the |---|---| separator row
            table_rows.append(cells)
            continue
        flush_table()

        if not line:
            continue
        if line.startswith("### "):
            blocks.append(Block("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(Block("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(Block("h1", line[2:]))
        elif line.startswith("---"):
            blocks.append(Block("rule"))
        elif line.startswith("- "):
            blocks.append(Block("para", "•  " + line[2:]))
        else:
            blocks.append(Block("para", line))

    flush_table()
    return blocks


def as_rich_text(text: str, language: str) -> str:
    """
    Markdown emphasis into ReportLab markup, and Arabic shaped for display.

    Arabic gets no inline markup. Reordering a line for display moves every character,
    including the characters of any tag sitting inside it — `<b>` comes back as `<b/>`
    and the paragraph fails to parse. Emphasis within an Arabic sentence is therefore
    dropped rather than corrupted; headings and table headers still carry weight,
    because that comes from the paragraph style and never enters the text.
    """
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if language == "ar":
        return shape_arabic(re.sub(r"\*{1,3}", "", text))

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)


def shape_arabic(text: str) -> str:
    """
    Join the letters, then lay them out right to left.

    Both steps are required and in this order. Arabic letters change shape according to
    their neighbours, and a PDF stores glyphs in the order they are drawn, not the order
    they are read.
    """
    return get_display(arabic_reshaper.reshape(text))


def heading_for_pdf(heading: str, language: str) -> str:
    """
    `### 1.5 Carry-Over` becomes `Section 1.5: Carry-Over`.

    The section word and number must appear together in the rendered text: it is how
    `pdf_page_resolver.resolve_pdf_page_number` finds which page to cite.
    """
    match = re.match(r"^(\d+\.\d+)\s+(.*)$", heading)
    if not match:
        return heading
    number, title = match.groups()
    return f"{SECTION_WORD[language]} {number}: {title}"


def build_styles(language: str) -> dict[str, ParagraphStyle]:
    """Paragraph styles for one language, right-aligned and Arabic-fonted when needed."""
    base = getSampleStyleSheet()
    is_arabic = language == "ar"
    body_font = ARABIC_FONT if is_arabic else "Helvetica"
    bold_font = ARABIC_FONT if is_arabic else "Helvetica-Bold"
    alignment = TA_RIGHT if is_arabic else TA_JUSTIFY

    return {
        "h1": ParagraphStyle("h1", parent=base["Title"], fontName=bold_font,
                             fontSize=16, textColor=BRAND, alignment=alignment,
                             spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading1"], fontName=bold_font,
                             fontSize=13, textColor=BRAND, alignment=alignment,
                             spaceBefore=6, spaceAfter=8),
        "h3": ParagraphStyle("h3", parent=base["Heading2"], fontName=bold_font,
                             fontSize=11, textColor=BRAND, alignment=alignment,
                             spaceBefore=12, spaceAfter=5),
        "para": ParagraphStyle("para", parent=base["BodyText"], fontName=body_font,
                               fontSize=9, leading=14, alignment=alignment,
                               spaceAfter=5),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontName=body_font,
                               fontSize=8, leading=11, alignment=alignment),
        "cellhead": ParagraphStyle("cellhead", parent=base["BodyText"], fontName=bold_font,
                                   fontSize=8, leading=11, alignment=alignment),
    }


def render_table(rows: list[list[str]], styles: dict, language: str) -> Table:
    """A policy table, header row shaded, wrapped so long cells do not overflow."""
    header, *body = rows
    width = (A4[0] - 40 * mm) / max(len(header), 1)

    data = [[Paragraph(as_rich_text(cell, language), styles["cellhead"]) for cell in header]]
    data += [
        [Paragraph(as_rich_text(cell, language), styles["cell"]) for cell in row]
        for row in body
    ]
    if language == "ar":
        data = [list(reversed(row)) for row in data]

    table = Table(data, colWidths=[width] * len(header), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), RULE),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8EA9DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_policy(markdown_path: Path, pdf_path: Path, language: str) -> int:
    """Render one policy. Returns the page count."""
    styles = build_styles(language)
    story = []

    for block in parse_markdown(markdown_path.read_text(encoding="utf-8")):
        if block.kind == "table":
            story.append(Spacer(1, 3))
            story.append(render_table(block.rows, styles, language))
            story.append(Spacer(1, 7))
        elif block.kind == "rule":
            story.append(Spacer(1, 3))
            story.append(HRFlowable(width="100%", thickness=0.4, color=RULE))
            story.append(Spacer(1, 3))
        elif block.kind == "h3":
            story.append(Paragraph(
                as_rich_text(heading_for_pdf(block.text, language), language), styles["h3"]
            ))
        else:
            story.append(Paragraph(as_rich_text(block.text, language), styles[block.kind]))

    document = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=markdown_path.stem,
    )
    document.build(story, onFirstPage=_stamp_page, onLaterPages=_stamp_page)

    import pymupdf
    with pymupdf.open(str(pdf_path)) as rendered:
        return rendered.page_count


def _stamp_page(canvas, document) -> None:
    """The confidentiality footer, on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#7F7F7F"))
    canvas.drawString(20 * mm, 10 * mm, "Confidential — Internal Use Only | HC Services UAE")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=["en", "ar", "all"], default="all")
    arguments = parser.parse_args()

    if FONT_FILE.exists():
        pdfmetrics.registerFont(TTFont(ARABIC_FONT, str(FONT_FILE)))
    elif arguments.language in ("ar", "all"):
        print(f"Arabic needs an embedded font at {FONT_FILE}. Without it the text is "
              f"silently replaced with dingbats. See the module docstring.")
        return 1

    languages = ["en", "ar"] if arguments.language == "all" else [arguments.language]
    written = 0

    for language in languages:
        source_directory = BACKEND / "data" / f"policies_{language}"
        output_directory = BACKEND / "data" / "policies_pdf"
        output_directory.mkdir(parents=True, exist_ok=True)

        if not source_directory.exists():
            print(f"  no source for '{language}' at {source_directory}, skipping")
            continue

        for markdown_path in sorted(source_directory.glob("*.md")):
            # Names the existing catalogue already points at: "..._policy.pdf" for
            # English, "..._ar.pdf" for Arabic.
            suffix = "_ar" if language == "ar" else "_policy"
            pdf_path = output_directory / f"{markdown_path.stem}{suffix}.pdf"
            pages = render_policy(markdown_path, pdf_path, language)
            print(f"  {language}  {markdown_path.name:28} -> {pdf_path.name:34} {pages} pages")
            written += 1

    print(f"\n{written} PDFs rendered from Markdown.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
