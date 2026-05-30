from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionRecord:
    harness: str
    session_id: str
    cwd: str
    project: str
    git_branch: str | None
    title: str
    first_user_msg: str
    content_text: str
    started_at: str
    last_activity_at: str
    msg_count: int
    file_path: str
    file_mtime: float
    file_size: int
