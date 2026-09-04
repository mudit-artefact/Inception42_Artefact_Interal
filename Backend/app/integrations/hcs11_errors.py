"""
Custom exceptions for HCS-11 integration.

Each exception maps to a specific failure mode, so the API layer can
return the right HTTP status and the response formatter can produce
a helpful message.
"""


class HCS11Error(Exception):
    """Base exception for all HCS-11 integration failures."""
    pass


class HCS11ConnectionError(HCS11Error):
    """Could not reach the HCS-11 backend."""

    def __init__(self, message: str = "The document verification service is not available"):
        self.message = message
        super().__init__(message)


class HCS11TimeoutError(HCS11Error):
    """HCS-11 took too long to respond."""

    def __init__(self, message: str = "Document verification timed out. Please try again."):
        self.message = message
        super().__init__(message)


class HCS11ValidationError(HCS11Error):
    """HCS-11 rejected the request (4xx response)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HCS-11 error {status_code}: {detail}")


class HCS11CaseNotFoundError(HCS11Error):
    """No case exists for this employee/dependent combination."""

    def __init__(self, employee_id: str, message: str | None = None):
        self.employee_id = employee_id
        self.message = message or f"No active verification case found for employee {employee_id}"
        super().__init__(self.message)


class HCS11DocumentError(HCS11Error):
    """A document-specific error (wrong type, too large, unreadable)."""

    def __init__(self, filename: str, error_type: str, detail: str):
        self.filename = filename
        self.error_type = error_type
        self.detail = detail
        super().__init__(f"{filename}: {detail}")


class HCS11AlreadyPaidError(HCS11Error):
    """The case was already sent to payroll and cannot be modified."""

    def __init__(self, case_id: str, batch_id: str | None = None):
        self.case_id = case_id
        self.batch_id = batch_id
        message = f"Case {case_id} was already sent to payroll"
        if batch_id:
            message += f" in batch {batch_id}"
        message += ". Documents cannot be replaced."
        self.message = message
        super().__init__(message)
