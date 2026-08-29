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
