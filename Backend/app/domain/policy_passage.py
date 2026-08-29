"""A single passage of policy text retrieved from the search index."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyPassage:
    """One retrieved piece of a policy document, with where it came from."""

    text: str
    policy_code: str
    title: str
    section: str
    page_number: int
    pdf_url: str
    language: str
    has_image: bool
    # Between 0 and 1. Results are ordered by this same number, and it is what the
    # web interface shows as a match percentage. It is derived from the passage's rank
    # under both search methods, so it says where a passage came in — not how close it
    # actually is to the question.
    relevance_score: float

    # How close this passage really is to the question, from the vector search. Ranges
    # over the whole 0 to 1 scale, so this is the number to use when deciding whether
    # anything relevant was found at all.
    semantic_similarity: float = 0.0

    # Which rule this is, and when it applied. A passage from a policy's superseded
    # appendix carries the window it was in force, so an answer about last year can be
    # told apart from an answer about today.
    clause_id: str = ""
    policy_version: str = ""
    effective_from: str = ""
    effective_to: str = ""
    status: str = "current"

    @property
    def is_superseded(self) -> bool:
        return self.status == "superseded"

    def as_dictionary(self) -> dict:
        """The shape older callers still expect."""
        return {
            "text": self.text,
            "source": self.policy_code,
            "title": self.title,
            "section": self.section,
            "page_number": self.page_number,
            "pdf_url": self.pdf_url,
            "has_image": self.has_image,
            "language": self.language,
            "score": self.relevance_score,
            "clause_id": self.clause_id,
            "policy_version": self.policy_version,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "status": self.status,
        }
