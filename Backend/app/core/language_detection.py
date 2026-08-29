"""
Deciding whether a piece of text is English or Arabic.

There used to be two answers to this question. The web layer called any text Arabic if it
contained a single Arabic character, so "Do I get 3 أيام?" was treated as an Arabic
question and answered in Arabic. The query layer required more than 30 percent of the
characters to be Arabic and called the same sentence English. This is the one detector.

It counts words, not characters. The share used to be counted with Arabic punctuation
and vowel marks in the numerator and neither of them in the denominator, so a wholly
Arabic sentence could score above 1.0 and a short English question quoting one Arabic
word scored high enough to be called Arabic — the very case the paragraph above says was
fixed.

Counting characters fails the way employees here actually write. "هل LWOP يؤثر على annual
leave؟" is an Arabic question, but the English HR terms in it are long and the Arabic
words are short, so by character count English wins and the employee is answered in a
language they did not ask in. By word count Arabic wins, which is the right answer. A tie
goes to Arabic, because a sentence mixing the two is far more often Arabic borrowing an
English term than the reverse.

Presentation forms count as Arabic: a PDF stores Arabic as those joined shapes, so text
read back out of one would otherwise look like no language at all.
"""

import re
import unicodedata
from typing import Literal

WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
# Standard Arabic, and the joined shapes a PDF stores it as.
ARABIC_LETTER_PATTERN = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
ARABIC_SHARE_REQUIRED = 0.5


def detect_language(text: str) -> Literal["en", "ar"]:
    """
    The language a reply should be written in.

    Arabic when at least half the words are Arabic, so an English question that happens
    to quote an Arabic word is still answered in English, while a mostly-Arabic question
    carrying an English HR term is still answered in Arabic.
    """
    words = WORD_PATTERN.findall(unicodedata.normalize("NFKC", text or ""))
    if not words:
        return "en"

    arabic_words = sum(1 for word in words if ARABIC_LETTER_PATTERN.search(word))
    return "ar" if (arabic_words / len(words)) >= ARABIC_SHARE_REQUIRED else "en"
