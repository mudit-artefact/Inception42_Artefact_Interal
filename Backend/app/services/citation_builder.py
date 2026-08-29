"""
Building the citations shown beneath an answer.

The citation for the employee's own record used to be assembled by hand in four places,
each with slightly different wording, so which one a reader saw depended on the code path
that produced it.
"""

import re

from app.domain.employee_facts import EmployeeFacts
from app.schemas.answer import SourceCitation

MAXIMUM_SNIPPET_LENGTH = 160
EMPLOYEE_RECORD_CITATION_ID = "source-employee-record"
EXACT_MATCH_SCORE = 1.0


def build_employee_record_citation(facts: EmployeeFacts, language: str = "en") -> SourceCitation:
    """The single citation representing this employee's own HR record."""
    summary = (
        f"Employee: {facts.name} ({facts.employee_id}) | "
        f"Department: {facts.department} | "
        f"Annual Leave: {facts.annual_leave_balance} days remaining | "
        f"Sick Leave: {facts.sick_leave_balance} days remaining | "
        f"Line Manager: {facts.manager_name}"
    )
    return SourceCitation(
        id=EMPLOYEE_RECORD_CITATION_ID,
        title="Omni HR Employee Record",
        source="Omni HR Database",
        source_type="database",
        table_name="employees, leave_balances",
        section=f"Record: {facts.employee_id} ({facts.name})",
        page_number=None,
        score=EXACT_MATCH_SCORE,
        language=language,
        snippet=summary,
        url="#",
        pdf_url=None,
        has_image=False,
    )


def build_policy_citations(passages: list[dict]) -> list[SourceCitation]:
    """One citation per retrieved policy extract, in the order they were ranked."""
    return [
        SourceCitation(
            id=f"source-policy-{position}",
            title=passage.get("title") or passage.get("source", ""),
            source=passage.get("source", ""),
            source_type="policy",
            table_name=None,
            section=passage.get("section", ""),
            page_number=passage.get("page_number", 1),
            score=passage.get("score", 0.0),
            language=passage.get("language", "en"),
            snippet=shorten_for_display(passage.get("text", "")),
            url=passage.get("pdf_url") or "#",
            pdf_url=passage.get("pdf_url") or "#",
            has_image=passage.get("has_image", False),
        )
        for position, passage in enumerate(passages, start=1)
    ]


def shorten_for_display(text: str) -> str:
    """A one-line preview of a passage, with its Markdown formatting stripped."""
    if not text:
        return ""
    without_headings = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    without_emphasis = re.sub(r"[*_]{1,3}", "", without_headings)
    collapsed = re.sub(r"\s+", " ", without_emphasis).strip()
    if len(collapsed) > MAXIMUM_SNIPPET_LENGTH:
        return collapsed[: MAXIMUM_SNIPPET_LENGTH - 5].rstrip() + "…"
    return collapsed
