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
