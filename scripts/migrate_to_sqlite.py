#!/usr/bin/env python3
"""Import legacy paper JSON/JSONL state into the v2 SQLite store.

The default action is a read-only dry run.  Use ``--apply`` to create/update
``references/paper_valt.db``; use ``--rollback`` to restore the ``.bak`` files
created by an apply.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running ``python scripts/migrate_to_sqlite.py`` puts ``scripts/`` (rather
# than the repository root) on sys.path.  Make the local package importable
# without requiring an installation or a caller-provided PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.stores.db import migrate_to_sqlite, rollback_migration  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate paper_valt legacy JSON/JSONL state to SQLite"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="PAPER_VALT_ROOT (defaults to the environment or repository root)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path (defaults to <root>/references/paper_valt.db)",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--apply",
        action="store_true",
        help="write the SQLite database after making .bak source copies",
    )
    action.add_argument(
        "--rollback",
        action="store_true",
        help="restore source and, when available, the SQLite .bak copy",
    )
    parser.add_argument(
        "--remove-db",
        action="store_true",
        help="with --rollback, remove a newly-created database if no DB backup exists",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.rollback:
            report = rollback_migration(
                args.root,
                db_path=args.db,
                remove_database=args.remove_db,
            )
        else:
            report = migrate_to_sqlite(
                args.root,
                db_path=args.db,
                apply=args.apply,
            )
    except Exception as exc:  # pragma: no cover - CLI guard, details go to stderr
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") == "applied_with_errors":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
