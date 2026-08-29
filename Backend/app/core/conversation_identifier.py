"""
Naming a conversation.

The same "conv-{milliseconds}" expression was written out in four places, and a fifth
place used "conv-{employee_id}" instead — which would have collapsed every conversation
by the same employee onto one thread. This is the one way a conversation gets named.
"""

from typing import Optional
from uuid import uuid4

CONVERSATION_IDENTIFIER_PREFIX = "conversation"


def create_conversation_identifier() -> str:
    """
    A fresh identifier for a conversation that does not have one yet.

    Random rather than the millisecond clock it used to be. A conversation now carries
    what was said in it, so a name that can be guessed — or arrived at by counting — is
    a way to read somebody else's. Two conversations starting in the same millisecond
    also used to be given the same name and share a thread.
    """
    return f"{CONVERSATION_IDENTIFIER_PREFIX}-{uuid4().hex}"


def use_or_create_conversation_identifier(supplied_identifier: Optional[str]) -> str:
    """The caller's identifier when they sent one, otherwise a fresh one."""
    return supplied_identifier or create_conversation_identifier()
