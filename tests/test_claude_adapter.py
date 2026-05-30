from pathlib import Path

from hgrep.harness.claude_code import ClaudeCodeAdapter

ROOT = Path(__file__).parent / "fixtures" / "claude"
F1 = ROOT / "-tmp-proj" / "11111111-1111-1111-1111-111111111111.jsonl"
F2 = ROOT / "-tmp-bar" / "22222222-2222-2222-2222-222222222222.jsonl"


def test_name_and_availability():
    a = ClaudeCodeAdapter(root=ROOT)
    assert a.name == "claude-code"
    assert a.is_available() is True
    assert ClaudeCodeAdapter(root=ROOT / "nope").is_available() is False


def test_iter_sessions_finds_both():
    a = ClaudeCodeAdapter(root=ROOT)
    paths = {p.name for p, _m, _s in a.iter_sessions()}
    assert paths == {F1.name, F2.name}


def test_parse_extracts_conversation_text_only():
    rec = ClaudeCodeAdapter(root=ROOT).parse(F1)
    assert rec.harness == "claude-code"
    assert rec.session_id == "11111111-1111-1111-1111-111111111111"
    assert rec.cwd == "/tmp/proj"
    assert rec.project == "proj"
    assert rec.git_branch == "main"
    assert rec.title == "Renewals"  # customTitle wins
    assert rec.first_user_msg == "fix the renewals retry bug"
    assert "renewals retry bug" in rec.content_text
    assert "look at the retry logic" in rec.content_text
    assert "SECRET_THINKING" not in rec.content_text
    assert "SECRET_TOOL_OUTPUT" not in rec.content_text
    assert rec.started_at == "2026-05-01T10:00:00.000Z"
    assert rec.last_activity_at == "2026-05-01T10:00:09.000Z"
    assert rec.msg_count == 3


def test_title_falls_back_to_first_user_message():
    rec = ClaudeCodeAdapter(root=ROOT).parse(F2)
    assert rec.title == "hello world question"
    assert rec.git_branch == "feature"


def test_resume_command():
    a = ClaudeCodeAdapter(root=ROOT)
    rec = a.parse(F1)
    assert a.resume_command(rec) == (
        "(cd /tmp/proj && claude --resume 11111111-1111-1111-1111-111111111111)"
    )
