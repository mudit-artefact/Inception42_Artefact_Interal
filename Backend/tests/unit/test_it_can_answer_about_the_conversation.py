"""
"What was the very first thing I asked you?"

At turn 11 of a conversation it had remembered perfectly — the right education plan at
turn 9, the right probation status at turn 10 — this was classified out of scope and
refused with "I cannot assist with questions outside our company HR policies." The
conversation was in the state the whole time. Only the classifier had nowhere to put a
question about it.

One reply serves every way of asking. The first thing they asked is number 1, what they
have covered is the list, and nothing in it is generated: each line is a question they
typed, already shortened and made safe when it was remembered.
"""

from app.domain.enums import QuestionIntent
from app.workflow.answer_validation import check_the_answer_is_in_the_requested_language
from app.workflow.nodes.finish_turn import _recap_of_the_conversation, generate_greeting
from app.workflow.routing_rules import decide_after_understanding

CONVERSATION = [
    {"question": "What is the carry over limit for annual leave?", "answer": "10 days."},
    {"question": "How long is probation?", "answer": "6 months."},
    {"question": "What is the mileage rate?", "answer": "AED 0.67 per kilometre."},
]


def test_the_first_question_is_the_first_line():
    said = _recap_of_the_conversation(CONVERSATION, "en")

    assert "1. “What is the carry over limit for annual leave?”" in said
    assert "3. “What is the mileage rate?”" in said


def test_it_says_so_when_there_is_nothing_to_look_back_on():
    said = _recap_of_the_conversation([], "en")

    assert "first thing you have asked me" in said
    assert "1." not in said


def test_a_turn_with_no_question_is_skipped_rather_than_numbered_blank():
    said = _recap_of_the_conversation(
        [{"question": "", "answer": "..."}, {"question": "How long is probation?", "answer": ""}],
        "en",
    )

    assert said.count("\n1.") == 1
    assert "1. “How long is probation?”" in said


def test_the_question_reaches_the_step_that_answers_it():
    assert (
        decide_after_understanding(
            {"question_intent": QuestionIntent.ABOUT_THIS_CONVERSATION, "clarification_count": 0}
        )
        == "generate_greeting"
    )


def test_the_node_answers_it_without_retrieving_anything():
    result = generate_greeting(
        {
            "employee_question": "what was the very first thing I asked you?",
            "question_intent": QuestionIntent.ABOUT_THIS_CONVERSATION.value,
            "requested_language": "en",
            "employee_facts": {"name": "Alia Al Marzouqi"},
            "remembered_turns": CONVERSATION,
        }
    )

    assert "carry over limit" in result["final_answer"]
    assert result["citations"] == []


def test_an_arabic_reply_may_quote_the_english_questions_it_is_recapping():
    """
    Someone who asked in English and then asked in Arabic what they had asked is owed
    their own words back unchanged. Counting those quoted English words against the reply
    called an Arabic answer English and threw it away.
    """
    said = _recap_of_the_conversation(CONVERSATION, "ar")

    assert "What is the carry over limit for annual leave?" in said
    assert check_the_answer_is_in_the_requested_language(said, "ar").is_valid


def test_quoting_is_still_not_a_way_round_the_language_check():
    """An answer that is nothing but a quotation is judged whole, like any other."""
    outcome = check_the_answer_is_in_the_requested_language(
        "“You have fifteen days of annual leave remaining.”", "ar"
    )

    assert not outcome.is_valid
