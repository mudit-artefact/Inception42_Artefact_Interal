"""
Canned policy passages, shaped exactly like the dictionaries `vector_store.search`
returns today, so tests never need a vector database or an embedding call.
"""


def build_policy_passage(
    text: str = "Employees accrue 25 working days of paid annual leave per calendar year.",
    source: str = "HC-PC-001",
    title: str = "Annual Leave Policy",
    section: str = "1.1",
    page_number: int = 1,
    score: float = 0.87,
    language: str = "en",
    has_image: bool = False,
) -> dict:
    return {
        "text": text,
        "source": source,
        "title": title,
        "section": section,
        "page_number": page_number,
        "pdf_url": f"/api/v1/hcs01/policies/pdf/01_annual_leave_policy.pdf",
        "has_image": has_image,
        "language": language,
        "score": score,
        "dense_score": score,
        "lexical_score": 0.5,
        "rrf_score": 0.03,
    }


DEFAULT_POLICY_PASSAGES = [
    build_policy_passage(),
    build_policy_passage(
        text="Carry-over is capped at 10 working days and must be used before 31 March.",
        section="1.3",
        page_number=1,
        score=0.79,
    ),
]
