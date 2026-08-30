"""
Defect 7: policy sections were assigned to the wrong PDF page.

The old rule labelled any section numbered 1.4 or higher as page 2. It compared the raw
"N.M" as a decimal without regard to which document it came from, so for every policy
after the first, all sections cleared the threshold and the whole document was labelled
page 2 — which for these documents is the diagram page and holds no text at all.
"""

from pathlib import Path

import pytest

from app.indexing.pdf_page_resolver import resolve_pdf_page_number
from app.indexing.policy_document_reader import read_pdf_page_texts

PDF_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "data" / "policies_pdf"


def test_a_section_is_found_on_the_page_that_prints_it():
    page_texts = {1: "Section 2.1: Notification\nSection 2.2: Certificates", 2: "Section 2.9: Appeals"}

    assert resolve_pdf_page_number("2.1", page_texts) == 1
    assert resolve_pdf_page_number("2.2", page_texts) == 1
    assert resolve_pdf_page_number("2.9", page_texts) == 2


def test_an_unknown_section_falls_back_to_the_first_page():
    """Sections that exist in the full Markdown but not in the shorter PDF summary."""
    page_texts = {1: "Section 1.1: Entitlement"}

    assert resolve_pdf_page_number("1.7", page_texts) == 1


def test_a_missing_section_number_falls_back_to_the_first_page():
    assert resolve_pdf_page_number("", {1: "anything"}) == 1
    assert resolve_pdf_page_number("1.1", {}) == 1


def test_section_numbers_are_not_matched_by_prefix():
    """Section 2.1 must not match a page that only prints Section 2.10."""
    page_texts = {1: "Section 2.10: Appeals", 2: "Section 2.1: Notification"}

    assert resolve_pdf_page_number("2.1", page_texts) == 2


def test_every_section_resolves_to_the_page_it_is_actually_printed_on():
    """
    The defect, measured against the real document.

    Sections used to collapse onto one page: the PDF was a short hand-written summary
    carrying only the first few sections, so everything after them fell back to page 1.
    The PDF is rendered from the Markdown now, so every section is really in it, and a
    citation deep-links to the page the reader needs.
    """
    page_texts = read_pdf_page_texts(PDF_DIRECTORY / "02_sick_leave_policy.pdf")

    resolved_pages = {
        section_number: resolve_pdf_page_number(section_number, page_texts)
        for section_number in ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.9"]
    }

    assert len(set(resolved_pages.values())) > 1, (
        f"every section resolved to the same page, which means the PDF no longer "
        f"contains the sections being cited: {resolved_pages}"
    )
    assert resolved_pages["2.9"] >= resolved_pages["2.1"], (
        f"the superseded appendix is printed after the opening sections: {resolved_pages}"
    )


def test_an_arabic_heading_is_found_although_it_extracts_reversed():
    """
    An Arabic PDF prints "القسم 2.1: ..." but extracts with the number and the heading
    word the other way round, because the line is reordered for display before it is
    drawn. Matching the English form against it finds nothing.
    """
    page_texts = {1: ": نطاق السياسة2.1 القسم", 2: ": المرض طويل الأمد2.5 القسم"}

    assert resolve_pdf_page_number("2.1", page_texts) == 1
    assert resolve_pdf_page_number("2.5", page_texts) == 2


def test_an_arabic_section_number_is_not_matched_by_prefix():
    """2.1 must not match a page that only prints 2.10, in either language."""
    page_texts = {1: ": الاستئناف2.10 القسم", 2: ": الإخطار2.1 القسم"}

    assert resolve_pdf_page_number("2.1", page_texts) == 2


def test_the_number_and_the_heading_word_must_share_a_line():
    """
    Otherwise a section number anywhere on the page pairs with the heading word of a
    different section, and every section resolves to whichever page mentions it first.
    """
    page_texts = {1: "القسم\n2.1", 2: ": نطاق السياسة2.1 القسم"}

    assert resolve_pdf_page_number("2.1", page_texts) == 2


@pytest.mark.parametrize(
    "pdf_name, section_numbers",
    [
        ("01_annual_leave_ar.pdf", ["1.0", "1.2", "1.5", "1.9"]),
        ("02_sick_leave_ar.pdf", ["2.0", "2.3", "2.6", "2.9"]),
        ("03_probation_ar.pdf", ["3.0", "3.3", "3.5", "3.7"]),
        ("04_remote_work_ar.pdf", ["4.0", "4.3", "4.6", "4.9"]),
        ("05_expense_claims_ar.pdf", ["5.0", "5.3", "5.7", "5.9"]),
    ],
)
def test_arabic_sections_do_not_all_collapse_onto_page_one(pdf_name, section_numbers):
    """
    The defect this file did not catch the first time.

    Every Arabic passage in the index resolved to page 1 — all 46 of them — because the
    lookup only knew the English heading word. The English document was the only one
    measured here, so nothing failed. An Arabic citation deep-linked the reader to page 1
    whatever it was about, which for an employee checking their own sick pay is a link
    that cannot be followed.
    """
    page_texts = read_pdf_page_texts(PDF_DIRECTORY / pdf_name)
    assert page_texts, f"{pdf_name} could not be read"

    resolved = {
        section_number: resolve_pdf_page_number(section_number, page_texts)
        for section_number in section_numbers
    }

    assert len(set(resolved.values())) > 1, (
        f"every section of {pdf_name} resolved to the same page, which is what a "
        f"heading the resolver cannot recognise looks like: {resolved}"
    )
    assert resolved == dict(sorted(resolved.items(), key=lambda item: item[1])), (
        f"sections of {pdf_name} are printed in order, so their pages must not go "
        f"backwards: {resolved}"
    )
