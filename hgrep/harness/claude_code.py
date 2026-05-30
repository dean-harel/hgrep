from __future__ import annotations

import os
import shlex
from collections.abc import Iterator
from pathlib import Path

from hgrep.harness.base import (
    MAX_CONTENT_CHARS,
    iter_jsonl,
    str_field,
    text_parts,
    unslug_dir,
)
from hgrep.record import SessionRecord


class ClaudeCodeAdapter:
    name: str = "claude-code"

    def __init__(self, root: Path | None = None) -> None:
        self.root: Path = Path(root) if root else Path.home() / ".claude" / "projects"

    def is_available(self) -> bool:
        return self.root.is_dir()

    def iter_sessions(self) -> Iterator[tuple[Path, float, int]]:
        if not self.root.is_dir():
            return
        for path in self.root.glob("*/*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            yield path, st.st_mtime, st.st_size

    def parse(self, path: Path) -> SessionRecord:
        cwd: str | None = None
        branch: str | None = None
        custom: str | None = None
        ai: str | None = None
        first_user: str | None = None
        texts: list[str] = []
        ts_min: str | None = None
        ts_max: str | None = None
        msg_count = 0

        for obj in iter_jsonl(path):
            if cwd is None:
                cwd = str_field(obj, "cwd")
            if branch is None:
                branch = str_field(obj, "gitBranch")
            custom = str_field(obj, "customTitle") or custom
            ai = str_field(obj, "aiTitle") or ai
            ts = str_field(obj, "timestamp")
            if ts is not None:
                if ts_min is None or ts < ts_min:
                    ts_min = ts
                if ts_max is None or ts > ts_max:
                    ts_max = ts
            kind = obj.get("type")
            if kind not in ("user", "assistant"):
                continue
            msg_count += 1
            message = obj.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            parts = text_parts(content)
            texts.extend(parts)
            if kind == "user" and first_user is None and parts:
                first_user = parts[0]

        session_id = path.stem
        if cwd is None:
            cwd = unslug_dir(path.parent.name)
        first_user = (first_user or "").strip()
        title = (custom or ai or first_user or "(untitled)").strip()[:200] or "(untitled)"
        content_text = "\n".join(texts)[:MAX_CONTENT_CHARS]
        st = path.stat()
        return SessionRecord(
            harness=self.name,
            session_id=session_id,
            cwd=cwd,
            project=os.path.basename(cwd.rstrip("/")) or cwd,
            git_branch=branch,
            title=title,
            first_user_msg=first_user[:500],
            content_text=content_text,
            started_at=ts_min or "",
            last_activity_at=ts_max or ts_min or "",
            msg_count=msg_count,
            file_path=str(path),
            file_mtime=st.st_mtime,
            file_size=st.st_size,
        )

    def resume_command(self, record: SessionRecord) -> str:
        return f"(cd {shlex.quote(record.cwd)} && claude --resume {record.session_id})"
