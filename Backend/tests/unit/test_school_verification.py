import pytest
from app.domain.enums import AnswerStatus, QuestionIntent
from app.workflow.nodes.handle_school_verification import handle_school_verification
from app.workflow.nodes.understand_query import understand_query


def test_intent_understanding_school_verification():
    test_queries = [
        "What is the status of my child's school verification?",
        "Did Rami's school verification get approved?",
        "How much education allowance can I claim?",
        "Status of schooling certificate for Dana",
        "Proof of schooling status",
    ]
    for q in test_queries:
        state = {"employee_question": q}
        res = understand_query(state)
        assert res["question_intent"] == QuestionIntent.CHECK_SCHOOL_VERIFICATION.value, (
            f"Expected CHECK_SCHOOL_VERIFICATION for '{q}', got {res['question_intent']}"
        )


def test_intent_understanding_school_submission():
    test_queries = [
        "I want to submit proof of schooling",
        "Upload school document for my child",
        "Submit school letter for Rami",
    ]
    for q in test_queries:
        state = {"employee_question": q}
        res = understand_query(state)
        assert res["question_intent"] == QuestionIntent.SUBMIT_SCHOOL_VERIFICATION.value, (
            f"Expected SUBMIT_SCHOOL_VERIFICATION for '{q}', got {res['question_intent']}"
        )


def test_handle_school_verification_status_for_alia():
    state = {
        "employee_id": "EMP001",
        "employee_question": "What is the status of schooling verification for Zayed?",
        "requested_language": "en",
        "question_intent": QuestionIntent.CHECK_SCHOOL_VERIFICATION.value,
    }
    result = handle_school_verification(state)
    assert result["answer_status"] == AnswerStatus.VERIFIED.value
    assert "Zayed Al Suwaidi" in result["final_answer"]
    payload = result.get("action_payload", {})
    assert payload.get("action_type") == "SCHOOL_VERIFICATION_STATUS"
    assert len(payload.get("cases", [])) > 0


def test_handle_school_submission_guidance():
    state = {
        "employee_id": "EMP001",
        "employee_question": "Upload school letter for Zayed",
        "requested_language": "en",
        "question_intent": QuestionIntent.SUBMIT_SCHOOL_VERIFICATION.value,
    }
    result = handle_school_verification(state)
    assert result["answer_status"] == AnswerStatus.VERIFIED.value
    assert "Submit Proof of Schooling" in result["final_answer"]
    payload = result.get("action_payload", {})
    assert payload.get("action_type") == "SCHOOL_DOCUMENT_SUBMISSION"
    assert len(payload.get("dependents", [])) > 0
