"""
The modules that each kept their own copy of something are gone, not just unused.

Three stores of conversation history existed at once: two modules held their own with
identical accessor functions and a comment claiming they were shared, and later a third
recorded every turn that nothing ever read. Each was removed rather than left in place
pointing at the survivor, because a store that still imports is a store somebody wires
back up.

What a conversation remembers now lives in its saved state — see
app/workflow/conversation_memory.py.
"""

import importlib
import pathlib

import pytest

RETIRED_MODULES = (
    "app.rag_engine",
    "app.agents.rag_agent",
    "app.services.conversation_history_service",
)


@pytest.mark.parametrize("retired_module", RETIRED_MODULES)
def test_a_retired_module_cannot_be_imported(retired_module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(retired_module)


# A script, not a module, so it is asserted on by path. `scripts/` has no __init__.py:
# import_module would raise ModuleNotFoundError whether or not the file existed, and the
# test would pass while proving nothing.
BACKEND_DIRECTORY = pathlib.Path(__file__).resolve().parents[2]

RETIRED_SCRIPTS = (
    (
        "scripts/generate_arabic_policy_pdfs.py",
        "It wrote the same five filenames as scripts/generate_policy_pdfs.py, so running "
        "it replaced every good Arabic PDF. It drew Arabic in Helvetica, which has no "
        "Arabic glyphs, so ReportLab substituted a dingbat for every letter — the failure "
        "policy_chunk_builder refuses passages for. Its text was also hand-written rather "
        "than rendered from the Markdown, and disagreed with it: a medical certificate at "
        "two days against §2.3.2's third, carry-over of 5 days by 31 March against §1.5's "
        "10 by 30 April, expense bands of 500/2,500 against §5.7.2's 1,500/7,500. It also "
        "renumbered every document's sections to 1.1, 1.2, which breaks page resolution. "
        "generate_policy_pdfs.py --language ar replaces it and renders from the Markdown.",
    ),
)


@pytest.mark.parametrize("relative_path, reason", RETIRED_SCRIPTS)
def test_a_retired_script_has_not_come_back(relative_path, reason):
    assert not (BACKEND_DIRECTORY / relative_path).exists(), (
        f"{relative_path} is back. {reason}"
    )
