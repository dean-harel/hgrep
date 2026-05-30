from pathlib import Path

from hgrep.harness.pi import PiAdapter

ROOT = Path(__file__).parent / "fixtures" / "pi"
F1 = ROOT / "--tmp-proj2--" / "2026-05-02T08-00-00-000Z_33333333-3333-3333-3333-333333333333.jsonl"
F2 = ROOT / "--tmp-proj3--" / "2026-05-03T08-00-00-000Z_44444444-4444-4444-4444-444444444444.jsonl"


def test_name_and_availability():
    a = PiAdapter(root=ROOT)
    assert a.name == "pi"
    assert a.is_available() is True
    assert PiAdapter(root=ROOT / "nope").is_available() is False


def test_iter_sessions_finds_both():
    a = PiAdapter(root=ROOT)
    names = {p.name for p, _m, _s in a.iter_sessions()}
    assert names == {F1.name, F2.name}


def test_parse_header_and_text_only():
    rec = PiAdapter(root=ROOT).parse(F1)
    assert rec.harness == "pi"
    assert rec.session_id == "33333333-3333-3333-3333-333333333333"
    assert rec.cwd == "/tmp/proj2"
    assert rec.project == "proj2"
    assert rec.git_branch is None
    assert rec.title == "Settlement deploy"  # session_info name wins
    assert rec.first_user_msg == "how do I deploy the settlement service"
    assert "deploy the settlement service" in rec.content_text
    assert "run the deploy script" in rec.content_text
    assert "PI_SECRET_THINKING" not in rec.content_text
    assert "PI_TOOL_OUTPUT" not in rec.content_text
    assert rec.started_at == "2026-05-02T08:00:00.000Z"
    assert rec.last_activity_at == "2026-05-02T08:00:05.000Z"
    assert rec.msg_count == 2


def test_title_falls_back_to_first_user_message():
    rec = PiAdapter(root=ROOT).parse(F2)
    assert rec.title == "pi fallback title question"


def test_resume_command():
    a = PiAdapter(root=ROOT)
    rec = a.parse(F1)
    assert a.resume_command(rec) == (
        "(cd /tmp/proj2 && pi --session 33333333-3333-3333-3333-333333333333)"
    )
