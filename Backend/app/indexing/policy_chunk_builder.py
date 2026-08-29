"""
Turns policy documents into the passages that get indexed.

Each document contributes its numbered sections, taken from the Markdown that is the
policy's source of truth, plus one dedicated passage for its hand-transcribed diagram.

Every passage carries the version it was written under and the window that version was
in force. That is what allows a question about an event last year to be answered with
the rule that applied last year rather than the rule that applies today — the superseded
provisions are indexed alongside the current ones, deliberately, so the two can be told
apart rather than one being hidden.
"""

import logging
from pathlib import Path

from app.core.errors import ApplicationError
from app.domain.policy_catalog import POLICY_CATALOG, PolicyDocument
from app.indexing.pdf_page_resolver import resolve_pdf_page_number
from app.indexing.policy_document_reader import (
    MINIMUM_PAGE_LENGTH,
    MarkdownSection,
    read_markdown_sections,
    read_pdf_page_texts,
)

logger = logging.getLogger(__name__)

BACKEND_DIRECTORY = Path(__file__).resolve().parent.parent.parent
PDF_DIRECTORY = BACKEND_DIRECTORY / "data" / "policies_pdf"

# A passage this long is doing too much at once: its embedding is an average of several
# rules and matches none of them well. Authored sections are kept below it.
LONGEST_COMFORTABLE_PASSAGE = 1500


class PassageInWrongLanguageError(ApplicationError):
    """A passage filed under a language it is not written in."""

    def __init__(self, code: str, section: str) -> None:
        super().__init__(
            f"{code} {section} is filed as Arabic but contains no Arabic characters. "
            f"This is what a broken PDF font looks like: the text was replaced with "
            f"substitute glyphs at generation time. Regenerate the PDFs with "
            f"scripts/generate_policy_pdfs.py rather than indexing this."
        )


def markdown_directory_for(language: str) -> Path:
    """Where a language's policy sources live."""
    return BACKEND_DIRECTORY / "data" / f"policies_{language}"


def build_passages_for_document(document: PolicyDocument) -> list[dict]:
    """Every indexable passage for one policy document."""
    pdf_page_texts = read_pdf_page_texts(PDF_DIRECTORY / document.pdf_filename)
    passages: list[dict] = []

    markdown_sections = (
        read_markdown_sections(
            markdown_directory_for(document.language) / document.markdown_filename
        )
        if document.markdown_filename
        else []
    )

    if markdown_sections:
        for section in markdown_sections:
            passages.append(
                _build_passage(
                    document=document,
                    text=section.combined_text,
                    section_name=section.display_name,
                    page_number=resolve_pdf_page_number(section.section_number, pdf_page_texts),
                    has_image=False,
                    section=section,
                )
            )
    else:
        # No Markdown source for this document, so index whole pages instead.
        for page_number, page_text in pdf_page_texts.items():
            if len(page_text) <= MINIMUM_PAGE_LENGTH:
                continue
            passages.append(
                _build_passage(
                    document=document,
                    text=page_text,
                    section_name=f"Page {page_number}",
                    page_number=page_number,
                    has_image=False,
                )
            )

    return passages


def build_all_policy_passages() -> list[dict]:
    """Every indexable passage across the whole catalogue."""
    passages: list[dict] = []
    for document in POLICY_CATALOG.values():
        passages.extend(build_passages_for_document(document))
    logger.info(f"Prepared {len(passages)} policy passages for indexing")
    return passages


def _build_passage(
    document: PolicyDocument,
    text: str,
    section_name: str,
    page_number: int,
    has_image: bool,
    section: MarkdownSection | None = None,
) -> dict:
    _refuse_a_passage_in_the_wrong_language(document, text, section_name)

    if len(text) > LONGEST_COMFORTABLE_PASSAGE:
        logger.warning(
            f"{document.code} {section_name} is {len(text)} characters. Consider "
            f"splitting it into its own subsections so its embedding stays specific."
        )

    return {
        "text": text,
        "source": document.code,
        "title": document.title,
        "section": section_name,
        "page_number": page_number,
        "pdf_url": document.pdf_url,
        "has_image": has_image,
        "language": document.language,
        "char_count": len(text),
        # Which rule this is, stably, whatever the document is renumbered to later.
        "clause_id": f"{document.code}§{section.section_number}" if section else "",
        # When this rule applied. An empty effective_to means it still does.
        "policy_version": section.version if section else "",
        "effective_from": section.effective_from if section else "",
        "effective_to": section.effective_to if section else "",
        "status": section.status if section else "current",
        "document_owner": document.owner,
    }


def _refuse_a_passage_in_the_wrong_language(
    document: PolicyDocument, text: str, section_name: str
) -> None:
    """
    Stop a passage that claims to be Arabic but contains none.

    Every Arabic PDF in this project once contained no Arabic at all: the generator drew
    it in a font with no Arabic glyphs, so ReportLab silently substituted a dingbat for
    every letter. Thousands of characters of that were embedded and indexed, and they
    matched nothing, and nothing complained. The failure was invisible precisely because
    it was silent, so indexing now refuses it out loud.
    """
    if document.language != "ar":
        return
    if any("؀" <= character <= "ۿ" for character in text):
        return
    raise PassageInWrongLanguageError(document.code, section_name)
