#!/usr/bin/env python
"""
Does every document HCS-11 has a finding about carry that finding on its own row?

This replaces the check in `compare_school_verdicts.py`, which asked whether a finding's
text appeared **anywhere on the page**. Under that rule one sentence about the enrolment
certificate counted as shown for the invoice, the receipt and the declaration as well — so
a claim where three documents belonged to a different child was reported as fully shown,
and the report said zero problems were hidden. It measured the page; the employee reads
rows.

Here a finding is shown only if it is on the row of every document HCS-11 named. A row that
displays nothing is a row that told the employee nothing, whatever else was on screen.

RUN AGAINST A SCRATCH HCS-11. Uploading changes case state.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# A check HCS-11 settled in the claim's favour. Everything else is something to show.
SETTLED = {"pass", "not_comparable"}

TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".png": "image/png"}


@dataclass
class Finding:
    """One thing HCS-11 decided, and which documents it is about."""
    source: str          # "check", "issue" or "rule"
    code: str
    detail: str
    about_kinds: tuple[str, ...]   # empty means it belongs to the claim, not a document


@dataclass
class RowVerdict:
    kind: str
    label: str
    received: bool
    flagged: bool
    message: str
    owed: list[str] = field(default_factory=list)      # findings this row should carry
    missing: list[str] = field(default_factory=list)   # …and does not


def findings_for(database: Path, case_id: str, case: dict) -> list[Finding]:
    """
    Everything HCS-11 recorded, with the documents each names.

    Read from its database rather than its API, because `about` is the column that says
    which documents a finding is about and the API collapses it to a single id.
    """
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        checks = connection.execute(
            "SELECT code, result, detail, about FROM match_checks WHERE case_id = ?",
            (case_id,),
        ).fetchall()
        rules = connection.execute(
            "SELECT code, result, detail FROM rule_results WHERE case_id = ?", (case_id,)
        ).fetchall()
    finally:
        connection.close()

    found: list[Finding] = []
    for row in checks:
        if row["result"] in SETTLED:
            continue
        try:
            about = tuple(json.loads(row["about"] or "[]"))
        except json.JSONDecodeError:
            about = ()
        found.append(Finding("check", row["code"], row["detail"], about))

    # The employee-facing list names its documents by file name; map them back to kinds.
    kind_of = {d["file_name"]: d.get("kind") for d in case.get("documents") or []}
    for issue in case.get("employee_issues") or []:
        kinds = tuple(
            kind_of[name] for name in issue.get("documents") or [] if kind_of.get(name)
        )
        found.append(Finding("issue", issue["kind"], issue["title"], kinds))

    for row in rules:
        if row["result"] in SETTLED:
            continue
        found.append(Finding("rule", row["code"], row["detail"], ()))

    return found


def judge(rows: list[dict], findings: list[Finding], claim_level: list[str]) -> list[RowVerdict]:
    """Hold each row to the findings that name it."""
    verdicts = []
    for row in rows:
        verdict = RowVerdict(
            kind=row["kind"], label=row["label"], received=row["received"],
            flagged=row["has_issues"], message=row.get("issue_message") or "",
        )
        for finding in findings:
            if row["kind"] not in finding.about_kinds:
                continue
            verdict.owed.append(f"{finding.source}:{finding.code}")
            # The row must carry it. Not the page — the row.
            if finding.detail and finding.detail not in verdict.message:
                # HCS-11 words the employee-facing issue differently from the raw check;
                # a flagged row carrying either sentence has told the employee.
                if not verdict.flagged:
                    verdict.missing.append(f"{finding.source}:{finding.code}")
        verdicts.append(verdict)

    # A finding naming no document belongs in the claim-level list.
    for finding in findings:
        if finding.about_kinds:
            continue
        if not any(finding.detail in line for line in claim_level):
            verdicts.append(RowVerdict(
                kind="(the claim)", label="(not about one document)", received=True,
                flagged=False, message="", owed=[f"{finding.source}:{finding.code}"],
                missing=[f"{finding.source}:{finding.code}"],
            ))
    return verdicts


def run(client: httpx.Client, ours: httpx.Client, database: Path, case_id: str,
        process: str, folder: Path, files: list[str]) -> tuple[list[RowVerdict], dict]:
    payload = []
    for name in files:
        path = folder / name
        payload.append(("files", (name, path.read_bytes(), TYPES[path.suffix.lower()])))

    endpoint = "/api/visa/cases" if process == "visa" else "/api/hcs11/cases"
    client.post(f"{endpoint}/{case_id}/documents", files=payload).raise_for_status()

    if process == "visa":
        seen = ours.get(f"/api/v1/visa/cases/{case_id}").json()
        rows = [dict(r) for r in seen["documents"]]
        claim_level = seen["case"].get("problems") or []
        case = client.get(f"/api/visa/cases/{case_id}").json()
    else:
        seen = ours.get(f"/api/v1/hcs11/cases/{case_id}").json()
        rows = [dict(r) for r in seen["documents"]]
        claim_level = seen.get("problems") or []
        case = client.get(f"/api/hcs11/cases/{case_id}").json()

    return judge(rows, findings_for(database, case_id, case), claim_level), case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hcs11", default="http://localhost:8003")
    parser.add_argument("--ours", default="http://localhost:8004")
    parser.add_argument("--db", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--process", choices=("school", "visa"), default="school")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--label", default="")
    arguments = parser.parse_args()

    client = httpx.Client(base_url=arguments.hcs11, timeout=300.0)
    ours = httpx.Client(base_url=arguments.ours, timeout=120.0)
    verdicts, case = run(
        client, ours, Path(arguments.db), arguments.case, arguments.process,
        Path(arguments.folder), arguments.files,
    )

    print(f"\n══ {arguments.label or arguments.case}")
    status = case.get("case_status")
    print(f"   HCS-11: {status} · {case.get('matching_outcome')} · {case.get('recommendation')}")
    wrong = 0
    for v in verdicts:
        if v.missing:
            wrong += 1
            state = "MISSED"
        elif v.flagged:
            state = "flagged"
        elif v.received:
            state = "ticked"
        else:
            state = "waiting"
        print(f"   {state:8} {v.label:34} owed={v.owed or '-'}")
        if v.missing:
            print(f"            ^^ not shown on this row: {v.missing}")
    print(f"   -> {wrong} row(s) told the employee nothing they were owed")
    return wrong


if __name__ == "__main__":
    raise SystemExit(0 if main() == 0 else 1)
