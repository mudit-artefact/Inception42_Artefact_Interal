"""
Clears the data a local run leaves behind, so the next start is a clean one.

Two files accumulate while you use the assistant, and both are disposable:

  data/conversation_checkpoints.sqlite   every conversation, its memory, and any
                                         clarification it is still waiting on
  data/omni_hr.db                        the demonstration employees, written from
                                         seed_employees.py and never edited by hand

Nothing else is touched. The policies, the PDFs and the font are source material, not
run-time state. The policy search index needs no clearing at all — it is held in memory
and rebuilt from scratch every time the server starts.

    python scripts/reset_local_data.py                    # chats and employees
    python scripts/reset_local_data.py --conversations    # chats only

Then start the server:

    .venv/bin/python -m uvicorn app.main:app --reload --port 8000
"""

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "data"

CONVERSATIONS = "conversation_checkpoints.sqlite"
EMPLOYEES = "omni_hr.db"


def remove(file_name: str) -> list[str]:
    """
    Delete a database and the journal files that belong with it.

    SQLite keeps recent writes in a `-wal` file beside the database and an index into it
    in `-shm`. Deleting only the `.sqlite` leaves those two behind holding the tail of
    the data, and the next run reads them back — so the reset looks like it silently
    failed.
    """
    removed = []
    for path in sorted(DATA.glob(f"{file_name}*")):
        if path.suffix == ".bak":
            continue  # a backup somebody took on purpose
        try:
            path.unlink()
        except OSError as error:
            print(f"  could not remove {path.name}: {error}")
            print("  is the server still running? stop it with Ctrl+C and try again.")
            raise SystemExit(1)
        removed.append(path.name)
    return removed


def describe(removed: list[str], nothing_there: str) -> None:
    if removed:
        for name in removed:
            print(f"  removed {name}")
    else:
        print(f"  {nothing_there}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear the local run's data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run with no arguments to clear everything a local run leaves behind.",
    )
    parser.add_argument(
        "--conversations",
        action="store_true",
        help="clear the saved conversations only, and leave the employees alone",
    )
    arguments = parser.parse_args()

    if not DATA.exists():
        print(f"No data directory at {DATA} — nothing to clear.")
        return 0

    print("Clearing saved conversations…")
    describe(remove(CONVERSATIONS), "none saved")

    if not arguments.conversations:
        print("\nResetting the demonstration employees…")
        describe(remove(EMPLOYEES), "none stored")

        # Rebuilt now rather than at the next start, so this script can say whether it
        # worked instead of leaving you to find out when you ask a question.
        sys.path.insert(0, str(BACKEND))
        from app.database.engine import init_and_seed_db

        print(f"  seeded {init_and_seed_db()} employees from seed_employees.py")

    print("\nDone. The policy index needs no clearing — it is rebuilt on every start.")
    print("\nStart the server with:")
    print("  .venv/bin/python -m uvicorn app.main:app --reload --port 8000")

    print("\n" + "-" * 70)
    print("The browser keeps its own copy, which nothing here can reach.")
    print("-" * 70)
    print("The page stores its chat list under one key per employee, so 'New")
    print("conversation' does not clear it — that only adds another chat above the")
    print("old ones. Paste this into the browser console (F12) on the page:")
    print()
    print("  Object.keys(localStorage)")
    print("    .filter(k => k.startsWith('hcs01.'))")
    print("    .forEach(k => localStorage.removeItem(k));")
    print("  location.reload();")
    return 0


if __name__ == "__main__":
    sys.exit(main())
