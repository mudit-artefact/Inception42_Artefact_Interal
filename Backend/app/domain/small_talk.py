"""
The words people use when they are not asking anything.

Hello, thank you, that's fine, how are you — the four kinds of message that carry no
question. Two steps need to recognise them and for different reasons: `understand_query`
to label the turn conversational rather than send it to be answered, and `finish_turn` to
choose which of the four replies to give. They each kept their own copy of the same three
regexes, and the copies had already drifted.

**Two faults these patterns used to have, both fixed here and both worth not reintroducing.**

The first is anchoring. Every pattern was written `^…$`, so the message had to be *only*
"ok" or *only* "thanks". "Okay, thank you" is the commonest way in English to end a
conversation and it is both of those joined, so it matched neither and fell through to be
answered as a greeting — a hello, in reply to goodbye. Five of the nine most ordinary
sign-offs did the same.

The second is that greeting was the fallback. Anything conversational that matched nothing
else was greeted, which makes a hello the widest case when it should be the narrowest:
mid-conversation it is the one reply that is always wrong. `looks_like` returns None when
it does not recognise something, and the caller decides — which, after the first turn, is
never a greeting.
"""

import re

# Order matters, and it is the order of a sentence rather than of importance. "Ok thanks"
# is thanks with a preamble; reading the "ok" first would answer the throat-clearing and
# ignore what was actually said.
#
# Each of these is a phrase somewhere in the message rather than the whole of it — that is
# the anchoring fix — with word boundaries so "thanks" is not found inside "thanksgiving"
# and "ok" is not found inside "broker".

# Matched on the stem, so the spelling does not have to be right.
#
# "Okay thanky ou" is "thank you" with the space in the wrong place, and it is the kind of
# thing people actually type. Spelt out in full it matched nothing, fell through to the
# unrecognised-aside reply, and was answered as though it were a shrug. The stem catches
# "thanks", "thankyou", "thanky ou" and "thank yo" alike.
#
# Two words start the same way and mean nothing of the sort — "a thankless task" is a
# complaint, not gratitude — so they are excluded by name rather than by hoping nobody
# writes them.
THANKS = re.compile(
    r"\bthank(?!less|sgiving)|\b(thx|much appreciated|many thanks)\b"
    r"|شكرا|شكراً|مشكور|يعطيك العافية|جزاك الله خير",
    re.IGNORECASE,
)

PLEASANTRY = re.compile(
    r"\b(how are you|how're you|how r u|how are you doing|how is it going"
    r"|how's it going|how do you do|how have you been|how are things)\b"
    r"|كيف حالك|شخبارك|كيفك|شلونك|عساك بخير",
    re.IGNORECASE,
)

# Anchored, unlike the two above, and deliberately.
#
# "Hi" is a greeting and "is hiring frozen?" is not; "hey, what is my leave balance?" is a
# question with a hello stuck to the front of it, and answering the hello would drop the
# question. A greeting is only a greeting when it is the whole message.
GREETING = re.compile(
    # "Hola" and "bonjour" are here although the product answers in English and Arabic
    # only. Somebody who opens with one is still saying hello, and greeting them back in
    # English is a better answer than treating it as an unrecognised aside.
    r"^\s*(hi|hey|hello|hiya|yo|good morning|good afternoon|good evening|greetings"
    r"|hola|bonjour|ciao|namaste"
    r"|salam|salaam|assalam|assalamu|as-salamu|alaykum|alaikum|walekum|walaykum"
    r"|مرحبا|مرحباً|أهلا|أهلاً|السلام عليكم|سلام)"
    # "Hey there" and "hello everyone" are the same greeting with a word after it. Only
    # these two, and only at the end — "hi, what is my balance" is still a question.
    r"(\s+(there|everyone|all))?"
    r"[\s,\.\!،]*$",
    re.IGNORECASE,
)

# Last of the four, because it is the vaguest. "Fine" and "sure" and "great" are also
# ordinary English words, so this one stays anchored to the whole message.
ACKNOWLEDGEMENT = re.compile(
    r"^\s*(ok|okay|k|noted|got it|all right|alright|understood|sounds good|sure|fine"
    r"|great|perfect|done|will do|cool"
    r"|تمام|حسنا|حسناً|ماشي|اوكي|أوكي|طيب|تسلم)"
    r"[\s,\.\!،]*$",
    re.IGNORECASE,
)

# Kept for the one thing it does that `GREETING` does not: recognising a salam anywhere in
# the message, so the reply can return it in kind.
ISLAMIC_GREETING = re.compile(
    r"\b(salam|salaam|salambay|assalam|assalamu|alaykum|alaikum|walekum|walaykum)\b"
    r"|[؀-ۿ]*سلام[؀-ۿ]*|السلام\s+عليكم",
    re.IGNORECASE,
)

# What a turn carrying no question actually was. In sentence order: thanks beats the "ok"
# in front of it, and a greeting beats a bare acknowledgement because "hi" would otherwise
# never be reached.
IN_ORDER = (
    ("thanks", THANKS),
    ("pleasantry", PLEASANTRY),
    ("greeting", GREETING),
    ("acknowledgement", ACKNOWLEDGEMENT),
)


def looks_like(message: str) -> str | None:
    """
    Which kind of small talk this is, or None when it is none of them.

    None is the useful answer, not a failure. It used to be impossible to express — the
    step that chose a reply treated anything it did not recognise as a greeting — and
    saying "I do not know what this was" is what lets the caller pick something that is not
    a hello.
    """
    for kind, pattern in IN_ORDER:
        if pattern.search(message or ""):
            return kind
    return None


def is_small_talk(message: str) -> bool:
    """Whether this message carries no question worth routing to be answered."""
    return looks_like(message) is not None
