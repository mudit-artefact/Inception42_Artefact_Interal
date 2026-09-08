"""
The education allowance answer is the asker's own, and it has a policy behind it.

It used to be a paragraph typed into a workflow step: "up to AED 45,000 per eligible
child", returned to everyone who asked, marked verified, citing nothing. AED 45,000 is a
real figure — the Enhanced ceiling — but six of the twelve seeded employees are on
Standard at AED 25,000 and one is on no plan at all.

There is no step any more. The scheme is written down in HC-PC-012, and which plan an
employee is on is a fact about them that the assistant may read, so the question is
answered the way "how many leave days do I have" is answered: the policy supplies the
ceiling, the record supplies which one is theirs.
"""

from pathlib import Path

import pytest

from app.database.employee_lookup import get_employee_facts_for
from app.domain.enums import HrDataField
from app.domain.policy_catalog import POLICY_CATALOG
from app.workflow.evidence_formatting import format_employee_facts

POLICIES = Path(__file__).resolve().parents[2] / "data"
ENGLISH_POLICY = POLICIES / "policies_en" / "12_education_allowance.md"
ARABIC_POLICY = POLICIES / "policies_ar" / "12_education_allowance.md"


@pytest.mark.parametrize(
    "employee_id, expected",
    [
        ("EMP001", "Education Allowance – Enhanced"),
        ("EMP002", "Education Allowance – Standard"),
        ("EMP007", "none — no education allowance on this package"),
    ],
)
def test_the_assistant_reads_the_employees_own_plan(temporary_database, employee_id, expected):
    """Three employees, three different answers. One fixed figure cannot serve all three."""
    facts = get_employee_facts_for(employee_id)

    written_out = format_employee_facts(facts, [HrDataField.EDUCATION_PLAN])

    assert expected in written_out


def test_the_policy_states_both_ceilings():
    """The figures live in the policy, where they can be quoted and cited."""
    text = ENGLISH_POLICY.read_text()

    assert "AED 25,000" in text
    assert "AED 45,000" in text


def test_the_policy_agrees_with_the_database(temporary_database):
    """
    A ceiling in the policy that the records contradict is worse than no policy at all,
    because it reads as authoritative.
    """
    from app.database.engine import SessionLocal
    from app.database.tables import BenefitPlanRule

    session = temporary_database()
    try:
        limits = {
            rule.plan_code: rule.annual_limit_aed
            for rule in session.query(BenefitPlanRule).all()
        }
    finally:
        session.close()

    text = ENGLISH_POLICY.read_text()
    assert f"AED {limits['EDU_STANDARD']:,}" in text
    assert f"AED {limits['EDU_ENHANCED']:,}" in text


def test_no_age_rule_is_stated_anywhere():
    """
    "between ages 4 and 18" was in the old answer and in no plan rule, no database column
    and no policy document. There is no age rule to state, so nothing may state one.
    """
    for policy in (ENGLISH_POLICY, ARABIC_POLICY):
        text = policy.read_text()
        assert "4 and 18" not in text
        assert "ages" not in text.lower()


def test_both_editions_are_registered():
    """A document not in the catalogue is never indexed, so it may as well not exist."""
    assert POLICY_CATALOG["HC-PC-012"].markdown_filename == "12_education_allowance.md"
    assert POLICY_CATALOG["HC-PC-012-AR"].language == "ar"


ASKING_ABOUT_THE_SCHEME = [
    "Which school fees can I claim back?",
    "What is the schooling policy?",
    "What documents do I need for my child's school claim?",
    "When is the deadline to submit school documents?",
    "How much education allowance do I get?",
    "ما هي المستندات المطلوبة لمطالبة الدراسة؟",
]

SENDING_DOCUMENTS_IN = [
    "I want to upload my school documents",
    "upload school documents",
    "submit proof of schooling",
    "أريد رفع مستندات الدراسة",
]


def _reads_as_sending_documents(text: str) -> bool:
    from app.workflow.nodes.understand_query import ASKING_TO_SEND_DOCUMENTS

    return any(pattern.search(text.lower().strip()) for pattern in ASKING_TO_SEND_DOCUMENTS)


@pytest.mark.parametrize("question", ASKING_ABOUT_THE_SCHEME)
def test_a_question_about_the_scheme_is_not_read_as_an_upload(question):
    """
    A question is answered from the policy. Offering an upload button instead answers
    nothing that was asked — and "when is the deadline to submit school documents" is a
    question about a date, however many of its words look like an instruction.
    """
    assert not _reads_as_sending_documents(question)


@pytest.mark.parametrize("request_text", SENDING_DOCUMENTS_IN)
def test_asking_to_send_documents_still_opens_the_upload(request_text):
    """The one schooling thing that is an action still is one, in both languages."""
    assert _reads_as_sending_documents(request_text)


def test_no_childs_name_decides_where_a_question_goes():
    """
    Twenty-one first names from the seed data used to sit in these patterns, so a question
    was recognised by spotting a demo child's name in it. A real employee called Omar
    tripped it; a family not in the seed did not.
    """
    from app.workflow.nodes import understand_query as routing

    source = Path(routing.__file__).read_text().lower()
    for seeded_name in ("zayed", "fatima", "hind", "saeed", "latifa", "shaikha", "hamdan", "amna"):
        assert seeded_name not in source, f"{seeded_name} is still deciding routing"
