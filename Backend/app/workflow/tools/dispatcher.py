"""
The one way a tool is run.

Everything an action does to the database goes through `run_tool`, and that is the point:
it is the single place that decides a write may proceed, and the single place that turns a
failure into something an employee can be shown.

The default is deliberately the safe one. `authorised_to_write` starts False, so a caller
that forgets it does not quietly perform the write — it gets a refusal. The alternative
default fails open, and a permission check that can be forgotten is one that eventually is.
"""

import logging
from typing import Any

from app.workflow.tools.registry import TOOLS, ToolOutcome

logger = logging.getLogger(__name__)

# Reasons a tool did not run, or ran and declined. These are codes, not sentences: the
# words an employee reads are chosen later, in their own language. An exception's own text
# never becomes one of these — it goes to the log with its traceback and stops there.
UNKNOWN_TOOL = "unknown_tool"
MISSING_ARGUMENTS = "missing_arguments"
NOT_AUTHORISED = "not_authorised"
THE_ACTION_FAILED = "the_action_failed"
DECLINED = "declined"


def run_tool(tool_name: str, *, authorised_to_write: bool = False, **arguments: Any) -> ToolOutcome:
    """
    Run one registered tool and describe what happened.

    Never raises. A tool that blows up, a tool that was never registered and a tool that
    refuses the request all come back the same way, so no caller has to remember which
    kinds of failure it has to catch.
    """
    specification = TOOLS.get(tool_name)
    if specification is None:
        logger.error(f"No such tool: {tool_name}")
        return ToolOutcome(ok=False, tool_name=tool_name, failure=UNKNOWN_TOOL)

    missing = [
        name
        for name in specification.required_arguments
        if arguments.get(name) is None
    ]
    if missing:
        logger.info(f"{tool_name} was not run; it still needs {', '.join(missing)}")
        return ToolOutcome(
            ok=False,
            tool_name=tool_name,
            failure=MISSING_ARGUMENTS,
            result={"missing": missing},
        )

    if specification.mutates and not authorised_to_write:
        logger.warning(f"{tool_name} changes records and was not authorised; refusing")
        return ToolOutcome(ok=False, tool_name=tool_name, failure=NOT_AUTHORISED)

    try:
        result = specification.run(**arguments)
    except Exception as error:
        # The traceback belongs here, and nowhere the employee can see. Returning
        # str(error) to the chat window used to put SQLAlchemy's own words, and the
        # statement it was running, in front of whoever asked for two days off.
        logger.error(f"{tool_name} failed: {error}", exc_info=True)
        return ToolOutcome(ok=False, tool_name=tool_name, failure=THE_ACTION_FAILED)

    # Several of these services report a refusal by returning success=False with a
    # sentence of their own, rather than raising. That sentence is ours and is safe to
    # show; it travels in `result` while `failure` stays a code.
    if isinstance(result, dict) and result.get("success") is False:
        logger.info(f"{tool_name} declined: {result.get('message', '')}")
        return ToolOutcome(ok=False, tool_name=tool_name, failure=DECLINED, result=result)

    return ToolOutcome(ok=True, tool_name=tool_name, result=result)
