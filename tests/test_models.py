from app.models import SessionIndex, TranscriptEntry, Transcript


def test_session_index_defaults():
    s = SessionIndex(session_id="abc", title="abc")
    assert s.message_count == 0
    assert s.outcome == "unknown"
    assert s.compacted is False
    assert s.context_tokens is None


def test_transcript_roundtrip():
    t = Transcript(session_id="abc", title="T",
                   entries=[TranscriptEntry(role="user", kind="text", content="hi")])
    dumped = t.model_dump()
    assert dumped["entries"][0]["role"] == "user"
    assert dumped["session_id"] == "abc"


def test_session_index_bookmarked_defaults_false():
    from app.models import SessionIndex
    s = SessionIndex(session_id="abc", title="abc")
    assert s.bookmarked is False
