from pathlib import Path

from hgrep.harness.claude_code import ClaudeCodeAdapter
from hgrep.harness.pi import PiAdapter
from hgrep.index import connect, refresh, rebuild

CLAUDE_ROOT = Path(__file__).parent / "fixtures" / "claude"
PI_ROOT = Path(__file__).parent / "fixtures" / "pi"


def _adapters():
    return [ClaudeCodeAdapter(root=CLAUDE_ROOT), PiAdapter(root=PI_ROOT)]


def test_refresh_indexes_all_sessions(tmp_path):
    conn = connect(tmp_path / "i.db")
    stats = refresh(conn, _adapters())
    assert stats["parsed"] == 4  # 2 claude + 2 pi fixtures
    n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert n == 4
    nfts = conn.execute("SELECT COUNT(*) FROM sessions_fts").fetchone()[0]
    assert nfts == 4


def test_refresh_is_incremental(tmp_path):
    conn = connect(tmp_path / "i.db")
    refresh(conn, _adapters())
    stats = refresh(conn, _adapters())  # nothing changed
    assert stats["parsed"] == 0
    assert stats["skipped"] == 4


def test_refresh_reparses_changed_file(tmp_path):
    src = CLAUDE_ROOT / "-tmp-bar" / "22222222-2222-2222-2222-222222222222.jsonl"
    work = tmp_path / "claude" / "-tmp-bar"
    work.mkdir(parents=True)
    target = work / src.name
    target.write_text(src.read_text())
    adapters = [ClaudeCodeAdapter(root=tmp_path / "claude")]
    conn = connect(tmp_path / "i.db")
    refresh(conn, adapters)
    # bump mtime and change size
    target.write_text(target.read_text() + "\n")
    import os
    os.utime(target, (target.stat().st_atime, target.stat().st_mtime + 5))
    stats = refresh(conn, adapters)
    assert stats["parsed"] == 1


def test_refresh_deletes_vanished_file(tmp_path):
    src = CLAUDE_ROOT / "-tmp-bar" / "22222222-2222-2222-2222-222222222222.jsonl"
    work = tmp_path / "claude" / "-tmp-bar"
    work.mkdir(parents=True)
    target = work / src.name
    target.write_text(src.read_text())
    adapters = [ClaudeCodeAdapter(root=tmp_path / "claude")]
    conn = connect(tmp_path / "i.db")
    refresh(conn, adapters)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    target.unlink()
    stats = refresh(conn, adapters)
    assert stats["deleted"] == 1
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_resume_command_is_stored(tmp_path):
    conn = connect(tmp_path / "i.db")
    refresh(conn, _adapters())
    row = conn.execute(
        "SELECT resume_command FROM sessions WHERE harness='pi' AND project='proj2'"
    ).fetchone()
    assert row["resume_command"].startswith("(cd /tmp/proj2 && pi --session ")


def test_rebuild_clears_and_recreates(tmp_path):
    conn = connect(tmp_path / "i.db")
    refresh(conn, _adapters())
    rebuild(conn)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    # refresh still works after rebuild
    refresh(conn, _adapters())
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 4
