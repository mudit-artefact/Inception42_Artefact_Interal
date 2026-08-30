"""
Works out which PDF page a policy section is actually printed on.

This used to be a guess: any section number greater than or equal to 1.4 was called
page 2. The comparison compared the raw "N.M" as a decimal across documents, so for the
sick leave policy every section from 2.1 upwards was over the threshold and the whole
document was labelled page 2 — which is the diagram page and contains no text at all.
Citation deep links pointed readers at a blank page.

Each policy PDF prints its section headings in its own text, so instead of guessing we
look the section up in the extracted page text.

The two languages have to be looked up differently, and the reason is not obvious.

An English page prints "Section 2.1: ..." and extracts in that order. An Arabic page
prints "القسم 2.1: ..." — but `scripts/generate_policy_pdfs.py` runs every Arabic line
through arabic_reshaper and bidi `get_display` before drawing it, because a PDF stores
glyphs in the order they are painted rather than the order they are read. The extracted
text therefore comes back with the number and the heading word on the same line but in
the opposite order, and `القسم\\s+2\\.1` matches nothing at all.

So the Arabic lookup asks only that the number and the heading word share a line. Do not
"correct" it to the English form: it will match nothing, silently, and every Arabic
citation will fall back to page 1 — which is exactly the defect this replaced.
"""

import re

FALLBACK_PAGE_NUMBER = 1

# The word each language prints before a section number. Kept in step with SECTION_WORD
# in scripts/generate_policy_pdfs.py, which is what puts them on the page.
ENGLISH_SECTION_WORD = "Section"
ARABIC_SECTION_WORD = "القسم"


def _english_heading(section_number: str) -> re.Pattern:
    """"Section 2.1", in the order it is both printed and extracted."""
    return re.compile(rf"{ENGLISH_SECTION_WORD}\s+{re.escape(section_number)}\b")


def _arabic_heading(section_number: str) -> re.Pattern:
    """
    The number and "القسم" on one line, in either order.

    `[^\\n]*` keeps the match inside a single line, so a section number on one line cannot
    pair with a heading word on the next. The lookarounds do the same job as the `\\b` in
    the English pattern: they stop 2.1 matching a page that prints only 2.10.

    A heading that names two numbers — "القسم 2.9: ... (الإصدار 2.8)" — matches either of
    them. That is harmless here because the second number is a version rather than a
    section, so it is never looked up.
    """
    number = re.escape(section_number)
    return re.compile(rf"(?<![\d.]){number}(?![\d])[^\n]*{ARABIC_SECTION_WORD}")


def resolve_pdf_page_number(section_number: str, pdf_page_texts: dict[int, str]) -> int:
    """
    Return the page this section is printed on.

    Falls back to the first page when the section cannot be found, which happens for
    sections that exist in the full Markdown policy but not in the shorter PDF summary.
    """
    if not section_number or not pdf_page_texts:
        return FALLBACK_PAGE_NUMBER

    # English first: it is the cheaper pattern and the larger half of the catalogue.
    for heading in (_english_heading(section_number), _arabic_heading(section_number)):
        for page_number in sorted(pdf_page_texts):
            if heading.search(pdf_page_texts[page_number]):
                return page_number

    return FALLBACK_PAGE_NUMBER
