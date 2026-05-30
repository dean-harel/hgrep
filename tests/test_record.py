from hgrep.record import SessionRecord


def test_session_record_holds_all_fields():
    rec = SessionRecord(
        harness="pi",
        session_id="abc",
        cwd="/tmp/p",
        project="p",
        git_branch=None,
        title="t",
        first_user_msg="hi",
        content_text="hi there",
        started_at="2026-05-01T10:00:00.000Z",
        last_activity_at="2026-05-01T10:05:00.000Z",
        msg_count=2,
        file_path="/tmp/p/abc.jsonl",
        file_mtime=1.0,
        file_size=10,
    )
    assert rec.harness == "pi"
    assert rec.git_branch is None
    assert rec.msg_count == 2
