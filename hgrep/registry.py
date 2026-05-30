from __future__ import annotations

from hgrep.harness.base import Adapter
from hgrep.harness.claude_code import ClaudeCodeAdapter
from hgrep.harness.pi import PiAdapter


def default_adapters() -> list[Adapter]:
    return [ClaudeCodeAdapter(), PiAdapter()]
