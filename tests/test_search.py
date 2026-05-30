from pathlib import Path

from hgrep.harness.claude_code import ClaudeCodeAdapter
from hgrep.harness.pi import PiAdapter
from hgrep.index import connect, refresh
from hgrep.search import search, to_public, format_pretty

CLAUDE_ROOT = Path(__file__).parent / "fixtures" / "claude"
PI_ROOT = Path(__file__).parent / "fixtures" / "pi"


def _conn(tmp_path):
    conn = connect(tmp_path / "i.db")
    refresh(conn, [ClaudeCodeAdapter(root=CLAUDE_ROOT), PiAdapter(root=PI_ROOT)])
    return conn


def test_keyword_match_in_body(tmp_path):
    conn = _conn(tmp_path)
    results = search(conn, "retry")
    assert len(results) == 1
    assert results[0]["title"] == "Renewals"
    assert results[0]["harness"] == "claude-code"


def test_cross_harness_match(tmp_path):
    conn = _conn(tmp_path)
    titles = {r["title"] for r in search(conn, "deploy")}
    assert "Settlement deploy" in titles


def test_empty_query_returns_nothing(tmp_path):
    conn = _conn(tmp_path)
    assert search(conn, "   ") == []


def test_harness_filter(tmp_path):
    conn = _conn(tmp_path)
    pi_only = search(conn, "question", harness="pi")
    assert all(r["harness"] == "pi" for r in pi_only)
    assert pi_only  # at least one


def test_branch_filter_excludes_pi(tmp_path):
    conn = _conn(tmp_path)
    res = search(conn, "question", branch="feature")
    assert all(r["harness"] == "claude-code" for r in res)


def test_project_filter(tmp_path):
    conn = _conn(tmp_path)
    res = search(conn, "deploy", project="proj2")
    assert res and all("proj2" in r["project"] for r in res)


def test_to_public_curates_fields(tmp_path):
    conn = _conn(tmp_path)
    pub = to_public(search(conn, "retry"))[0]
    assert set(pub.keys()) == {
        "harness", "session_id", "title", "project", "cwd", "git_branch",
        "last_activity_at", "msg_count", "snippet", "resume_command",
    }


def test_format_pretty_returns_text(tmp_path):
    conn = _conn(tmp_path)
    out = format_pretty(search(conn, "retry"))
    assert "Renewals" in out
    assert "claude-code" in out


def test_until_bare_date_is_inclusive_of_that_day(tmp_path):
    conn = _conn(tmp_path)
    # the pi "Settlement deploy" session's last activity is 2026-05-02T08:00:05Z
    res = search(conn, "deploy", until="2026-05-02")
    assert any(r["title"] == "Settlement deploy" for r in res)


def test_until_relative_excludes_recent(tmp_path):
    conn = _conn(tmp_path)
    # all fixtures are dated 2026-05; an old absolute upper bound drops them all
    assert search(conn, "deploy", until="2020-01-01") == []
