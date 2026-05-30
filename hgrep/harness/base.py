from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, Union, cast, runtime_checkable

from hgrep.record import SessionRecord

MAX_CONTENT_CHARS = 200_000

# A JSON value as produced by json.loads, typed recursively so that narrowing
# with isinstance() yields concrete types instead of Any. Forward references are
# quoted so the alias is safe to evaluate at runtime.
JsonValue = Union[
    str, int, float, bool, None, "list[JsonValue]", "dict[str, JsonValue]"
]
JsonObject = dict[str, "JsonValue"]


@runtime_checkable
class Adapter(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def iter_sessions(self) -> Iterator[tuple[Path, float, int]]: ...

    def parse(self, path: Path) -> SessionRecord: ...

    def resume_command(self, record: SessionRecord) -> str: ...


def unslug_dir(name: str) -> str:
    """Recover an absolute path from a dash-slug directory name.

    Both harnesses encode the cwd as the directory name with '/' replaced by
    '-'. This is a best-effort fallback only; the real cwd is read from the
    file contents when present.
    """
    return "/" + name.strip("-").replace("-", "/")


def iter_jsonl(path: Path) -> Iterator[JsonObject]:
    """Yield JSON objects from a .jsonl file, streaming line by line.

    Blank lines, malformed lines, and top-level JSON values that are not objects
    are skipped. Streaming keeps memory bounded for very large transcripts.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield cast(JsonObject, obj)


def str_field(obj: JsonObject, key: str) -> str | None:
    """Return obj[key] if it is a string, else None."""
    value = obj.get(key)
    return value if isinstance(value, str) else None


def text_parts(content: JsonValue) -> list[str]:
    """Extract conversation text from a message `content` value.

    `content` is either a plain string (a whole user turn) or a list of typed
    parts; only parts of type "text" contribute. Everything else (thinking,
    tool calls, tool results) is intentionally excluded.
    """
    if isinstance(content, str):
        return [content]
    out: list[str] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    out.append(text)
    return out
