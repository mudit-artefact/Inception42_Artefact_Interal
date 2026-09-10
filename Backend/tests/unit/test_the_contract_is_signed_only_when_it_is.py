"""
"I want to sign my contract."

HCS-11 issues each new joiner an employment contract, and signing it files the signed copy
back as the job-offer document — so it comes off the visa checklist at the same moment.

The trap this file exists for is the date. HCS-11 stamps `signed_on` as soon as *any*
job-offer form is on the case, including an unsigned one the joiner uploaded themselves,
where it falls back to the day the file arrived. Reading that date as a signature would
tell somebody their contract was signed while HCS-11's own OFFER_SIGNED check was failing
it — the same green tick over a rejected document that has already had to be fixed twice
on the schooling and visa sides.

So `contract_is_signed` is the field every screen and sentence reads, and it is computed
once, next to HCS-11's own verdict.
"""

import pytest

from app.domain.employee_facts import VisaCase
from app.domain.enums import AnswerStatus, QuestionIntent
from app.integrations.hcs11_client import _contract_facts
from app.workflow.evidence_formatting import _visa_case_lines
from app.workflow.nodes import finish_turn


# ── What HCS-11 sends ────────────────────────────────────────────────────────

def a_case(*, signed_on=None, checks=(), **overrides):
    """A visa case as HCS-11's JSON has it, with a contract on board."""
    case = {
        "case_id": "VISA0001",
        "plan_name": "Employment visa — international hire, degree required",
        "case_status": "Awaiting Submission",
        "checks": list(checks),
        "contract": {
            "prepared_on": "2026-09-10",
            "signed_on": signed_on,
            "document_id": "DOC-abc123" if signed_on else None,
            "job_title": "Senior Civil Engineer",
            "annual_salary_aed": 320000,
            "start_date": "2026-11-01",
        },
    }
    case.update(overrides)
    return case


OFFER_ACCEPTED = {"code": "OFFER_SIGNED", "result": "pass", "about": ["job_offer"]}
OFFER_NOT_SIGNED = {
    "code": "OFFER_SIGNED",
    "result": "fail",
    "detail": "The job-offer form has not been signed.",
    "about": ["job_offer"],
}


# ── Reading the contract off the case ────────────────────────────────────────

def test_a_contract_nobody_has_signed_is_not_signed():
    facts = _contract_facts(a_case())

    assert facts["contract_is_signed"] is False
    assert facts["contract_signed_on"] == ""
    assert facts["contract_prepared_on"] == "2026-09-10"


def test_a_contract_signed_on_screen_is_signed():
    facts = _contract_facts(a_case(signed_on="2026-09-11", checks=[OFFER_ACCEPTED]))

    assert facts["contract_is_signed"] is True
    assert facts["contract_signed_on"] == "2026-09-11"


def test_an_unsigned_offer_that_was_uploaded_anyway_is_not_a_signature():
    """
    The whole point of the flag.

    HCS-11 gives this case a `signed_on` — the day the file arrived — while its own check
    says the form carries no signature. Believing the date is how a screen tells somebody
    the one thing about their contract that is not true.
    """
    facts = _contract_facts(a_case(signed_on="2026-09-11", checks=[OFFER_NOT_SIGNED]))

    assert facts["contract_signed_on"] == "2026-09-11"
    assert facts["contract_is_signed"] is False


def test_a_case_from_an_hcs11_that_has_no_contracts_says_nothing_about_one():
    """An older HCS-11 sends no contract. That is not a contract nobody has signed."""
    case = a_case()
    del case["contract"]

    assert _contract_facts(case) == {}


def test_the_salary_is_carried_only_when_it_is_a_number():
    case = a_case()
    case["contract"]["annual_salary_aed"] = None

    assert _contract_facts(case)["contract_salary_aed"] is None
    assert _contract_facts(a_case())["contract_salary_aed"] == 320000


# ── What the assistant is told ───────────────────────────────────────────────

def a_visa_case(**overrides):
    fields = {
        "case_id": "VISA0001",
        "plan_name": "Employment visa — degree required",
        "status": "Awaiting Submission",
        "missing_documents": ("passport copy",),
        "contract_prepared_on": "2026-09-10",
        "contract_job_title": "Senior Civil Engineer",
        "contract_start_date": "2026-11-01",
        "contract_salary_aed": 320000,
    }
    fields.update(overrides)
    return VisaCase(**fields)


def test_the_assistant_is_told_the_contract_is_waiting():
    lines = "\n".join(_visa_case_lines([a_visa_case()]))

    assert "not signed yet" in lines
    assert "prepared on 2026-09-10" in lines


def test_the_assistant_is_told_when_it_has_been_signed():
    lines = "\n".join(
        _visa_case_lines([a_visa_case(contract_signed_on="2026-09-11",
                                      contract_is_signed=True)])
    )

    assert "signed on 2026-09-11" in lines


def test_the_assistant_is_never_told_an_unaccepted_offer_is_signed():
    """The evidence sentence is where the false claim would reach the employee."""
    lines = "\n".join(
        _visa_case_lines([a_visa_case(contract_signed_on="2026-09-11",
                                      contract_is_signed=False)])
    )

    assert "signed on" not in lines
    assert "has not been accepted" in lines


def test_the_contract_terms_are_carried_so_they_can_be_quoted():
    lines = "\n".join(_visa_case_lines([a_visa_case()]))

    assert "Senior Civil Engineer" in lines
    assert "2026-11-01" in lines
    assert "AED 320,000" in lines


def test_a_case_with_no_contract_prints_no_contract_lines():
    lines = "\n".join(
        _visa_case_lines([a_visa_case(contract_prepared_on="", contract_start_date="")])
    )

    assert "contract" not in lines.lower()


# ── Which window opens ───────────────────────────────────────────────────────

@pytest.fixture
def hcs11(monkeypatch):
    """Say what HCS-11 holds for this person, without needing HCS-11."""
    def holding(*, school=(), visa=()):
        monkeypatch.setattr(finish_turn, "read_school_claims", lambda _: school)
        monkeypatch.setattr(finish_turn, "read_visa_case", lambda _: visa)
    return holding


A_CONTRACT_TO_SIGN = {
    "case_id": "VISA0001",
    "plan_name": "Employment visa — degree required",
    "status": "Awaiting Submission",
    "missing_documents": ("passport", "job_offer"),
    "problems": (),
    "contract_prepared_on": "2026-09-10",
    "contract_signed_on": "",
    "contract_is_signed": False,
}
A_SIGNED_CONTRACT = {**A_CONTRACT_TO_SIGN, "contract_signed_on": "2026-09-11",
                     "contract_is_signed": True, "missing_documents": ("passport",)}
AN_UNSIGNED_OFFER_ON_FILE = {**A_CONTRACT_TO_SIGN, "contract_signed_on": "2026-09-11",
                             "contract_is_signed": False}


def asked_to_sign(language="en"):
    return {
        "employee_id": "EMP013",
        "employee_question": "i want to sign my contract",
        "requested_language": language,
        "document_kind": "contract",
        "employee_facts": {"education_plan_code": "NONE"},
    }


def test_asking_to_sign_opens_the_contract_window(hcs11):
    hcs11(school=(), visa=[A_CONTRACT_TO_SIGN])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert answer["action_payload"] == {
        "action_type": "CONTRACT_SIGNING",
        "case_id": "VISA0001",
    }
    # Not `document_upload`, which is what draws the school button beside it.
    assert answer["question_intent"] == QuestionIntent.HR_QUESTION.value
    assert answer["answer_status"] == AnswerStatus.VERIFIED.value


def test_asking_to_sign_never_opens_the_visa_upload_window(hcs11):
    """
    The wrong-window mistake, in its third costume.

    A contract lives on a visa case, so the person who asks to sign always has a visa case
    too — and handing them the upload window would answer a question they did not ask.
    """
    hcs11(school=(), visa=[A_CONTRACT_TO_SIGN])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert answer["action_payload"]["action_type"] != "VISA_DOCUMENT_UPLOAD"


def test_somebody_who_has_signed_is_told_so_and_can_still_read_it(hcs11):
    hcs11(school=(), visa=[A_SIGNED_CONTRACT])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert "already signed" in answer["final_answer"].lower()
    # The window still opens: reading a contract you signed is a reasonable thing to want.
    assert answer["action_payload"]["action_type"] == "CONTRACT_SIGNING"


def test_an_unsigned_offer_on_file_is_not_reported_as_signed(hcs11):
    """The date is set and the signature is not. The reply must not say signed."""
    hcs11(school=(), visa=[AN_UNSIGNED_OFFER_ON_FILE])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert "already signed" not in answer["final_answer"].lower()
    assert "not been accepted" in answer["final_answer"]
    assert answer["action_payload"]["action_type"] == "CONTRACT_SIGNING"


def test_somebody_with_no_visa_case_is_told_there_is_no_contract(hcs11):
    hcs11(school=(), visa=[])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert answer["action_payload"] is None
    assert "no employment contract" in answer["final_answer"].lower()


def test_an_employee_with_a_school_claim_and_no_case_gets_no_contract_window(hcs11):
    """Asking to sign is not a way into the schooling window by falling through."""
    hcs11(school=[{"case_id": "CASE0003", "payment_status": "Not Ready"}], visa=[])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert answer["action_payload"] is None


def test_hcs11_being_unreachable_does_not_claim_there_is_no_contract(hcs11):
    """
    `None` means it could not be asked, and it is not the same as having no contract.

    The window opens and reports the failure itself, which is how the visa and school
    windows already behave — refusing here would tell somebody who has a contract that
    they have none.
    """
    hcs11(school=None, visa=None)

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign())

    assert answer["action_payload"] is not None
    assert answer["action_payload"]["action_type"] == "CONTRACT_SIGNING"
    assert "no employment contract" not in answer["final_answer"].lower()


def test_the_arabic_reply_is_arabic(hcs11):
    hcs11(school=(), visa=[A_CONTRACT_TO_SIGN])

    answer = finish_turn.generate_document_upload_prompt(asked_to_sign(language="ar"))

    assert any("؀" <= ch <= "ۿ" for ch in answer["final_answer"])
