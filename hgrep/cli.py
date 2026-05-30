from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import TypedDict

from hgrep.harness.base import Adapter
from hgrep.index import connect, default_db_path, rebuild, refresh
from hgrep.registry import default_adapters
from hgrep.search import format_pretty, search, to_public

_SUBCOMMANDS = {"search", "reindex", "stats"}

_EPILOG = """\
examples:
  hgrep "renewals retry"                  search every harness (table in a
                                          terminal, JSON when piped)
  hgrep "deploy" --harness pi             only Pi sessions
  hgrep "auth" --since 7d --project api   filter by recency and project
  hgrep "x" --json | jq .                 force JSON for scripting
  hgrep reindex                           refresh the index now
  hgrep stats                             show what is indexed
"""


class StatsResult(TypedDict):
    total: int
    by_harness: dict[str, int]
    db: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hgrep",
        description="Search and resume past AI coding sessions across harnesses "
        "(Claude Code, Pi) by keyword, time, project, and branch.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser(
        "search",
        help="search sessions (the default; the word `search` may be omitted)",
        description="Full-text search over session titles and conversation text. "
        "Prints a table to a terminal and JSON when piped; each result includes a "
        "ready-to-run resume command.",
    )
    s.add_argument("query", help="words to match (combined with AND)")
    s.add_argument(
        "--since",
        help="only sessions active since this time (ISO date, or relative like 7d / 2w)",
    )
    s.add_argument(
        "--until",
        help="only sessions active up to this time (ISO date, or relative like 7d / 2w)",
    )
    s.add_argument(
        "--project", help="only sessions whose project/cwd contains this substring"
    )
    s.add_argument(
        "--branch",
        help="only sessions on this git branch (excludes harnesses without branches, e.g. Pi)",
    )
    s.add_argument("--harness", help="restrict to one harness (claude-code | pi)")
    s.add_argument(
        "--limit", type=int, default=20, help="maximum results (default: 20)"
    )
    fmt = s.add_mutually_exclusive_group()
    fmt.add_argument(
        "--json", action="store_true", help="force JSON output (default when piped)"
    )
    fmt.add_argument(
        "--pretty",
        action="store_true",
        help="force the human-readable table (default in a terminal)",
    )
    s.add_argument(
        "--no-refresh",
        action="store_true",
        help="skip the incremental index refresh before searching",
    )

    r = sub.add_parser(
        "reindex",
        help="refresh the index",
        description="Incrementally update the index, or rebuild it from scratch.",
    )
    r.add_argument(
        "--rebuild", action="store_true", help="wipe and rebuild the index from scratch"
    )

    sub.add_parser(
        "stats",
        help="show index stats",
        description="Print how many sessions are indexed per harness and the index path.",
    )
    return parser


def _gather_stats(conn: sqlite3.Connection) -> StatsResult:
    rows = conn.execute(
        "SELECT harness, COUNT(*) AS n FROM sessions GROUP BY harness"
    ).fetchall()
    by_harness = {str(row["harness"]): int(row["n"]) for row in rows}
    total = int(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    return {"total": total, "by_harness": by_harness, "db": str(default_db_path())}


def main(argv: list[str] | None = None, adapters: list[Adapter] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-"):
        argv = ["search"] + argv

    args = _build_parser().parse_args(argv)
    adapters = adapters if adapters is not None else default_adapters()

    try:
        conn = connect()
        if args.cmd == "search":
            if not args.no_refresh:
                refresh(conn, adapters)
            results = search(
                conn,
                args.query,
                since=args.since,
                until=args.until,
                project=args.project,
                branch=args.branch,
                harness=args.harness,
                limit=args.limit,
            )
            if args.json:
                use_pretty = False
            elif args.pretty:
                use_pretty = True
            else:
                use_pretty = sys.stdout.isatty()
            if use_pretty:
                print(format_pretty(results, color=sys.stdout.isatty()))
            else:
                print(json.dumps(to_public(results), indent=2))
        elif args.cmd == "reindex":
            if args.rebuild:
                rebuild(conn)
            print(json.dumps(refresh(conn, adapters)))
        elif args.cmd == "stats":
            print(json.dumps(_gather_stats(conn)))
    except Exception as e:
        print(f"hgrep: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
