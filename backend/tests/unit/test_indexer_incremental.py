import json
import random
from dataclasses import asdict

import pytest

from app.services import indexer
from app.services.jsonl import read_records

CWD = "/home/mario/projects/demo"


def _user(text_str, ts, **extra):
    return {"type": "user", "timestamp": ts, "cwd": CWD, "gitBranch": "main", **extra, "message": text_str}


def _prompt(text_str, ts, **extra):
    return _user({"role": "user", "content": text_str}, ts, **extra)


def _tool_result(ts):
    return _user({"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}, ts)


def _assistant(ts, stop_reason="end_turn", usage=None, model="claude-opus-4-8", **extra):
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": CWD,
        "gitBranch": "main",
        **extra,
        "message": {
            "model": model,
            "stop_reason": stop_reason,
            "usage": usage if usage is not None else {"input_tokens": 3, "cache_read_input_tokens": 1000},
            "content": [{"type": "text", "text": "ok ✓"}],
        },
    }


def _lines() -> list[bytes]:
    """A real-shaped session log that exercises every index aggregate and line-level oddity."""
    records = [
        {"type": "permission-mode", "permissionMode": "default"},
        _prompt("  first   prompt, whitespace collapsed ", "2026-05-30T09:00:00Z"),
        {"type": "ai-title", "aiTitle": "Early AI title"},
        _assistant("2026-05-30T09:00:05Z", stop_reason="tool_use"),
        _tool_result("2026-05-30T09:00:06Z"),
        _assistant("2026-05-30T09:00:07Z", usage={"input_tokens": 5, "cache_creation_input_tokens": 60000}),
        _prompt("meta reminder", "2026-06-30T00:00:00Z", isMeta=True),
        _assistant("2026-05-30T09:00:08Z", isSidechain=True),
        _prompt("second prompt", "2026-05-30T09:01:00Z"),
        _assistant("2026-05-30T09:01:05Z", model="<synthetic>", usage={"input_tokens": 999999}),
        {"type": "ai-title", "aiTitle": ""},  # empty title must not clear the earlier one
        _prompt("x" * 500, "2026-05-30T09:02:00Z"),  # truncated prompt
        _assistant("2026-05-30T09:02:05Z", stop_reason=None),
        {"type": "system", "content": "note", "compactMetadata": {"trigger": "auto"}},
        _prompt("compacted summary", "2026-05-30T09:03:00Z", isCompactSummary=True),
        _prompt("after compaction", "2026-05-30T09:04:00Z", interruptedMessageId="m1"),
        _assistant("2026-05-30T09:04:05Z", usage={"input_tokens": 1, "cache_read_input_tokens": 300000}),
        {"type": "last-prompt", "lastPrompt": "resume   from here"},
        {"type": "custom-title", "customTitle": "My custom title"},
        _assistant("2026-05-30T09:05:00Z", isApiErrorMessage=True),
        _user("not a dict message", "2026-05-30T09:06:00Z"),
        _prompt("late prompt", "2026-05-30T09:07:00Z"),
        _assistant("2026-05-30T09:07:05Z", stop_reason="stop_sequence", usage=[1, 2]),
        _assistant("2026-05-30T09:08:00Z", stop_reason="max_tokens"),
    ]
    lines = [json.dumps(r, ensure_ascii=False).encode() + b"\n" for r in records]
    lines[4:4] = [b"\n", b"   \n", b"not valid json\n", b"[1, 2, 3]\n"]  # blank, malformed, non-dict
    lines[9:9] = [json.dumps(_prompt("crlf ended", "2026-05-30T09:00:30Z")).encode() + b"\r\n"]
    lines[12:12] = [b'{"type": "ai-title", "aiTitle": "bad \xff\xfe utf8"}\n']
    # a lone CR ends a line in text mode too: two records on one physical line
    lines[16:16] = [b'{"type": "user", "isMeta": true}\r{"type": "custom-title", "customTitle": "cr split"}\n']
    return lines


def _reference(path):
    """From-scratch index built through the text-mode reader, independent of the byte-level splitter."""
    records, bad = read_records(path)
    state = indexer._ParseState()
    for r in records:
        state.feed(r)
    state.bad = bad
    return state.to_index(path.stem, path.stat())


@pytest.fixture
def spy_consume(monkeypatch):
    """Record the byte offset each parse starts reading from."""
    starts: list[int] = []
    real = indexer._consume

    def _spy(fh, state, limit):
        starts.append(state.offset)
        return real(fh, state, limit)

    monkeypatch.setattr(indexer, "_consume", _spy)
    return starts


def _check_stage(path, prev):
    idx, state = indexer._parse(path, prev)
    full = indexer.index_file(path)
    assert idx.model_dump() == full.model_dump()
    assert full.model_dump() == _reference(path).model_dump()
    data = path.read_bytes()
    assert state.offset <= len(data)
    assert state.offset == 0 or data[state.offset - 1 : state.offset] == b"\n"
    assert b"\n" not in data[state.offset :]  # only an unterminated line is left uncommitted
    return idx, state


def test_incremental_matches_full_parse_line_by_line(tmp_path, spy_consume):
    path = tmp_path / "p" / "sess.jsonl"
    path.parent.mkdir()
    path.write_bytes(b"")
    _, state = _check_stage(path, None)
    for line in _lines():
        with path.open("ab") as fh:
            fh.write(line)
        spy_consume.clear()
        prev_offset = state.offset
        idx, state = _check_stage(path, state)
        assert spy_consume[0] == prev_offset  # resumed, not re-parsed from the start
    assert idx.title == "My custom title"
    assert idx.first_prompt == "first prompt, whitespace collapsed"
    assert idx.last_prompt == "resume from here"
    assert idx.outcome == "interrupted"  # an interruptedMessageId earlier in the log sticks
    assert idx.compacted is True
    assert idx.unparsable_lines == 2


def test_incremental_matches_full_parse_across_partial_lines(tmp_path, spy_consume):
    """Random append sizes cut through lines and multi-byte characters, like a writer mid-append."""
    data = b"".join(_lines())
    path = tmp_path / "p" / "sess.jsonl"
    path.parent.mkdir()
    for seed in range(25):
        rng = random.Random(seed)
        path.write_bytes(b"")
        state = None
        pos = 0
        while pos < len(data):
            step = rng.choice([1, 2, 3, 7, 40, 200, 1000])
            with path.open("ab") as fh:
                fh.write(data[pos : pos + step])
            pos += step
            spy_consume.clear()
            prev_offset = state.offset if state else 0
            _, state = _check_stage(path, state)
            assert spy_consume[0] == prev_offset
        assert state is not None and state.offset == len(data)


def test_outcome_and_context_transitions_track_appends(tmp_path):
    path = tmp_path / "p" / "sess.jsonl"
    path.parent.mkdir()
    stages = [
        (_prompt("go", "2026-05-30T09:00:00Z"), "unknown", None),
        (_assistant("2026-05-30T09:00:01Z", stop_reason="tool_use"), "interrupted", 1003),
        (_tool_result("2026-05-30T09:00:02Z"), "clean", 1003),
        (
            _assistant("2026-05-30T09:00:03Z", usage={"input_tokens": 1, "cache_read_input_tokens": 250000}),
            "clean",
            250001,
        ),
        (_assistant("2026-05-30T09:00:04Z", stop_reason=None), "interrupted", 1003),
        (_assistant("2026-05-30T09:00:05Z", isApiErrorMessage=True), "error", 1003),
    ]
    path.write_bytes(b"")
    state = None
    for record, outcome, context in stages:
        with path.open("ab") as fh:
            fh.write(json.dumps(record).encode() + b"\n")
        idx, state = _check_stage(path, state)
        assert idx.outcome == outcome
        assert idx.context_tokens == context


def _write_and_parse(path, data):
    path.write_bytes(data)
    return indexer._parse(path, None)[1]


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda data: data[: len(data) // 2], id="shrank"),
        pytest.param(lambda data: b"{}" + data[2:] + b"{}\n", id="head-rewritten"),
        pytest.param(lambda data: data[:-3] + b"XX\n" + b"{}\n", id="tail-before-offset-rewritten"),
        pytest.param(lambda data: b"\n".join(data.split(b"\n")[1:]) + b"{}\n" * 400, id="head-line-dropped"),
    ],
)
def test_non_append_change_falls_back_to_full_parse(tmp_path, spy_consume, mutate):
    path = tmp_path / "p" / "sess.jsonl"
    path.parent.mkdir()
    data = b"".join(_lines())
    state = _write_and_parse(path, data)
    path.write_bytes(mutate(data))
    spy_consume.clear()
    idx, _ = indexer._parse(path, state)
    assert spy_consume == [0]
    assert idx.model_dump() == indexer.index_file(path).model_dump()


def test_build_index_resumes_from_cache_file_after_restart(tmp_path, spy_consume):
    root = tmp_path / "projects"
    path = root / "p" / "sess.jsonl"
    path.parent.mkdir(parents=True)
    lines = _lines()
    path.write_bytes(b"".join(lines[:-3]))
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    committed = path.stat().st_size

    indexer._stores.pop(cache)  # a fresh process: memory is empty, cache.json is the seed
    with path.open("ab") as fh:
        fh.write(b"".join(lines[-3:]))
    spy_consume.clear()
    sessions = indexer.build_index(root, cache)
    assert spy_consume == [committed]
    assert sessions[0].model_dump() == indexer.index_file(path).model_dump()


def test_from_json_rejects_wrong_typed_aggregates(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_bytes(b"".join(_lines()))
    _, state = indexer._parse(path, None)
    good = json.loads(json.dumps(asdict(state)))
    assert indexer._ParseState.from_json(good) is not None
    for field_name, bad_value in [
        ("last_activity", 5),
        ("last_usage", ["not", "a", "dict"]),
        ("compacted", "yes"),
        ("first_prompt", 1.5),
        ("last_role", 0),
    ]:
        raw = dict(good)
        raw[field_name] = bad_value
        assert indexer._ParseState.from_json(raw) is None, field_name


def test_parse_survives_poisoned_resume_state(tmp_path):
    """A resume state that slips past validation must fall back to a full parse, never raise."""
    path = tmp_path / "s.jsonl"
    lines = _lines()
    path.write_bytes(b"".join(lines[: len(lines) // 2]))
    _, state = indexer._parse(path, None)
    setattr(state, "last_activity", 5)  # bypasses from_json, as in-memory corruption would
    path.write_bytes(b"".join(lines))
    expected, _ = indexer._parse(path, None)
    got, _ = indexer._parse(path, state)
    assert got == expected
