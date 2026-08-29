"""
The errors this application raises on purpose.

Each one describes a situation in business terms. The API layer decides what HTTP status
each should become, so nothing below the API layer needs to know about HTTP.
"""


class ApplicationError(Exception):
    """Base class for every deliberate error in this application."""


class EmployeeNotFoundError(ApplicationError):
    """No employee exists with the given identifier."""

    def __init__(self, employee_id: str) -> None:
        self.employee_id = employee_id
        super().__init__(f"No employee found with the identifier '{employee_id}'.")


class PolicyIndexEmptyError(ApplicationError):
    """The policy search index has not been built yet, so nothing can be retrieved."""

    def __init__(self) -> None:
        super().__init__(
            "The policy index is empty. Rebuild it with POST /api/v1/hcs01/policies/reindex."
        )


class LanguageModelUnavailableError(ApplicationError):
    """The language model could not be reached, so no answer can be produced."""

    def __init__(self, underlying_error: Exception | None = None) -> None:
        self.underlying_error = underlying_error
        super().__init__(f"The language model is unavailable: {underlying_error}")
