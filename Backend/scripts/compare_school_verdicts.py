#!/usr/bin/env python
"""
Does our screen show what HCS-11 actually decided?

An employee uploads four documents and is told they are fine. HCS-11's own record says one
of them is not. That is the worst failure this feature has: the employee stops, and nobody
finds out until a person opens the claim in the other system weeks later.

This script settles it with evidence rather than argument. For every demo scenario it
uploads the files, then puts two things side by side:

    what HCS-11 recorded    — its employee_issues, its failing checks, its failing rules
    what our screen shows   — the same derivation `DocumentUpload.tsx` performs, ported
                              below line for line, including its lookup tables

and classifies every problem HCS-11 found:

    shown     the employee sees it
    HIDDEN    HCS-11 found it, our screen shows nothing — the bug
    invented  our screen shows a problem HCS-11 did not find — the opposite bug

Both counts must be zero. `hidden` is the number that matters.

RUN IT AGAINST A SCRATCH COPY, NEVER AGAINST THE LIVE HCS-11. Uploading changes case state.
Set HCS11_STORAGE to a scratch directory and start a second instance on another port:

    sqlite3 -readonly "file:<their>/storage/hcs11.sqlite?mode=ro" ".backup '<scratch>/hcs11.sqlite'"
    cd <hcs-11>/backend && HCS11_STORAGE=<scratch> .venv/bin/uvicorn app.main:app --port 8003

That gives the instance its own database and its own uploaded-files folder, which is what
`hcs-11/backend/app/settings.py` calls out as the supported way to run a scratch copy.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── what the screen believes, ported from the browser ────────────────────────────────
#
# Copied verbatim from Frontend/src/components/concierge/DocumentUpload.tsx so the
# comparison is against the real screen and not against a charitable summary of it. When
# the screen is fixed these tables go, and so does this block.

CHECK_CODE_TO_DOC_KIND = {
    "DEPENDENT_NAME": "enrolment_certificate",
    "DEPENDENT_DOB": "enrolment_certificate",
    "PARENT_NAME": "enrolment_certificate",
    "ENROLMENT_CONFLICT": "enrolment_certificate",
    "INVOICE_IS_SAME_CHILD": "school_invoice",
    "RECEIPT_REFERENCES_INVOICE": "payment_receipt",
    "PAID_NOT_MORE_THAN_INVOICED": "payment_receipt",
    "RECEIPT_NOT_BEFORE_INVOICE": "payment_receipt",
    "DECLARATION_IS_THIS_EMPLOYEE": "employee_declaration",
}

CROSS_DOC_CHECKS = {"SAME_ACADEMIC_YEAR", "SAME_SCHOOL"}

ISSUE_KIND_TO_DOC_KIND = {
    "wrong_signer": "employee_declaration",
    "name_mismatch": "enrolment_certificate",
    "dob_mismatch": "enrolment_certificate",
}


def what_the_screen_shows(case: dict) -> set[str]:
    """
    Every problem the panel puts in front of the employee, as `source:key` labels.

    `getDocumentIssues` and `getCrossDocumentIssues` in DocumentUpload.tsx, followed
    exactly — a check or issue that falls through every branch there falls through here.
    """
    shown: set[str] = set()

    for issue in case.get("employee_issues") or []:
        if ISSUE_KIND_TO_DOC_KIND.get(issue["kind"]):
            shown.add(f"issue:{issue['kind']}")

    for check in case.get("match_checks") or []:
        # The panel's own guard was `!== "fail" && !== "review"`, so a `missing` check
        # was skipped outright. That is part of what it hid, and is left exactly as it
        # was — the point is to measure the panel, not to improve it here.
        if check["result"] not in ("fail", "review"):
            continue
        if check["code"] in CROSS_DOC_CHECKS:
            shown.add(f"check:{check['code']}")     # the cross-document section
        elif CHECK_CODE_TO_DOC_KIND.get(check["code"]):
            shown.add(f"check:{check['code']}")     # against its row

    return shown


def what_the_fixed_screen_shows(case: dict, rules: list[dict]) -> set[str]:
    """
    The same question asked of the repaired panel, which displays what the server decided.

    The test is harder than the one above, and deliberately: it is not enough for a problem
    to be counted somewhere. HCS-11's own sentence about it has to appear on the screen,
    either beside the file it is about or in the claim-level list. A finding reduced to a
    tick in a total would pass the old test and still tell the employee nothing.
    """
    from app.integrations.hcs11_response_formatter import format_upload_result
    from app.integrations.hcs11_schemas import CaseDetail

    verdict = format_upload_result(CaseDetail(**case))
    on_screen = " ".join(
        [row.issue_message or "" for row in verdict.documents] + verdict.issues
    )

    shown = set()
    for issue in case.get("employee_issues") or []:
        if issue["title"] and issue["title"] in on_screen:
            shown.add(f"issue:{issue['kind']}")
    for check in case.get("match_checks") or []:
        if is_a_finding(check, case) and check["detail"] in on_screen:
            shown.add(f"check:{check['code']}")
    for rule in rules:
        if rule["result"] in NOT_SETTLED and rule["detail"] in on_screen:
            shown.add(f"rule:{rule['code']}")
    return shown


def the_fixed_banner_is_green(case: dict) -> bool:
    """
    The repaired banner: every file in, nothing outstanding, and HCS-11 itself content.

    The third condition is the one that was missing.
    """
    from app.api.endpoints.hcs11_documents import NOTHING_LEFT_TO_DO
    from app.integrations.hcs11_response_formatter import format_upload_result
    from app.integrations.hcs11_schemas import CaseDetail

    verdict = format_upload_result(CaseDetail(**case))
    required = case.get("required_documents") or []
    everything_arrived = bool(required) and all(row["received"] for row in required)
    nothing_outstanding = not any(row.has_issues for row in verdict.documents) and not verdict.issues
    return everything_arrived and nothing_outstanding and verdict.status in NOTHING_LEFT_TO_DO


def the_banner_is_green(case: dict) -> bool:
    """
    "Everything we need is here" — DocumentUpload.tsx:514.

    `allDocumentsReceived && !hasIssues`, where hasIssues counts only what the tables above
    recognised. HCS-11's own verdict — route, recommendation, case_status — is not consulted.
    """
    required = case.get("required_documents") or []
    everything_arrived = bool(required) and all(row["received"] for row in required)
    return everything_arrived and not what_the_screen_shows(case)


# ── what HCS-11 decided ──────────────────────────────────────────────────────────────


def what_hcs11_found(case: dict, rules: list[dict]) -> set[str]:
    """
    Every problem HCS-11 recorded against this claim, in the same `source:key` labels.

    Three sources, and the first is the one that admits no argument: `employee_issues` is
    HCS-11's own curated list of what the employee must be told. If something is in there
    and not on the screen, the screen is lying.
    """
    found = {f"issue:{issue['kind']}" for issue in case.get("employee_issues") or []}
    found |= {f"rule:{rule['code']}" for rule in rules if rule["result"] in NOT_SETTLED}
    found |= {
        f"check:{check['code']}"
        for check in case.get("match_checks") or []
        if is_a_finding(check, case)
    }
    return found


NOT_SETTLED = ("fail", "review", "missing")


def is_a_finding(check: dict, case: dict) -> bool:
    """
    Is this check something about a document, rather than about a document's absence?

    `missing` means both on HCS-11's side. Once every document has arrived it means the
    page does not state something it should — a real finding, and one an earlier draft of
    this script did not count on either side, so neither screen was ever marked for
    hiding it. While a document is still outstanding it means there was nothing yet to
    compare against, which the checklist reports in its own right.

    The distinction is applied to HCS-11's side of the comparison, so both screens are
    held to it equally: the old panel gets exactly the allowance the new one gets.
    """
    if check["result"] not in NOT_SETTLED:
        return False
    if check["result"] == "missing" and case.get("missing_documents"):
        return False
    return True


def hcs11_is_happy(case: dict) -> bool:
    """HCS-11 approved it outright: no person needed, nothing to fix."""
    return case.get("route") == "approve" and case.get("recommendation") == "approve"


# ── one scenario ─────────────────────────────────────────────────────────────────────


@dataclass
class Verdict:
    folder: str
    case_id: str
    employee_id: str
    dependent_name: str
    scenario: str
    hcs11_route: str | None = None
    hcs11_recommendation: str | None = None
    hcs11_case_status: str | None = None
    hidden: list[str] = field(default_factory=list)
    invented: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)
    green_banner: bool = False
    false_green: bool = False
    error: str | None = None

    @property
    def agrees(self) -> bool:
        return not self.hidden and not self.invented and not self.false_green


def rules_for(database: Path, case_id: str) -> list[dict]:
    """The rule results HCS-11 wrote, which no part of hcs-01 currently reads."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT code, result, detail FROM rule_results WHERE case_id = ?", (case_id,)
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def run_one(client: httpx.Client, database: Path, folder: Path, case_id: str,
            files: list[tuple[str, str]], meta: dict, screen: str = "server",
            upload: bool = True) -> Verdict:
    verdict = Verdict(
        folder=folder.name,
        case_id=case_id,
        employee_id=meta["employee_id"],
        dependent_name=meta["dependent_name"],
        scenario=meta["scenario"],
    )

    try:
        if upload:
            payload = []
            for file_name, _kind in files:
                path = folder / file_name
                if not path.exists():
                    verdict.error = f"missing file {file_name}"
                    return verdict
                payload.append(
                    ("files", (file_name, path.read_bytes(), content_type_of(path)))
                )
            response = client.post(f"/api/hcs11/cases/{case_id}/documents", files=payload)
        else:
            # The claim as it already stands. Re-uploading would put the same files
            # through the reader again for no new information, and the reader is the
            # expensive part. Measuring both screens against one uploaded state is also
            # the fairer comparison: same claims, same findings, only the screen differs.
            response = client.get(f"/api/hcs11/cases/{case_id}")
        response.raise_for_status()
        case = response.json()
    except httpx.HTTPError as problem:
        verdict.error = f"{type(problem).__name__}: {problem}"
        return verdict

    rules = rules_for(database, case_id)
    found = what_hcs11_found(case, rules)
    if screen == "tables":
        shown = what_the_screen_shows(case)
        green = the_banner_is_green(case)
    else:
        shown = what_the_fixed_screen_shows(case, rules)
        green = the_fixed_banner_is_green(case)

    verdict.hcs11_route = case.get("route")
    verdict.hcs11_recommendation = case.get("recommendation")
    verdict.hcs11_case_status = case.get("case_status")
    verdict.shown = sorted(shown)
    verdict.hidden = sorted(found - shown)
    verdict.invented = sorted(shown - found)
    verdict.green_banner = green
    verdict.false_green = green and not hcs11_is_happy(case)
    return verdict


def content_type_of(path: Path) -> str:
    return {".pdf": "application/pdf", ".png": "image/png",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(), "application/pdf")


# ── the corpus ───────────────────────────────────────────────────────────────────────


def scenarios(documents_dir: Path, cases_by_dependent: dict[str, str]) -> list[tuple]:
    """
    Every demo scenario, as sent by the employee.

    Only the `as sent` rows — the `corrected` ones are the fixed versions, and uploading
    those would test the happy path twice and the reported bug not at all.
    """
    manifest = documents_dir / "document_manifest.csv"
    grouped: dict[str, list] = defaultdict(list)
    details: dict[str, dict] = {}

    with manifest.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["as_sent_or_corrected"].strip().lower() != "as sent":
                continue
            grouped[row["folder"]].append((row["file_name"], row["document_kind"]))
            details.setdefault(row["folder"], {
                "employee_id": row["employee_id"],
                "dependent_id": row["dependent_id"],
                "dependent_name": row["dependent_name"],
                "scenario": row["scenario"],
            })

    ready = []
    for folder, files in sorted(grouped.items()):
        meta = details[folder]
        case_id = cases_by_dependent.get(meta["dependent_id"])
        if not case_id:
            print(f"  skipping {folder}: no open claim for {meta['dependent_id']}")
            continue
        ready.append((documents_dir / "demo" / folder, case_id, files, meta))
    return ready


# ── reporting ────────────────────────────────────────────────────────────────────────


def report(verdicts: list[Verdict]) -> None:
    ran = [v for v in verdicts if not v.error]
    hidden_total = sum(len(v.hidden) for v in ran)
    false_greens = [v for v in ran if v.false_green]

    print()
    print("═" * 100)
    print(f"  {len(ran)} claims uploaded to a scratch HCS-11 and compared against its own record")
    print("═" * 100)

    for verdict in verdicts:
        if verdict.error:
            print(f"\n  {verdict.folder}\n      could not run: {verdict.error}")
            continue
        mark = "OK  " if verdict.agrees else "BAD "
        print(f"\n  {mark}{verdict.folder}")
        print(f"      HCS-11 decided: {verdict.hcs11_case_status}, route "
              f"{verdict.hcs11_route}, recommendation {verdict.hcs11_recommendation}")
        if verdict.hidden:
            print(f"      HIDDEN from the employee ({len(verdict.hidden)}):")
            for item in verdict.hidden:
                print(f"          {item}")
        if verdict.invented:
            print(f"      shown but never found ({len(verdict.invented)}): {verdict.invented}")
        if verdict.false_green:
            print("      *** the screen shows \"Everything we need is here\" ***")
        if verdict.agrees:
            print(f"      screen agrees ({len(verdict.shown)} shown)")

    print()
    print("═" * 100)
    print(f"  {hidden_total} problems HCS-11 found that the employee is never shown")
    print(f"  {len(false_greens)} claims told the employee \"Everything we need is here\" "
          f"when HCS-11 had not approved them")
    print(f"  {sum(len(v.invented) for v in ran)} problems shown that HCS-11 never found")
    print("═" * 100)

    if false_greens:
        print("\n  Claims wrongly showing the green banner:")
        for verdict in false_greens:
            print(f"      {verdict.folder:52} HCS-11 said {verdict.hcs11_recommendation}")

    by_kind: dict[str, int] = defaultdict(int)
    for verdict in ran:
        for item in verdict.hidden:
            by_kind[item] += 1
    if by_kind:
        print("\n  What is being hidden, most often first:")
        for item, count in sorted(by_kind.items(), key=lambda pair: -pair[1]):
            print(f"      {count:>3}x  {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hcs11", default="http://localhost:8003",
                        help="a SCRATCH HCS-11, never the live one")
    parser.add_argument("--db", required=True, help="that scratch instance's sqlite file")
    parser.add_argument("--documents", required=True, help="hcs-11's documents/ folder")
    parser.add_argument("--out", help="directory for the saved figures")
    parser.add_argument("--only", nargs="*", help="run only these scenario folders")
    parser.add_argument("--no-upload", action="store_true",
                        help="compare the claims as they already stand, without sending "
                             "the files again. Use this to measure the second screen "
                             "against the state the first was measured on.")
    parser.add_argument("--screen", choices=("server", "tables"), default="server",
                        help="'server' is the repaired panel, which shows what the server "
                             "decided. 'tables' replays the panel's old hand-written "
                             "lookup tables, and is how the before figure was measured.")
    arguments = parser.parse_args()

    database = Path(arguments.db)
    if not database.exists():
        print(f"no database at {database}", file=sys.stderr)
        return 1
    if "storage/hcs11.sqlite" in str(database.resolve()).replace("\\", "/") and "/tmp/" not in str(database):
        print("that looks like the live database. Point this at a scratch copy.", file=sys.stderr)
        return 1

    client = httpx.Client(base_url=arguments.hcs11, timeout=300.0)
    cases = client.get("/api/hcs11/cases").json()
    by_dependent = {c["dependent_id"]: c["case_id"] for c in cases if c.get("dependent_id")}

    work = scenarios(Path(arguments.documents), by_dependent)
    if arguments.only:
        wanted = set(arguments.only)
        work = [item for item in work if item[0].name in wanted]

    print(f"  {len(work)} scenarios to run against {arguments.hcs11}")
    verdicts = []
    for index, (folder, case_id, files, meta) in enumerate(work, start=1):
        doing = "uploading" if not arguments.no_upload else "reading"
        print(f"  [{index}/{len(work)}] {doing} {folder.name} -> {case_id}")
        verdicts.append(
            run_one(client, database, folder, case_id, files, meta, arguments.screen,
                    upload=not arguments.no_upload)
        )

    report(verdicts)

    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"school-verdicts-{date.today().isoformat()}.json"
        path.write_text(json.dumps({
            "run_on": date.today().isoformat(),
            "claims_run": len([v for v in verdicts if not v.error]),
            "problems_hidden_from_the_employee": sum(len(v.hidden) for v in verdicts),
            "claims_wrongly_shown_as_complete": len([v for v in verdicts if v.false_green]),
            "problems_invented": sum(len(v.invented) for v in verdicts),
            "claims": [vars(v) for v in verdicts],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  written to {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
