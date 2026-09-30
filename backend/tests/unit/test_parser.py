import json
import time
from concurrent.futures import ThreadPoolExecutor

from app.services import parser


def test_parse_transcript_entries(write_session):
    path = write_session(
        [
            {"type": "ai-title", "aiTitle": "Demo"},
            {
                "type": "user",
                "timestamp": "t1",
                "cwd": "/home/mario/projects/demo",
                "message": {"role": "user", "content": "please help"},
            },
            {
                "type": "assistant",
                "timestamp": "t2",
                "cwd": "/home/mario/projects/demo",
                "message": {
                    "model": "claude-opus-4-8",
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 1, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
                    "content": [
                        {"type": "thinking", "thinking": "let me think"},
                        {"type": "text", "text": "I'll run a command"},
                        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "t3",
                "cwd": "/home/mario/projects/demo",
                "message": {"role": "user", "content": [{"type": "tool_result", "content": "file1\nfile2"}]},
            },
        ]
    )
    tr = parser.parse_transcript(path)
    assert tr.title == "Demo"
    assert tr.model == "claude-opus-4-8"
    assert tr.context_tokens == 101
    kinds = [(e.role, e.kind) for e in tr.entries]
    assert ("user", "text") in kinds
    assert ("assistant", "thinking") in kinds
    assert ("assistant", "text") in kinds
    assert ("assistant", "tool_use") in kinds
    assert ("user", "tool_result") in kinds
    tool = next(e for e in tr.entries if e.kind == "tool_use")
    assert tool.tool_name == "Bash"
    assert "ls" in tool.content


def test_parse_transcript_compact_summary_as_system_note(write_session):
    path = write_session(
        [
            {
                "type": "user",
                "timestamp": "t1",
                "isCompactSummary": True,
                "message": {"role": "user", "content": "summary of prior work"},
            },
        ]
    )
    tr = parser.parse_transcript(path)
    assert tr.entries[0].role == "system"
    assert tr.entries[0].kind == "system_note"
    assert "compaction summary" in tr.entries[0].content


def test_parse_transcript_marks_sidechain(write_session):
    path = write_session(
        [
            {
                "type": "assistant",
                "timestamp": "t1",
                "isSidechain": True,
                "message": {
                    "model": "claude-opus-4-8",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "subagent output"}],
                },
            },
        ]
    )
    tr = parser.parse_transcript(path)
    assert tr.entries[0].is_sidechain is True


def _count_parses(monkeypatch):
    calls = []
    real = parser.parse_transcript

    def _spy(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(parser, "parse_transcript", _spy)
    return calls


def _prompt(text_str):
    return {"type": "user", "timestamp": "t1", "message": {"role": "user", "content": text_str}}


def test_load_transcript_reuses_parse_of_unchanged_file(write_session, monkeypatch):
    path = write_session([_prompt("hello")], session_id="cached")
    calls = _count_parses(monkeypatch)
    first = parser.load_transcript(path)
    assert parser.load_transcript(path) is first
    assert len(calls) == 1
    assert first.model_dump() == parser.parse_transcript(path).model_dump()


def test_load_transcript_reparses_appended_file(write_session, monkeypatch):
    path = write_session([_prompt("hello")], session_id="grows")
    calls = _count_parses(monkeypatch)
    parser.load_transcript(path)
    with path.open("a") as fh:
        fh.write(json.dumps(_prompt("appended")) + "\n")
    tr = parser.load_transcript(path)
    assert len(calls) == 2
    assert [e.content for e in tr.entries] == ["hello", "appended"]


def test_load_transcript_evicts_least_recently_used(write_session, monkeypatch):
    paths = [write_session([_prompt("hi")], session_id=f"lru{i}") for i in range(parser._CACHE_SIZE + 1)]
    calls = _count_parses(monkeypatch)
    for p in paths:
        parser.load_transcript(p)
    parser.load_transcript(paths[-1])  # still cached
    assert len(calls) == len(paths)
    parser.load_transcript(paths[0])  # evicted by the last one
    assert len(calls) == len(paths) + 1


def test_concurrent_load_transcript_parses_once(write_session, monkeypatch):
    path = write_session([_prompt("hello")], session_id="concurrent")
    calls = []
    real = parser.parse_transcript

    def _slow(p):
        calls.append(p)
        time.sleep(0.2)
        return real(p)

    monkeypatch.setattr(parser, "parse_transcript", _slow)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: parser.load_transcript(path), range(4)))
    assert len(calls) == 1
    assert all(r is results[0] for r in results)
