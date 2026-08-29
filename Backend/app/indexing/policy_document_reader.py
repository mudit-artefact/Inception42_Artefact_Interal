"""
Reads policy documents off disk: the PDF pages, the Markdown sections, and the version
each section was written under.

Two things here are less obvious than they look.

Extracted PDF text is normalised. Arabic in a PDF is stored as *presentation forms* —
the joined, context-dependent shapes actually drawn — so the extracted text of a
correctly generated Arabic page contains no ordinary Arabic letters at all. Someone
searching for a word would never match it. NFKC folds those shapes back to the letters
they stand for.

A section may be governed by a different version from the document that contains it. A
superseded provision is kept in its policy's reserved section 9, and the revision table
in section 0 says when it was in force. That is what lets a question about last year be
answered with last year's rule.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

# A heading alone is not a policy. Raised from 25, which admitted the identical 27-char
# "# HC Services — People Code" title of every document as its own passage — five
# byte-identical chunks competing in every search.
MINIMUM_SECTION_LENGTH = 60
MINIMUM_PAGE_LENGTH = 30

_HEADING_PATTERN = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)
_SECTION_NUMBER_PATTERN = re.compile(r"(\d+\.\d+)")

# The reserved band a policy keeps its superseded provisions in.
SUPERSEDED_SECTION_SUFFIX = ".9"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "مايو": 5, "يونيو": 6,
    "يوليو": 7, "أغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}


def _as_iso_date(text: str) -> str:
    """"1 January 2026" or "1 يناير 2026" as "2026-01-01". Empty when unparseable."""
    match = re.search(r"(\d{1,2})\s+([^\s\d]+)\s+(\d{4})", text.strip())
    if not match:
        return ""
    day, month_name, year = match.groups()
    month = _MONTHS.get(month_name.lower())
    if not month:
        return ""
    return date(int(year), month, int(day)).isoformat()


@dataclass(frozen=True)
class DocumentMetadata:
    """What a policy says about itself, and about the versions it has passed through."""

    code: str = ""
    version: str = ""
    effective_from: str = ""
    owner: str = ""
    # version -> (effective_from, superseded_on). Superseded_on is "" for the current one.
    version_history: dict = None

    def window_for_version(self, version: str) -> tuple[str, str]:
        """When a given version was in force."""
        return (self.version_history or {}).get(version, ("", ""))


def read_document_metadata(markdown_path: Path) -> DocumentMetadata:
    """The document control block and the revision table, from section N.0."""
    if not markdown_path.exists():
        return DocumentMetadata(version_history={})

    text = markdown_path.read_text(encoding="utf-8")

    def field(name: str) -> str:
        found = re.search(rf"\*\*{name}:\*\*\s*(.+)", text)
        return found.group(1).strip() if found else ""

    history: dict[str, tuple[str, str]] = {}
    for row in re.findall(r"^\|\s*(\d+\.\d+)\s*\|([^|]*)\|([^|]*)\|", text, re.MULTILINE):
        version, effective, superseded = (cell.strip() for cell in row)
        history[version] = (_as_iso_date(effective), _as_iso_date(superseded))

    return DocumentMetadata(
        code=field("Document Reference"),
        version=field("Version"),
        effective_from=_as_iso_date(field("Effective Date")),
        owner=field("Owner"),
        version_history=history,
    )


@dataclass(frozen=True)
class MarkdownSection:
    """One numbered section of a policy, taken from its Markdown source."""

    heading: str
    body: str
    section_number: str
    # The version this particular section was written under. A superseded provision
    # carries the version it was in force under, not the document's current one.
    version: str = ""
    effective_from: str = ""
    effective_to: str = ""
    status: str = "current"

    @property
    def combined_text(self) -> str:
        return (self.heading + "\n" + self.body).strip()

    @property
    def display_name(self) -> str:
        if self.section_number:
            return f"Section {self.section_number}"
        return self.heading.lstrip("# ").strip()


def read_pdf_page_texts(pdf_path: Path) -> dict[int, str]:
    """
    Page number (starting at 1) to its extracted text, skipping pages with no text.

    Text is normalised with NFKC, which is what turns the presentation forms a PDF
    stores Arabic as back into ordinary Arabic letters. Without it an Arabic page
    extracts as characters no reader would ever type, and matches nothing.

    A page holding only a picture comes back empty; nothing here reads images.
    """
    if not pdf_path.exists():
        return {}

    page_texts: dict[int, str] = {}
    try:
        document = pymupdf.open(str(pdf_path))
        for page_index, page in enumerate(document):
            page_text = unicodedata.normalize("NFKC", page.get_text()).strip()
            if page_text:
                page_texts[page_index + 1] = page_text
        document.close()
    except Exception as error:
        logger.warning(f"Could not read the PDF at {pdf_path}: {error}")

    return page_texts


def read_markdown_sections(markdown_path: Path) -> list[MarkdownSection]:
    """Split a policy's Markdown into its numbered sections."""
    if not markdown_path.exists():
        return []

    metadata = read_document_metadata(markdown_path)
    parts = _HEADING_PATTERN.split(markdown_path.read_text(encoding="utf-8"))
    sections: list[MarkdownSection] = []
    current_heading = ""
    current_body = ""

    def keep_current_section() -> None:
        combined = (current_heading + "\n" + current_body).strip()
        if len(combined) < MINIMUM_SECTION_LENGTH:
            return
        section_number_match = _SECTION_NUMBER_PATTERN.search(current_heading)
        section_number = section_number_match.group(1) if section_number_match else ""
        version, effective_from, effective_to, status = _version_governing(
            section_number, current_heading, metadata
        )
        sections.append(
            MarkdownSection(
                heading=current_heading,
                body=current_body,
                section_number=section_number,
                version=version,
                effective_from=effective_from,
                effective_to=effective_to,
                status=status,
            )
        )

    for part in parts:
        if _HEADING_PATTERN.match(part):
            if current_heading or current_body:
                keep_current_section()
            current_heading = part
            current_body = ""
        else:
            current_body += part

    if current_heading or current_body:
        keep_current_section()

    return sections


def _version_governing(
    section_number: str, heading: str, metadata: DocumentMetadata
) -> tuple[str, str, str, str]:
    """
    Which version of the policy governs one section, and when it was in force.

    Almost every section is governed by the document's current version. The exception is
    the reserved section 9, where a policy keeps a provision it has replaced: that
    section names its own version in its heading, and the revision table says when that
    version stopped applying. Getting this right is the difference between answering a
    question about last year with last year's rule and answering it with today's.
    """
    is_superseded = section_number.endswith(SUPERSEDED_SECTION_SUFFIX) and bool(
        re.search(r"Superseded|ملغاة", heading)
    )
    if not is_superseded:
        return metadata.version, metadata.effective_from, "", "current"

    named_version = re.search(r"(?:Version|الإصدار)\s+(\d+\.\d+)", heading)
    version = named_version.group(1) if named_version else ""
    effective_from, effective_to = metadata.window_for_version(version)
    return version, effective_from, effective_to, "superseded"
