"""
The seeded HR records and the policy corpus have to say the same thing.

They did not. Every employee held a flat 30-day annual entitlement, which is the top of
the ten-year service band, so four of five contradicted the ladder at HC-PC-001 §1.2.2.
Sick leave held the full-pay tranche presented as the whole entitlement. Grades sat about
five bands above the scale the policies cite, so the most junior employee qualified for
business-class travel. A question spanning both sources could not be answered correctly,
because the two sources disagreed.

These tests are the reason that cannot come back quietly.
"""

import re
from pathlib import Path

import pytest

from app.database.seed_employees import build_seed_employees
from app.domain.policy_catalog import POLICY_CATALOG

CORPUS = Path(__file__).resolve().parents[2] / "data" / "policies_en"

# HC-PC-001 §1.2.2. Years of continuous service -> total entitlement.
SERVICE_LADDER = [(0, 2, 21), (3, 5, 24), (6, 9, 26), (10, 99, 30)]

# Employees whose record departs from the ladder, and the reason the policy allows it.
DOCUMENTED_EXCEPTIONS = {
    "EMP007": "part-time at 0.6 FTE, pro-rated under HC-PC-001 §1.2.3",
    "EMP008": "contractual entitlement above the policy, permitted by HC-PC-001 §1.1",
}


def entitlement_for(years_of_service: int) -> int:
    return next(days for low, high, days in SERVICE_LADDER if low <= years_of_service <= high)


def annual_balance(record: dict, year: int = 2026):
    return next(
        balance for balance in record["balances"]
        if balance.leave_type == "Annual leave" and balance.year == year
    )


@pytest.mark.parametrize("record", build_seed_employees(), ids=lambda r: r["employee"].user_id)
def test_entitlement_matches_the_service_ladder(record):
    """Or departs from it for a reason the policy itself allows."""
    employee = record["employee"]
    expected = entitlement_for(employee.years_of_service)
    actual = annual_balance(record).entitled_days

    if employee.user_id in DOCUMENTED_EXCEPTIONS:
        assert actual != expected or employee.employment_fraction < 1.0
        return
    assert actual == expected, (
        f"{employee.user_id} has {employee.years_of_service} years of service, so "
        f"HC-PC-001 §1.2.2 entitles them to {expected} days, not {actual}"
    )


@pytest.mark.parametrize("record", build_seed_employees(), ids=lambda r: r["employee"].user_id)
def test_the_balance_adds_up(record):
    """remaining = entitled + carried over - used, on every row."""
    for balance in record["balances"]:
        assert balance.remaining_days == (
            balance.entitled_days + balance.carry_over_days - balance.used_days
        ), f"{record['employee'].user_id} {balance.leave_type} {balance.year} does not reconcile"


@pytest.mark.parametrize("record", build_seed_employees(), ids=lambda r: r["employee"].user_id)
def test_days_used_are_backed_by_approved_requests(record):
    """
    Otherwise "show me the requests behind my balance" has no answer, and the number the
    assistant quotes is unsupported by anything in the record.
    """
    approved = sum(
        request.days_requested
        for request in record["leave_requests"]
        if request.leave_type == "Annual Leave"
        and request.status == "Approved"
        and request.start_date.startswith("2026")
    )
    assert annual_balance(record).used_days == approved, (
        f"{record['employee'].user_id} shows days used that no approved request accounts for"
    )


@pytest.mark.parametrize("record", build_seed_employees(), ids=lambda r: r["employee"].user_id)
def test_sick_leave_models_the_whole_entitlement(record):
    """
    Ninety days across three pay tranches, as HC-PC-002 §2.2.1 sets out — not the 15-day
    full-pay tranche presented as though it were the entitlement.
    """
    tranches = [b for b in record["balances"] if "sick" in b.leave_type.lower()]

    assert len(tranches) == 3, f"{record['employee'].user_id} is missing sick leave tranches"
    assert sum(tranche.entitled_days for tranche in tranches) == 90
    assert sorted(tranche.pay_rate_pct for tranche in tranches) == [0, 50, 100]


def test_every_grade_is_one_the_grade_table_defines():
    """
    The scale used to run about five bands above the one the policies cite, so the most
    junior employee sat at the grade that grants business-class travel.
    """
    grade_table = (CORPUS / "07_definitions.md").read_text(encoding="utf-8")
    defined = set()
    for row in re.findall(r"^\|\s*(\d)(?:–(\d))?\s*\|", grade_table, re.MULTILINE):
        low, high = row
        defined.update(range(int(low), int(high or low) + 1))

    for record in build_seed_employees():
        grade = int(record["employee"].grade.removeprefix("Grade ").strip())
        assert grade in defined, (
            f"{record['employee'].user_id} is {record['employee'].grade}, which "
            f"HC-PC-007 §7.6 does not define"
        )


def test_every_cross_reference_resolves():
    """
    A reference to a section that does not exist is a dead end a reader cannot follow,
    and a chain the assistant cannot complete. Eleven of twenty used to dangle.
    """
    sections: dict[str, set[str]] = {}
    for path in sorted(CORPUS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        code = re.search(r"\*\*Document Reference:\*\*\s*(HC-PC-\d+)", text).group(1)
        sections[code] = set(re.findall(r"^###\s+(\d+\.\d+)", text, re.MULTILINE))

    broken = []
    for path in sorted(CORPUS.glob("*.md")):
        for code, section in re.findall(r"(HC-PC-\d+)\s*§(\d+\.\d+)", path.read_text(encoding="utf-8")):
            if section not in sections.get(code, set()):
                broken.append(f"{path.name} -> {code} §{section}")

    assert not broken, f"references pointing nowhere: {broken}"


def test_the_arabic_editions_state_the_same_numbers():
    """
    A bilingual policy that disagrees with itself is worse than one that is untranslated.
    The Arabic stub used to say 30 days where the English said 21, and 2.5 days a month
    where the English said 1.75.
    """
    arabic = (CORPUS.parent / "policies_ar" / "01_annual_leave.md").read_text(encoding="utf-8")

    for figure in ["21", "24", "26", "30", "1.75", "2.50", "10", "30 أبريل"]:
        assert figure in arabic, f"the Arabic annual leave policy is missing {figure!r}"
