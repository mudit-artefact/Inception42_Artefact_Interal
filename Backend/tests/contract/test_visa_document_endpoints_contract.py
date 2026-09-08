"""
The endpoints the visa document window talks to.

Nothing in this project tested the school upload endpoints — not the routes, not the file
check, not the streaming contract. This sets the precedent on the visa side, where the
window is being written against these shapes right now.

HCS-11 is never called. Every test replaces the client with one that returns a case it
states itself, so a failure here is this application's fault and not a service being down.
"""

import io
import json
from contextlib import asynccontextmanager

import pytest

from app.integrations.hcs11_errors import (
    HCS11CaseNotFoundError,
    HCS11ConnectionError,
    HCS11DocumentError,
)
from app.integrations.hcs11_schemas import VisaCaseOut

pytestmark = pytest.mark.contract

A_CASE = {
    "case_id": "VISA0003",
    "employee_id": "E0015",
    "employee_name": "Daniel Okonkwo",
    "plan_code": "VISA_STANDARD",
    "plan_name": "Employment visa — no degree required",
    "case_status": "Awaiting Submission",
    "submission_deadline": "2026-10-07",
    "required_documents": ["passport", "photograph", "job_offer"],
    "missing_documents": ["photograph", "job_offer"],
    "documents": [
        {"document_id": "D1", "file_name": "passport.pdf", "kind": "passport",
         "kind_label": "Passport copy", "uploaded_at": "2026-09-08T10:00:00+00:00"},
    ],
    "checks": [],
    "problems": [],
}


class FakeHCS11:
    """Answers the three calls the visa router makes, or raises what it was told to."""

    def __init__(self, case=None, raises=None):
        self._case = VisaCaseOut(**(case or A_CASE))
        self._raises = raises
        self.uploaded: list[tuple] = []

    async def list_visa_cases(self, employee_id):
        if self._raises:
            raise self._raises
        return [self._case]

    async def get_visa_case(self, case_id):
        if self._raises:
            raise self._raises
        return self._case

    async def upload_documents(self, case_id, files, process="school"):
        if self._raises:
            raise self._raises
        self.uploaded.append((case_id, process, [name for name, _, _ in files]))
        return self._case


@pytest.fixture
def hcs11(monkeypatch):
    def standing_in(case=None, raises=None) -> FakeHCS11:
        fake = FakeHCS11(case=case, raises=raises)

        @asynccontextmanager
        async def client():
            yield fake

        monkeypatch.setattr(
            "app.api.endpoints.visa_documents.get_hcs11_client", lambda: client()
        )
        return fake

    return standing_in


def a_file(name="passport.pdf", content=b"%PDF-1.4 pretend", kind="application/pdf"):
    return ("files", (name, io.BytesIO(content), kind))


# ── reading ──────────────────────────────────────────────────────────────────


def test_the_cases_for_one_new_joiner_are_listed(api_client, hcs11):
    hcs11()

    response = api_client.get("/api/v1/visa/cases", params={"employee_id": "EMP015"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert body["cases"][0]["case_id"] == "VISA0003"


def test_one_case_arrives_with_its_checklist_already_worked_out(api_client, hcs11):
    """
    Derived on this side, not in the browser. HCS-11 sends kind strings and a separate
    list of what is outstanding; turning that into rows is this application's job.
    """
    hcs11()

    body = api_client.get("/api/v1/visa/cases/VISA0003").json()

    rows = {row["kind"]: row for row in body["documents"]}
    assert list(rows) == ["passport", "photograph", "job_offer"]
    assert rows["passport"]["received"] is True
    assert rows["passport"]["filename"] == "passport.pdf"
    assert rows["photograph"]["received"] is False


def test_a_case_that_does_not_exist_is_a_404(api_client, hcs11):
    hcs11(raises=HCS11CaseNotFoundError(employee_id="EMP015", message="gone"))

    assert api_client.get("/api/v1/visa/cases/VISA9999").status_code == 404


def test_the_service_being_down_is_a_503_not_a_crash(api_client, hcs11):
    hcs11(raises=HCS11ConnectionError())

    response = api_client.get("/api/v1/visa/cases", params={"employee_id": "EMP015"})

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


# ── sending ──────────────────────────────────────────────────────────────────


def test_a_document_reaches_hcs11_on_the_visa_path(api_client, hcs11):
    """
    The one thing that must not be wrong: a visa document sent down the school path would
    land on somebody's education claim.
    """
    fake = hcs11()

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents", files=[a_file()]
    )

    assert response.status_code == 200, response.text
    assert fake.uploaded == [("VISA0003", "visa", ["passport.pdf"])]


def test_the_answer_carries_the_checklist_and_no_payment(api_client, hcs11):
    hcs11()

    body = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents", files=[a_file()]
    ).json()

    assert [row["kind"] for row in body["documents"]] == [
        "passport", "photograph", "job_offer"
    ]
    assert "payment_amount" not in body
    assert "payment_status" not in body


@pytest.mark.parametrize(
    "name,kind",
    [("notes.txt", "text/plain"), ("sheet.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")],
)
def test_a_file_of_the_wrong_kind_is_refused_before_hcs11_is_troubled(
    api_client, hcs11, name, kind
):
    fake = hcs11()

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents", files=[a_file(name=name, kind=kind)]
    )

    assert response.status_code == 422
    assert "PDF, PNG, or JPEG" in response.json()["detail"]
    assert fake.uploaded == []


def test_an_empty_file_is_refused(api_client, hcs11):
    """HCS-11 rejects these; saying so here saves a round trip and reads better."""
    fake = hcs11()

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents", files=[a_file(content=b"")]
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()
    assert fake.uploaded == []


def test_hcs11_refusing_a_document_is_passed_on_in_words(api_client, hcs11):
    hcs11(raises=HCS11DocumentError(
        error_type="too_large", detail="too big", filename="passport.pdf"
    ))

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents", files=[a_file()]
    )

    assert response.status_code == 422
    assert "passport.pdf" in response.json()["detail"]


# ── sending, with progress ───────────────────────────────────────────────────


def _events(raw: str) -> list[tuple[str, dict]]:
    parsed = []
    for block in raw.strip().split("\n\n"):
        lines = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line
        )
        parsed.append((lines.get("event", ""), json.loads(lines.get("data", "{}"))))
    return parsed


def test_the_stream_reports_progress_then_the_whole_result(api_client, hcs11):
    """
    The school stream omits the checklist from its final event, and its own client then
    hardcodes an empty one. This carries every field the plain endpoint returns.
    """
    hcs11()

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents/stream", files=[a_file()]
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert [name for name, _ in events][-1] == "complete"
    assert any(name == "stage" for name, _ in events)

    finished = events[-1][1]
    assert [row["kind"] for row in finished["documents"]] == [
        "passport", "photograph", "job_offer"
    ]
    assert finished["case_id"] == "VISA0003"


def test_the_stream_reports_a_failure_as_an_event_not_a_broken_connection(api_client, hcs11):
    hcs11(raises=HCS11ConnectionError())

    response = api_client.post(
        "/api/v1/visa/cases/VISA0003/documents/stream", files=[a_file()]
    )

    assert response.status_code == 200
    name, payload = _events(response.text)[-1]
    assert name == "error"
    assert "unavailable" in payload["detail"].lower()
