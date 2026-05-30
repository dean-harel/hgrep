from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from hgrep.harness.base import Adapter
from hgrep.record import SessionRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  harness TEXT NOT NULL,
  session_id TEXT NOT NULL,
  cwd TEXT,
  project TEXT,
  git_branch TEXT,
  title TEXT,
  first_user_msg TEXT,
  started_at TEXT,
  last_activity_at TEXT,
  msg_count INTEGER,
  resume_command TEXT,
  file_path TEXT NOT NULL UNIQUE,
  file_mtime REAL,
  file_size INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sessions_harness ON sessions(harness);
CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts
  USING fts5(title, first_user_msg, content);
"""


class RefreshStats(TypedDict):
    parsed: int
    skipped: int
    deleted: int
    failed: int


def default_db_path() -> Path:
    env = os.environ.get("HGREP_DB")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "hgrep" / "index.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


def rebuild(conn: sqlite3.Connection) -> None:
    conn.executescript(
        "DROP TABLE IF EXISTS sessions; DROP TABLE IF EXISTS sessions_fts;"
    )
    conn.executescript(SCHEMA)
    conn.commit()


def _upsert(conn: sqlite3.Connection, rec: SessionRecord, resume_command: str) -> None:
    row = conn.execute(
        "SELECT id FROM sessions WHERE file_path=?", (rec.file_path,)
    ).fetchone()
    cols = (
        rec.harness, rec.session_id, rec.cwd, rec.project, rec.git_branch,
        rec.title, rec.first_user_msg, rec.started_at, rec.last_activity_at,
        rec.msg_count, resume_command, rec.file_path, rec.file_mtime, rec.file_size,
    )
    if row is not None:
        rid = row["id"]
        conn.execute(
            """UPDATE sessions SET harness=?,session_id=?,cwd=?,project=?,git_branch=?,
               title=?,first_user_msg=?,started_at=?,last_activity_at=?,msg_count=?,
               resume_command=?,file_path=?,file_mtime=?,file_size=? WHERE id=?""",
            cols + (rid,),
        )
        conn.execute("DELETE FROM sessions_fts WHERE rowid=?", (rid,))
    else:
        cur = conn.execute(
            """INSERT INTO sessions(harness,session_id,cwd,project,git_branch,title,
               first_user_msg,started_at,last_activity_at,msg_count,resume_command,
               file_path,file_mtime,file_size)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            cols,
        )
        rid = cur.lastrowid
    conn.execute(
        "INSERT INTO sessions_fts(rowid,title,first_user_msg,content) VALUES(?,?,?,?)",
        (rid, rec.title, rec.first_user_msg, rec.content_text),
    )


def refresh(conn: sqlite3.Connection, adapters: Iterable[Adapter]) -> RefreshStats:
    stats: RefreshStats = {"parsed": 0, "skipped": 0, "deleted": 0, "failed": 0}
    for adapter in adapters:
        if not adapter.is_available():
            continue
        seen: set[str] = set()
        for path, mtime, size in adapter.iter_sessions():
            fp = str(path)
            seen.add(fp)
            row = conn.execute(
                "SELECT file_mtime,file_size FROM sessions WHERE file_path=?", (fp,)
            ).fetchone()
            if (
                row is not None
                and row["file_mtime"] is not None
                and abs(row["file_mtime"] - mtime) < 1e-6
                and row["file_size"] == size
            ):
                stats["skipped"] += 1
                continue
            try:
                rec = adapter.parse(path)
                cmd = adapter.resume_command(rec)
            except Exception:
                stats["failed"] += 1
                continue
            _upsert(conn, rec, cmd)
            stats["parsed"] += 1
        stored = conn.execute(
            "SELECT id,file_path FROM sessions WHERE harness=?", (adapter.name,)
        ).fetchall()
        for r in stored:
            if r["file_path"] not in seen:
                conn.execute("DELETE FROM sessions_fts WHERE rowid=?", (r["id"],))
                conn.execute("DELETE FROM sessions WHERE id=?", (r["id"],))
                stats["deleted"] += 1
    conn.commit()
    return stats
