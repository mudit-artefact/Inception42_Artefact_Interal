"""
Defect 5: two contradictory language detectors.

The web layer called any text containing a single Arabic character Arabic. The query
layer required Arabic to be more than 30 percent of the characters. The same sentence got
two different answers depending on which one ran, and the reply language followed.
"""

import pytest

from app.core.language_detection import detect_language


@pytest.mark.parametrize(
    "text, expected_language",
    [
        ("How many annual leave days do I have?", "en"),
        ("Hello", "en"),
        ("كم يوم إجازة سنوية متبقي لي؟", "ar"),
        ("مرحبا", "ar"),
        # The sentence the two old detectors disagreed about.
        ("Do I get 3 أيام of leave?", "en"),
        ("", "en"),
    ],
)
def test_language_is_detected_from_the_dominant_script(text, expected_language):
    assert detect_language(text) == expected_language


def test_there_is_only_one_detector_left():
    """The second implementation has been removed rather than left to drift again."""
    import importlib

    for retired_module in ("app.query_transform", "app.orchestrator"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(retired_module)
