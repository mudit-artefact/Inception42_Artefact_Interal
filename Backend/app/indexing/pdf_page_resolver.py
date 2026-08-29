"""
Works out which PDF page a policy section is actually printed on.

This used to be a guess: any section number greater than or equal to 1.4 was called
page 2. The comparison compared the raw "N.M" as a decimal across documents, so for the
sick leave policy every section from 2.1 upwards was over the threshold and the whole
document was labelled page 2 — which is the diagram page and contains no text at all.
Citation deep links pointed readers at a blank page.

Each policy PDF prints "Section N.M:" headings in its own text, so instead of guessing we
look the section up in the extracted page text.
"""

import re

FALLBACK_PAGE_NUMBER = 1


def resolve_pdf_page_number(section_number: str, pdf_page_texts: dict[int, str]) -> int:
    """
    Return the page this section is printed on.

    Falls back to the first page when the section cannot be found, which happens for
    sections that exist in the full Markdown policy but not in the shorter PDF summary.
    """
    if not section_number or not pdf_page_texts:
        return FALLBACK_PAGE_NUMBER

    section_heading = re.compile(rf"Section\s+{re.escape(section_number)}\b")
    for page_number in sorted(pdf_page_texts):
        if section_heading.search(pdf_page_texts[page_number]):
            return page_number

    return FALLBACK_PAGE_NUMBER
