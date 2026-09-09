"""
Pins the JSON contract of the two Omni HR endpoints the React sidebar calls.

Reference: Frontend/src/lib/api/employee.ts and Frontend/src/lib/api/types.ts
"""

import pytest

pytestmark = pytest.mark.contract

EMPLOYEE_LIST_ENDPOINT = "/api/omni/employees"
EMPLOYEE_DETAIL_ENDPOINT = "/api/omni/employee/{employee_id}"

# EmployeeCard.tsx and UserSwitcher.tsx read these off the profile.
REQUIRED_PROFILE_KEYS = {
    "id",
    "user_id",
    "name",
    "jobTitle",
    "role",
    "department",
    "grade",
    "manager",
    "balances",
    "policyLinks",
}


def test_employee_list_returns_the_seeded_people(api_client):
    response = api_client.get(EMPLOYEE_LIST_ENDPOINT)

    assert response.status_code == 200, response.text
    employees = response.json()
    assert isinstance(employees, list) and employees
    for employee in employees:
        assert REQUIRED_PROFILE_KEYS <= set(employee)


def test_employee_detail_uses_the_camel_case_keys_the_frontend_reads(api_client):
    """`jobTitle` and `policyLinks` are camelCase on the wire and must stay that way."""
    response = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP001"))

    assert response.status_code == 200, response.text
    profile = response.json()
    assert REQUIRED_PROFILE_KEYS <= set(profile)
    assert "jobTitle" in profile
    assert "policyLinks" in profile


def test_leave_balances_carry_the_four_keys_the_card_renders(api_client):
    response = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP001"))

    balances = response.json()["balances"]
    assert balances, "the employee card renders a row per leave balance"
    for leave_balance in balances:
        assert {"type", "used", "entitled", "unit"} <= set(leave_balance)


def test_unknown_employee_is_reported_as_not_found(api_client):
    """
    Defect 2: an unknown identifier used to return 200 with a fabricated employee called
    "Employee" who had twenty invented leave days.
    """
    response = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP999"))

    assert response.status_code == 404
    assert "EMP999" in response.json()["detail"]


def test_the_arbitrary_sql_endpoint_is_gone(api_client):
    """
    Defect 4: this ran caller-supplied SQL against the HR database with no authentication,
    guarded only by a check on the statement's first word.
    """
    response = api_client.post("/api/omni/sql/query", json={"query": "SELECT 1"})

    assert response.status_code == 404


def test_an_unknown_employee_is_not_invented_for_the_assistant_either(temporary_database):
    """The same fabricated record used to reach the language model's prompt."""
    from app.core.errors import EmployeeNotFoundError
    from app.database.employee_lookup import get_employee_facts_for

    with pytest.raises(EmployeeNotFoundError):
        get_employee_facts_for("EMP999")


# ── what the dashboard reads ─────────────────────────────────────────────────
#
# A page that shows different things to different people needs to know which person it
# is looking at. Both of these facts were in the database and neither reached the
# browser, so the only way to tell a new joiner from a current employee was to guess
# from the wording of a question.

LEAVE_REQUESTS_ENDPOINT = "/api/omni/employee/{employee_id}/leave-requests"
APPROVALS_ENDPOINT = "/api/omni/employee/{employee_id}/approvals"


def test_the_profile_says_whether_somebody_has_started(api_client):
    joining = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP013")).json()
    started = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP001")).json()

    assert joining["employment_status"] == "Onboarding"
    assert started["employment_status"] == "Active"


def test_the_profile_says_whether_somebody_manages_anyone(api_client):
    """
    There is no "is a manager" flag in this system. Managing is having reports, and the
    count is the only honest way to ask.
    """
    manager = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP001")).json()
    nobody = api_client.get(EMPLOYEE_DETAIL_ENDPOINT.format(employee_id="EMP013")).json()

    assert manager["direct_reports"] > 0
    assert nobody["direct_reports"] == 0


def test_an_employees_leave_requests_are_listed_newest_first(api_client):
    response = api_client.get(LEAVE_REQUESTS_ENDPOINT.format(employee_id="EMP001"))

    assert response.status_code == 200, response.text
    requests = response.json()
    assert requests, "EMP001 has seeded leave requests"
    assert {"id", "leave_type", "start_date", "end_date", "days_requested", "status",
            "created_at"} <= set(requests[0])

    starts = [request["start_date"] for request in requests]
    assert starts == sorted(starts, reverse=True), "newest first"


def test_the_list_is_the_whole_history_not_only_what_is_waiting(api_client):
    """
    The screen shows what somebody has asked for. Filtering to `Pending` — which is what
    the one existing reader of this table does — would show an employee almost nothing.
    """
    requests = api_client.get(LEAVE_REQUESTS_ENDPOINT.format(employee_id="EMP001")).json()

    assert {request["status"] for request in requests} != {"Pending"}
    assert any(request["status"] == "Approved" for request in requests)


def test_a_manager_sees_what_is_waiting_on_them(api_client):
    response = api_client.get(APPROVALS_ENDPOINT.format(employee_id="EMP001"))

    assert response.status_code == 200, response.text
    waiting = response.json()
    assert waiting, "EMP011's request names EMP001 as approver"
    assert {"request_id", "employee_name", "leave_type", "days_requested"} <= set(waiting[0])
    assert all(item["status"] == "Pending" for item in waiting)


def test_the_request_id_is_sent_so_a_card_can_name_the_request(api_client):
    """
    The bell menu already holds this id and throws it away, sending a generic sentence
    instead — so it cannot open the request it came from. Anything built on this endpoint
    has the id and should use it.
    """
    waiting = api_client.get(APPROVALS_ENDPOINT.format(employee_id="EMP001")).json()

    assert all(isinstance(item["request_id"], int) for item in waiting)


def test_somebody_who_manages_nobody_has_nothing_to_approve(api_client):
    response = api_client.get(APPROVALS_ENDPOINT.format(employee_id="EMP013"))

    assert response.status_code == 200
    assert response.json() == []


def test_an_employee_is_never_shown_their_own_request_to_approve(api_client):
    """A manager approving their own leave is the one thing this list must not offer."""
    waiting = api_client.get(APPROVALS_ENDPOINT.format(employee_id="EMP001")).json()

    assert all(item["employee_id"] != "EMP001" for item in waiting)
