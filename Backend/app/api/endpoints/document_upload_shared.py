"""
The parts of sending a document that do not care which document it is.

A school claim and a visa case differ in what a document means, what checks run against it
and what the answer looks like. They do not differ in what a file is, how large it may be,
or how progress is reported to a browser — so those live here and both routers import them
rather than each carrying its own copy that can drift from the other.

The one thing deliberately left behind is `HCS11AlreadyPaidError`. Only a school claim can
be closed by payroll; HCS-11's visa upload never returns 409.
"""

import json

from fastapi import HTTPException, UploadFile

from app.core.settings import settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def require_hcs11_enabled():
    """One flag covers both processes: they are the same service."""
    if not settings.hcs11_enabled:
        raise HTTPException(
            status_code=503,
            detail="Document verification service is not enabled",
        )


def validate_file(file: UploadFile) -> str | None:
    """
    Check a file before it is sent on. Returns what is wrong with it, or None.

    Checked here so an obviously unusable file is refused in a moment rather than after a
    round trip. HCS-11 checks again, and its answer is the one that decides — this is
    courtesy, not authority.
    """
    if not file.filename:
        return "File must have a name"

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return (
            f"'{file.filename}' is not a supported format. "
            "Please upload PDF, PNG, or JPEG files only."
        )

    if file.size and file.size > MAX_FILE_SIZE:
        return (
            f"'{file.filename}' is too large ({file.size / 1024 / 1024:.1f}MB). "
            "Maximum file size is 10MB."
        )

    return None


def sse_event(name: str, data: dict) -> str:
    """One server-sent event, in the shape a browser's EventSource expects."""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ReadableBytes:
    """
    Bytes that behave enough like a file for httpx to post them.

    An UploadFile cannot be read twice, and verification can take a minute, so the bytes
    are held here rather than the handle.
    """

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            result = self._data[self._pos:]
            self._pos = len(self._data)
        else:
            result = self._data[self._pos:self._pos + size]
            self._pos += len(result)
        return result

    def seek(self, pos: int) -> None:
        self._pos = pos
