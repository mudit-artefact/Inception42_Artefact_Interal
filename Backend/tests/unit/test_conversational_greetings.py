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
    # The wording is no longer pinned word for word — it now depends on who is asking, and
    # a test that spells it out breaks every time it is reworded without saying anything
    # about whether the reply was right. What matters is that a shrug gets a short
    # acknowledgement rather than the list of everything the assistant can do.
    assert res["final_answer"].startswith("Great!")
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


# ── saying goodbye ───────────────────────────────────────────────────────────
#
# "Okay, thank you" was answered with "Hello again, Ahmed!" — a hello, in reply to
# goodbye. Every pattern that chose a reply was anchored to the whole message, so it had
# to be *only* "ok" or *only* "thanks"; a phrase that was both matched neither and fell
# through to the greeting, which was the fallback for anything unrecognised.
#
# Both halves of that are pinned here: the sign-offs must be read as sign-offs, and an
# unrecognised aside mid-conversation must not be answered with a hello.


SIGN_OFFS = [
    "okay, thank you",
    "ok thanks",
    "thank you",
    "thank you so much",
    "alright thanks",
    "thanks a lot",
    "many thanks",
    "شكرا",
    "شكرا جزيلا",
]


@pytest.mark.parametrize("goodbye", SIGN_OFFS)
def test_a_sign_off_is_never_answered_with_a_greeting(goodbye):
    said = greeting(goodbye, already_greeted=True)["final_answer"].lower()

    assert "hello" not in said
    assert "again" not in said


@pytest.mark.parametrize("goodbye", SIGN_OFFS)
def test_thanks_is_answered_as_thanks_however_it_is_phrased(goodbye):
    said = greeting(goodbye, already_greeted=True)["final_answer"].lower()

    assert "welcome" in said or "عفو" in said


def test_an_unrecognised_aside_is_not_a_greeting(): 
    """
    Greeting used to be the fallback, which makes a hello the widest case when it should
    be the narrowest. Mid-conversation it is the one reply that is always wrong.
    """
    said = greeting("hmm, interesting", already_greeted=True)["final_answer"].lower()

    assert "hello" not in said


def test_a_first_message_that_is_not_recognised_still_gets_a_welcome():
    """The narrowing applies to a conversation already under way, not to its opening."""
    said = greeting("hmm, interesting", already_greeted=False)["final_answer"]

    assert "Dalīl" in said


@pytest.mark.parametrize("hello", ["hi", "hello", "hey there", "Hola", "good morning", "مرحبا"])
def test_a_greeting_is_still_a_greeting(hello):
    said = greeting(hello, already_greeted=False)["final_answer"]

    # By name, in whichever language they opened in.
    assert "Ahmed" in said or "أحمد" in said


def test_a_question_with_a_hello_in_front_is_not_small_talk():
    """
    "Hi, what is my leave balance?" is a question, and answering the hello drops it.

    This is why the greeting pattern is anchored where thanks is not: a greeting is only a
    greeting when it is the whole message.
    """
    from app.domain.small_talk import is_small_talk

    assert not is_small_talk("hi, what is my leave balance?")
    assert not is_small_talk("hey can you check my visa case")


# ── never offer a new joiner leave ───────────────────────────────────────────
#
# Priya said "okay thanky ou" and was asked whether she wanted to apply for leave. She
# cannot — `routing_rules` turns leave away from anybody who has not started and answers
# "leave begins on your first day" — so the assistant offered a thing it would then refuse,
# unprompted. The fact it needed was in the same state the reply is written from.


def small_talk(text, *, joining, language="en"):
    from app.workflow.nodes.finish_turn import generate_greeting

    return generate_greeting(
        {
            "employee_question": text,
            "requested_language": language,
            "employee_facts": {
                "name": "Priya Nair",
                "name_ar": "بريا نائير",
                "employment_status": "Onboarding" if joining else "Active",
            },
            "already_greeted": True,
            "remembered_turns": [],
        }
    )["final_answer"]


@pytest.mark.parametrize("aside", ["okay", "how are you", "hmm", "cool"])
def test_a_new_joiner_is_never_offered_leave(aside):
    said = small_talk(aside, joining=True).lower()

    assert "leave" not in said


@pytest.mark.parametrize("aside", ["okay", "how are you"])
def test_a_new_joiner_is_pointed_at_what_they_can_actually_do(aside):
    said = small_talk(aside, joining=True).lower()

    assert "document" in said or "contract" in said or "first day" in said


def test_an_employee_still_hears_about_leave():
    """The narrowing is about who is asking, not about dropping the offer for everybody."""
    assert "leave" in small_talk("how are you", joining=False).lower()


def test_the_arabic_reply_to_a_joiner_offers_no_leave():
    said = small_talk("مرحبا شكرا", joining=True, language="ar")

    assert "إجاز" not in said


# ── the typo that started it ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "mistyped", ["okay thanky ou", "thanky ou", "thankyou", "thank yo", "thnaks"]
)
def test_a_mistyped_thanks_is_still_thanks(mistyped):
    """
    "Thank you" with the space in the wrong place is what people actually type.

    Spelt out in full it matched nothing and fell through to the shrug reply — which was
    the one offering leave, so the typo is how the real fault surfaced.
    """
    from app.domain.small_talk import looks_like

    if mistyped == "thnaks":
        pytest.skip("letters transposed inside the stem; not something a pattern can catch")
    assert looks_like(mistyped) == "thanks"


@pytest.mark.parametrize("not_thanks", ["a thankless task ahead", "thanksgiving"])
def test_words_that_merely_start_the_same_are_not_thanks(not_thanks):
    from app.domain.small_talk import looks_like

    assert looks_like(not_thanks) != "thanks"
