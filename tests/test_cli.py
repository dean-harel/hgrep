import json
import sys
from pathlib import Path

import pytest

from hgrep.cli import main
from hgrep.harness.claude_code import ClaudeCodeAdapter
from hgrep.harness.pi import PiAdapter

CLAUDE_ROOT = Path(__file__).parent / "fixtures" / "claude"
PI_ROOT = Path(__file__).parent / "fixtures" / "pi"


def _adapters():
    return [ClaudeCodeAdapter(root=CLAUDE_ROOT), PiAdapter(root=PI_ROOT)]


def test_search_default_subcommand_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    rc = main(["retry"], adapters=_adapters())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["title"] == "Renewals"
    assert out[0]["resume_command"].startswith("(cd /tmp/proj && claude --resume ")


def test_search_explicit_with_harness_filter(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    rc = main(["search", "deploy", "--harness", "pi"], adapters=_adapters())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out and all(r["harness"] == "pi" for r in out)


def test_pretty_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    main(["retry", "--pretty"], adapters=_adapters())
    assert "Renewals" in capsys.readouterr().out


def test_reindex_then_stats(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    main(["reindex"], adapters=_adapters())
    capsys.readouterr()
    main(["stats"], adapters=_adapters())
    stats = json.loads(capsys.readouterr().out)
    assert stats["total"] == 4
    assert stats["by_harness"]["pi"] == 2
    assert stats["by_harness"]["claude-code"] == 2


def test_json_flag_forces_json(tmp_path, monkeypatch, capsys):
    # The /recall skill invokes `hgrep search ... --json`; it must parse as JSON.
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    rc = main(["deploy", "--json"], adapters=_adapters())
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert any(r["harness"] == "pi" for r in out)


def test_terminal_defaults_to_pretty(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main(["retry"], adapters=_adapters())
    out = capsys.readouterr().out
    assert "Renewals" in out
    assert "claude-code" in out  # pretty table column, not present in JSON keys
    assert not out.lstrip().startswith("[")  # not a JSON array


def test_json_and_pretty_are_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))
    with pytest.raises(SystemExit):
        main(["retry", "--json", "--pretty"], adapters=_adapters())


def test_runtime_error_returns_exit_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HGREP_DB", str(tmp_path / "i.db"))

    class Boom:
        name = "boom"

        def is_available(self):
            return True

        def iter_sessions(self):
            raise RuntimeError("disk on fire")

        def parse(self, path):
            raise AssertionError("should not be called")

        def resume_command(self, record):
            return ""

    rc = main(["anything"], adapters=[Boom()])
    assert rc == 1
    assert "disk on fire" in capsys.readouterr().err
