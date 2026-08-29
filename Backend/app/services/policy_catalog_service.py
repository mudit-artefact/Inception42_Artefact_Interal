"""The list of policies the web interface offers for browsing."""

from app.domain.policy_catalog import english_documents
from app.schemas.policy import PolicySummary


def list_policy_summaries() -> list[PolicySummary]:
    """Every English policy document, with links to its official PDF."""
    return [
        PolicySummary(
            id=document.code,
            title=document.title,
            section=document.code,
            topics=document.topics,
            pdf_url=document.pdf_url,
            url=document.pdf_url,
            diagram_page=document.diagram_page,
        )
        for document in english_documents()
    ]
