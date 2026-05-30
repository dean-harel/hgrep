from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import TypedDict, cast


class PublicResult(TypedDict):
    harness: str
    session_id: str
    title: str
    project: str
    cwd: str
    git_branch: str | None
    last_activity_at: str
    msg_count: int
    snippet: str
    resume_command: str


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def build_match(query: str) -> str:
    terms = [t for t in query.split() if t]
    return " ".join('"' + t.replace('"', '""') + '"' for t in terms)


def _is_bare_date(value: str) -> bool:
    return (
        len(value) == 10
        and value[4] == "-"
        and value[7] == "-"
        and value.replace("-", "").isdigit()
    )


def parse_when(value: str, *, end_of_day: bool = False) -> str:
    """Normalize a --since/--until value to an ISO cutoff for lexical compare.

    Relative forms `<N>d` / `<N>w` become `now - N` (UTC). A bare `YYYY-MM-DD`
    used as an inclusive upper bound is widened to end-of-day. Anything else
    passes through unchanged.
    """
    v = value.strip().lower()
    units = {"d": 1, "w": 7}
    if len(v) >= 2 and v[-1] in units and v[:-1].isdigit():
        days = int(v[:-1]) * units[v[-1]]
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if end_of_day and _is_bare_date(value.strip()):
        return value.strip() + "T23:59:59.999Z"
    return value


def parse_since(value: str) -> str:
    return parse_when(value)


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    since: str | None = None,
    until: str | None = None,
    project: str | None = None,
    branch: str | None = None,
    harness: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    match = build_match(query)
    if not match:
        return []
    where = ["sessions_fts MATCH ?"]
    params: list[object] = [match]
    if since:
        where.append("s.last_activity_at >= ?")
        params.append(parse_when(since))
    if until:
        where.append("s.last_activity_at <= ?")
        params.append(parse_when(until, end_of_day=True))
    if project:
        where.append("s.project LIKE ?")
        params.append(f"%{project}%")
    if branch:
        where.append("s.git_branch = ?")
        params.append(branch)
    if harness:
        where.append("s.harness = ?")
        params.append(harness)
    sql = f"""
        SELECT s.*, bm25(sessions_fts) AS rank,
               snippet(sessions_fts, 2, '[', ']', '...', 12) AS snippet
        FROM sessions_fts JOIN sessions s ON s.id = sessions_fts.rowid
        WHERE {" AND ".join(where)}
        ORDER BY rank ASC, s.last_activity_at DESC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [cast("dict[str, object]", dict(row)) for row in rows]


def to_public(results: list[dict[str, object]]) -> list[PublicResult]:
    out: list[PublicResult] = []
    for r in results:
        out.append(
            PublicResult(
                harness=_as_str(r.get("harness")),
                session_id=_as_str(r.get("session_id")),
                title=_as_str(r.get("title")),
                project=_as_str(r.get("project")),
                cwd=_as_str(r.get("cwd")),
                git_branch=_as_opt_str(r.get("git_branch")),
                last_activity_at=_as_str(r.get("last_activity_at")),
                msg_count=_as_int(r.get("msg_count")),
                snippet=_as_str(r.get("snippet")),
                resume_command=_as_str(r.get("resume_command")),
            )
        )
    return out


def format_pretty(results: list[dict[str, object]], *, color: bool = False) -> str:
    """Render results as numbered, blank-line-separated blocks.

    Each block is a bold title, a dim metadata line, the cleaned match snippet,
    and the resume command. ANSI styling is applied only when `color` is True
    (set by the CLI when stdout is a terminal).
    """
    if not results:
        return "(no matches)"
    bold = "\x1b[1m" if color else ""
    dim = "\x1b[2m" if color else ""
    cyan = "\x1b[36m" if color else ""
    reset = "\x1b[0m" if color else ""

    blocks: list[str] = []
    for i, r in enumerate(results, 1):
        title = _as_str(r.get("title")) or "(untitled)"
        harness = _as_str(r.get("harness"))
        when = _as_str(r.get("last_activity_at"))[:10]
        project = _as_str(r.get("project"))
        branch = _as_opt_str(r.get("git_branch"))
        loc = f"{project}/{branch}" if branch else project
        snippet = " ".join(_as_str(r.get("snippet")).split())
        cmd = _as_str(r.get("resume_command"))

        lines = [
            f"{bold}{i}. {title}{reset}",
            f"   {dim}{harness:<11} {when}  {loc}{reset}",
        ]
        if snippet:
            lines.append(f"   {dim}{snippet}{reset}")
        lines.append(f"   {cyan}{cmd}{reset}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
