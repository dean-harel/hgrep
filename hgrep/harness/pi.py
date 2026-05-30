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


class PiAdapter:
    name: str = "pi"

    def __init__(self, root: Path | None = None) -> None:
        self.root: Path = (
            Path(root) if root else Path.home() / ".pi" / "agent" / "sessions"
        )

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
        sid: str | None = None
        cwd: str | None = None
        name: str | None = None
        first_user: str | None = None
        texts: list[str] = []
        ts_min: str | None = None
        ts_max: str | None = None
        msg_count = 0

        for obj in iter_jsonl(path):
            ts = str_field(obj, "timestamp")
            if ts is not None:
                if ts_min is None or ts < ts_min:
                    ts_min = ts
                if ts_max is None or ts > ts_max:
                    ts_max = ts
            kind = obj.get("type")
            if kind == "session":
                sid = str_field(obj, "id")
                cwd = str_field(obj, "cwd")
            elif kind == "session_info":
                name = str_field(obj, "name") or name
            elif kind == "message":
                message = obj.get("message")
                if not isinstance(message, dict):
                    continue
                role = message.get("role")
                if role not in ("user", "assistant"):
                    continue
                msg_count += 1
                parts = text_parts(message.get("content"))
                texts.extend(parts)
                if role == "user" and first_user is None and parts:
                    first_user = parts[0]

        if sid is None:
            stem = path.stem
            sid = stem.split("_", 1)[1] if "_" in stem else stem
        if cwd is None:
            cwd = unslug_dir(path.parent.name)
        first_user = (first_user or "").strip()
        title = (name or first_user or "(untitled)").strip()[:200] or "(untitled)"
        content_text = "\n".join(texts)[:MAX_CONTENT_CHARS]
        st = path.stat()
        return SessionRecord(
            harness=self.name,
            session_id=sid,
            cwd=cwd,
            project=os.path.basename(cwd.rstrip("/")) or cwd,
            git_branch=None,
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
        return f"(cd {shlex.quote(record.cwd)} && pi --session {record.session_id})"
