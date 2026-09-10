import pytest
from app.domain.enums import AnswerStatus, QuestionIntent
from app.workflow.nodes.finish_turn import generate_greeting
from app.workflow.nodes.understand_query import understand_query


def test_acknowledgment_response():
    state = {
        "employee_question": "ok",
        "employee_facts": {"name": "Fatima Maryam Al Qubaisi"},
        "requested_language": "en",
        "remembered_turns": [],
    }
    res = generate_greeting(state)
    assert res["answer_status"] == AnswerStatus.VERIFIED.value
    assert "Great! Let me know if you need anything else" in res["final_answer"]
    assert "Annual and sick leave policies" not in res["final_answer"]


def test_pleasantry_response():
    state = {
        "employee_question": "how are you?",
        "employee_facts": {"name": "Fatima Maryam Al Qubaisi"},
        "requested_language": "en",
        "remembered_turns": [],
    }
    res = generate_greeting(state)
    assert res["answer_status"] == AnswerStatus.VERIFIED.value
    assert "I'm doing well, thank you for asking!" in res["final_answer"]
    assert "Annual and sick leave policies" not in res["final_answer"]


def test_gratitude_response():
    state = {
        "employee_question": "thank you!",
        "employee_facts": {"name": "Fatima Maryam Al Qubaisi"},
        "requested_language": "en",
        "remembered_turns": [],
    }
    res = generate_greeting(state)
    assert res["answer_status"] == AnswerStatus.VERIFIED.value
    assert "You're very welcome!" in res["final_answer"]


def test_arabic_acknowledgment_and_pleasantry():
    state_ar_ok = {
        "employee_question": "تمام",
        "employee_facts": {"name": "Fatima", "name_ar": "فاطمة مريم القبيسي"},
        "requested_language": "ar",
        "remembered_turns": [],
    }
    res = generate_greeting(state_ar_ok)
    assert "ممتاز!" in res["final_answer"]

    state_ar_how = {
        "employee_question": "كيف حالك؟",
        "employee_facts": {"name": "Fatima", "name_ar": "فاطمة مريم القبيسي"},
        "requested_language": "ar",
        "remembered_turns": [],
    }
    res2 = generate_greeting(state_ar_how)
    assert "أنا بخير، شكراً لسؤالك!" in res2["final_answer"]


def test_mid_conversation_repeat_greeting():
    state = {
        "employee_question": "hi",
        "employee_facts": {"name": "Fatima"},
        "requested_language": "en",
        "remembered_turns": [{"question": "what is my leave balance?", "answer": "You have 3 days."}],
    }
    res = generate_greeting(state)
    assert "Hello again, Fatima!" in res["final_answer"]
    assert "Annual and sick leave policies" not in res["final_answer"]


def test_initial_turn_greeting_has_menu():
    state = {
        "employee_question": "hello",
        "employee_facts": {"name": "Fatima"},
        "requested_language": "en",
        "remembered_turns": [],
    }
    res = generate_greeting(state)
    assert "Hello Fatima! I am Dalīl, your HR assistant." in res["final_answer"]
    assert "Annual and sick leave policies" not in res["final_answer"]


def test_understand_query_fast_conversational_override():
    state_ok = {"employee_question": "ok"}
    out = understand_query(state_ok)
    assert out["question_intent"] == QuestionIntent.GREETING.value
    assert out["intent_confidence"] == 1.0

    state_how = {"employee_question": "how are you?"}
    out_how = understand_query(state_how)
    assert out_how["question_intent"] == QuestionIntent.GREETING.value


# ── hello, twice ─────────────────────────────────────────────────────────────
#
# "Hi", then "Salam", then "Hola" each produced the identical sentence, introduction and
# all, because the check for a second greeting asked whether the conversation had any
# remembered turns — and a greeting is deliberately never remembered.


def greeting(question, *, already_greeted=False, language="en"):
    from app.workflow.nodes.finish_turn import generate_greeting

    return generate_greeting(
        {
            "employee_question": question,
            "requested_language": language,
            "employee_facts": {"name": "Ahmed Al Rashid", "name_ar": "أحمد الراشد"},
            "already_greeted": already_greeted,
            "remembered_turns": [],
        }
    )


def test_the_greeting_uses_a_first_name():
    """"Hello Ahmed Al Rashid" is how a system addresses a case file."""
    said = greeting("Hi")["final_answer"]

    assert "Ahmed" in said
    assert "Al Rashid" not in said


def test_the_greeting_says_hello_once():
    """It read "Hello {name}! Hi, I am Dalīl" — a hello and a hi in one breath."""
    said = greeting("Hi")["final_answer"]

    assert said.count("Hello") == 1
    assert "Hi, I am" not in said


def test_the_second_hello_is_answered_as_a_second_one(): 
    first = greeting("Hi")
    second = greeting("Hola", already_greeted=True)["final_answer"]

    assert first["already_greeted"] is True, "the first greeting must record that it happened"
    assert second != first["final_answer"]
    assert "again" in second.lower()


def test_the_second_hello_does_not_introduce_itself_again():
    said = greeting("hey", already_greeted=True)["final_answer"]

    assert "Dalīl" not in said


def test_a_salam_is_returned_in_kind():
    assert "salam" in greeting("Salam")["final_answer"].lower()


def test_arabic_greets_in_arabic_and_by_first_name():
    said = greeting("مرحبا", language="ar")["final_answer"]

    assert "أحمد" in said
    assert "الراشد" not in said
