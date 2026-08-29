"""
Ranking a set of candidate passages.

Dense vector search and lexical (BM25) matching each produce a ranking, and the two are
combined with Reciprocal Rank Fusion.

One number, `relevance_score`, is both what the results are sorted by and what is
reported to the caller. Previously results were sorted by the fused score but reported a
different, inflated number (the cosine similarity multiplied by 1.1), so the web
interface could show a lower percentage above a higher one.
"""

import re
import unicodedata

RECIPROCAL_RANK_FUSION_CONSTANT = 60
BM25_TERM_SATURATION = 1.5
BM25_LENGTH_NORMALISATION = 0.75
ASSUMED_AVERAGE_PASSAGE_LENGTH = 120.0
ASSUMED_INVERSE_DOCUMENT_FREQUENCY = 1.5
MINIMUM_TOKEN_LENGTH = 3


# Arabic is written many ways for the same word. A policy writes بعد, a reader types
# بُعد, a form prints بُعْد. All three must reach the index as one token.
_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_FOLDINGS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا",   # hamza-carrying alef -> plain alef
    "ة": "ه",                        # ta marbuta -> ha
    "ى": "ي",                        # alef maqsura -> ya
    "ؤ": "و", "ئ": "ي",
})


def normalise_arabic(text: str) -> str:
    """
    One spelling per word.

    Two separate problems. Presentation forms — the joined shapes a PDF stores Arabic as
    — are folded back to ordinary letters by NFKC. Then the optional marks a writer may
    or may not add are removed, and the letters that are written several ways are folded
    together.

    The diacritics matter more than they look. Word matching does not span a non-spacing
    mark, so
    a vowel in the middle of a word split it into fragments that were then dropped for
    being too short: `بُعد`, the most distinctive word in the remote-work policy, indexed
    as nothing at all.
    """
    folded = unicodedata.normalize("NFKC", text)
    return _ARABIC_DIACRITICS.sub("", folded).translate(_ARABIC_FOLDINGS)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, ignoring very short ones. Arabic is normalised first."""
    return [
        word.lower()
        for word in re.findall(r"\w+", normalise_arabic(text))
        if len(word) >= MINIMUM_TOKEN_LENGTH
    ]


def score_lexical_match(query_tokens: list[str], passage_tokens: list[str]) -> float:
    """A BM25 score for how well a passage matches the query's words."""
    if not query_tokens or not passage_tokens:
        return 0.0

    passage_length = len(passage_tokens)
    occurrences_by_token: dict[str, int] = {}
    for token in passage_tokens:
        occurrences_by_token[token] = occurrences_by_token.get(token, 0) + 1

    score = 0.0
    for query_token in query_tokens:
        occurrences = occurrences_by_token.get(query_token, 0)
        if occurrences == 0:
            continue
        length_penalty = 1 - BM25_LENGTH_NORMALISATION + BM25_LENGTH_NORMALISATION * (
            passage_length / ASSUMED_AVERAGE_PASSAGE_LENGTH
        )
        saturated_frequency = (occurrences * (BM25_TERM_SATURATION + 1)) / (
            occurrences + BM25_TERM_SATURATION * length_penalty
        )
        score += ASSUMED_INVERSE_DOCUMENT_FREQUENCY * saturated_frequency
    return score


def fuse_rankings(dense_rank: int, lexical_rank: int) -> float:
    """
    Combine two 1-based rankings into a single relevance score between 0 and 1.

    A passage ranked first by both methods scores 1.0; anything ranked lower scores less.
    """
    fused = (1.0 / (RECIPROCAL_RANK_FUSION_CONSTANT + dense_rank)) + (
        1.0 / (RECIPROCAL_RANK_FUSION_CONSTANT + lexical_rank)
    )
    best_possible = 2.0 / (RECIPROCAL_RANK_FUSION_CONSTANT + 1)
    return min(fused / best_possible, 1.0)
