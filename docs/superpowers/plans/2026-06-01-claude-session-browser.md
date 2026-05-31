# Claude Session Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local FastAPI web page that indexes Claude Code session JSONL logs into a sortable/searchable table (title, description, state, context usage) and renders a read-only transcript when a row is clicked.

**Architecture:** Small Python/FastAPI backend scans `~/.claude/projects/`, builds a lightweight index cached by file mtime+size (eager), and parses a full transcript only on demand (lazy). A vanilla HTML/JS/CSS frontend renders the table and transcript view. No build toolchain.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic v2, pytest, httpx (TestClient). Frontend: vanilla HTML/CSS/JS.

**Conventions for every task:** Run tests inside the project venv (`.venv/bin/python -m pytest ...`). Commit after each task passes. Work on `master`.

---

## File Structure

```
my-sessions/
├── pyproject.toml          # deps + pytest config
├── app/
│   ├── __init__.py
│   ├── tokens.py           # context-fill / window-size / pct math
│   ├── jsonl.py            # streaming + buffered JSONL readers
│   ├── text.py             # message text extraction + truncation + prompt detection
│   ├── models.py           # pydantic schemas: SessionIndex, TranscriptEntry, Transcript
│   ├── indexer.py          # index_file, build_index (+cache), find_session_path, compute_outcome
│   ├── parser.py           # parse_transcript (single file → render-ready entries)
│   └── main.py             # FastAPI routes + static serving
├── static/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── conftest.py         # fixture helpers (write_session)
│   ├── test_tokens.py
│   ├── test_jsonl.py
│   ├── test_text.py
│   ├── test_indexer.py
│   ├── test_parser.py
│   └── test_api.py
├── run.sh                  # launcher: uvicorn app.main:app
└── cache.json              # generated, gitignored
```

**Module responsibilities:**
- `tokens.py` — pure math, no I/O.
- `jsonl.py` — file reading, malformed-line tolerance, no domain logic.
- `text.py` — pure string helpers, no I/O.
- `models.py` — data shapes only.
- `indexer.py` — cheap summary extraction + caching + lookup.
- `parser.py` — full transcript extraction for one file.
- `main.py` — HTTP layer only; delegates to indexer/parser.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "claude-session-browser"
version = "0.1.0"
description = "Local web browser for Claude Code session logs"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "pydantic>=2.7",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create empty package markers**

Create `app/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Create the venv and install**

Run:
```bash
uv venv && uv pip install -e ".[dev]"
```
Expected: venv created at `.venv`, packages installed without error.

- [ ] **Step 4: Verify pytest runs (collects nothing yet)**

Run: `.venv/bin/python -m pytest`
Expected: `no tests ran` (exit code 5 is fine) — confirms pytest is wired up.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml app/__init__.py tests/__init__.py
git commit -m "chore: scaffold project and dev deps"
```

---

### Task 2: Token math (`tokens.py`)

**Files:**
- Create: `app/tokens.py`
- Test: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tokens.py
from app import tokens


def test_context_fill_sums_input_side_only():
    usage = {
        "input_tokens": 6,
        "cache_creation_input_tokens": 45351,
        "cache_read_input_tokens": 1000,
        "output_tokens": 9999,  # must be ignored
    }
    assert tokens.context_fill(usage) == 6 + 45351 + 1000


def test_context_fill_handles_none_and_missing():
    assert tokens.context_fill(None) == 0
    assert tokens.context_fill({}) == 0
    assert tokens.context_fill({"input_tokens": None}) == 0


def test_window_size_defaults_to_200k():
    assert tokens.window_size(150_000) == 200_000


def test_window_size_switches_to_1m_when_over_200k():
    assert tokens.window_size(200_001) == 1_000_000
    assert tokens.window_size(494_037) == 1_000_000


def test_context_pct():
    assert tokens.context_pct(50_000, 200_000) == 25.0
    assert tokens.context_pct(0, 200_000) == 0.0
    assert tokens.context_pct(100, 0) == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.tokens'`.

- [ ] **Step 3: Implement `app/tokens.py`**

```python
"""Token-usage and context-window math for Claude session logs."""

DEFAULT_WINDOW = 200_000
LARGE_WINDOW = 1_000_000


def context_fill(usage: dict | None) -> int:
    """Input-side token count for a single assistant usage block.

    This equals the size of the prompt sent for that request, i.e. how full
    the context window was at that turn. Output tokens are excluded on purpose,
    and we never sum across messages.
    """
    if not usage:
        return 0
    return (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )


def window_size(observed_tokens: int) -> int:
    """Context window size: 200k default, 1M if usage exceeds 200k.

    The JSONL does not record the 1M-beta header, so exceeding the standard
    window is the only reliable signal that the larger window was active.
    """
    return LARGE_WINDOW if observed_tokens > DEFAULT_WINDOW else DEFAULT_WINDOW


def context_pct(tokens_used: int, window: int) -> float:
    if window <= 0:
        return 0.0
    return round(100.0 * tokens_used / window, 1)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tokens.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tokens.py tests/test_tokens.py
git commit -m "feat: token-usage and context-window math"
```

---

### Task 3: JSONL reader (`jsonl.py`)

**Files:**
- Create: `app/jsonl.py`
- Test: `tests/test_jsonl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jsonl.py
from app import jsonl


def test_read_records_parses_and_counts_bad(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(
        '{"type": "user", "n": 1}\n'
        '\n'                       # blank line ignored
        'not valid json\n'         # malformed -> counted
        '{"type": "assistant", "n": 2}\n'
    )
    records, bad = jsonl.read_records(f)
    assert [r["n"] for r in records] == [1, 2]
    assert bad == 1


def test_read_records_empty_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    records, bad = jsonl.read_records(f)
    assert records == []
    assert bad == 0


def test_iter_records_skips_malformed(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"a": 1}\nbad\n{"a": 2}\n')
    assert [r["a"] for r in jsonl.iter_records(f)] == [1, 2]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_jsonl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.jsonl'`.

- [ ] **Step 3: Implement `app/jsonl.py`**

```python
"""Streaming and buffered readers for Claude Code session .jsonl files."""
import json
from pathlib import Path
from typing import Iterator


def iter_records(path: Path) -> Iterator[dict]:
    """Yield parsed JSON objects, skipping blank and malformed lines.

    Append-only logs can end with a partial write; such lines are skipped.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_records(path: Path) -> tuple[list[dict], int]:
    """Return (records, unparsable_line_count)."""
    records: list[dict] = []
    bad = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return records, bad
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_jsonl.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/jsonl.py tests/test_jsonl.py
git commit -m "feat: malformed-tolerant JSONL readers"
```

---

### Task 4: Text helpers (`text.py`)

**Files:**
- Create: `app/text.py`
- Test: `tests/test_text.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_text.py
from app import text


def test_message_text_from_string():
    assert text.message_text({"content": "hello"}) == "hello"


def test_message_text_from_blocks_joins_text_only():
    msg = {"content": [
        {"type": "text", "text": "first"},
        {"type": "tool_use", "name": "Bash", "input": {}},
        {"type": "text", "text": "second"},
    ]}
    assert text.message_text(msg) == "first\nsecond"


def test_message_text_missing_content():
    assert text.message_text({}) == ""


def test_truncate_collapses_whitespace_and_limits():
    assert text.truncate("a\n\n  b   c") == "a b c"
    long = "x" * 300
    out = text.truncate(long, 200)
    assert len(out) == 200 and out.endswith("…")


def test_is_real_user_prompt():
    assert text.is_real_user_prompt({"content": "do a thing"}) is True
    assert text.is_real_user_prompt({"content": "   "}) is False
    assert text.is_real_user_prompt({"content": [
        {"type": "tool_result", "content": "output"}]}) is False
    assert text.is_real_user_prompt({"content": [
        {"type": "text", "text": "real prompt"}]}) is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.text'`.

- [ ] **Step 3: Implement `app/text.py`**

```python
"""Pure helpers for extracting and trimming text from message records."""


def message_text(message: dict) -> str:
    """Flatten a message's content into plain text (text blocks only)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return ""


def truncate(text_in: str, limit: int = 200) -> str:
    """Collapse whitespace and cap length with an ellipsis."""
    collapsed = " ".join((text_in or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def is_real_user_prompt(message: dict) -> bool:
    """True if the message carries actual typed user text (not a tool_result)."""
    content = message.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and (block.get("text") or "").strip()
            ):
                return True
    return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_text.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/text.py tests/test_text.py
git commit -m "feat: message text extraction helpers"
```

---

### Task 5: Pydantic models (`models.py`)

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement `app/models.py`**

```python
"""Pydantic data shapes for the session index and transcript."""
from pydantic import BaseModel


class SessionIndex(BaseModel):
    session_id: str
    title: str
    first_prompt: str | None = None
    last_prompt: str | None = None
    cwd: str | None = None
    git_branch: str | None = None
    last_activity: str | None = None       # ISO timestamp string
    message_count: int = 0
    context_tokens: int | None = None
    context_pct: float | None = None
    window_size: int | None = None
    model: str | None = None
    outcome: str = "unknown"               # clean | interrupted | error | unknown
    compacted: bool = False
    unparsable_lines: int = 0
    file_mtime: float = 0.0
    file_size: int = 0


class TranscriptEntry(BaseModel):
    role: str                              # user | assistant | system
    kind: str                              # text | thinking | tool_use | tool_result | system_note
    content: str = ""
    tool_name: str | None = None
    timestamp: str | None = None
    is_sidechain: bool = False


class Transcript(BaseModel):
    session_id: str
    title: str
    cwd: str | None = None
    model: str | None = None
    context_tokens: int | None = None
    context_pct: float | None = None
    outcome: str = "unknown"
    entries: list[TranscriptEntry] = []
    unparsable_lines: int = 0
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: pydantic models for index and transcript"
```

---

### Task 6: Index extraction (`indexer.py` — `index_file` + `compute_outcome`)

**Files:**
- Create: `app/indexer.py`
- Create: `tests/conftest.py`
- Test: `tests/test_indexer.py`

- [ ] **Step 1: Create the shared fixture helper**

```python
# tests/conftest.py
import json
import pytest


@pytest.fixture
def write_session(tmp_path):
    """Write a list of record dicts to a <project>/<session_id>.jsonl file."""
    def _write(records, project="-home-mario-projects-demo", session_id="sess1"):
        proj_dir = tmp_path / project
        proj_dir.mkdir(parents=True, exist_ok=True)
        path = proj_dir / f"{session_id}.jsonl"
        with path.open("w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return path
    return _write
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_indexer.py
from app import indexer


def _assistant(stop_reason="end_turn", usage=None, model="claude-opus-4-8"):
    return {
        "type": "assistant", "timestamp": "2026-05-30T10:00:00Z",
        "cwd": "/home/mario/projects/demo", "gitBranch": "main",
        "message": {"model": model, "stop_reason": stop_reason,
                    "usage": usage or {}, "content": [{"type": "text", "text": "ok"}]},
    }


def _user(text_str, ts="2026-05-30T09:59:00Z"):
    return {"type": "user", "timestamp": ts,
            "cwd": "/home/mario/projects/demo", "gitBranch": "main",
            "message": {"role": "user", "content": text_str}}


def test_index_file_basic_fields(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "My Session Title"},
        _user("the first prompt", ts="2026-05-30T09:00:00Z"),
        _assistant(usage={"input_tokens": 5, "cache_read_input_tokens": 45000,
                          "cache_creation_input_tokens": 5000}),
        _user("the last prompt", ts="2026-05-30T09:30:00Z"),
    ], session_id="sess1")
    idx = indexer.index_file(path)
    assert idx.session_id == "sess1"
    assert idx.title == "My Session Title"
    assert idx.first_prompt == "the first prompt"
    assert idx.last_prompt == "the last prompt"
    assert idx.cwd == "/home/mario/projects/demo"
    assert idx.git_branch == "main"
    assert idx.context_tokens == 50005
    assert idx.window_size == 200_000
    assert idx.model == "claude-opus-4-8"
    assert idx.outcome == "clean"
    assert idx.message_count == 3   # 2 user + 1 assistant


def test_title_falls_back_to_session_id(write_session):
    path = write_session([_user("hi"), _assistant()], session_id="no-title-here")
    idx = indexer.index_file(path)
    assert idx.title == "no-title-here"


def test_custom_title_overrides_ai_title(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "auto"},
        {"type": "custom-title", "customTitle": "MINE"},
        _user("hi"), _assistant(),
    ])
    assert indexer.index_file(path).title == "MINE"


def test_outcome_interrupted_on_dangling_tool_use(write_session):
    path = write_session([_user("hi"), _assistant(stop_reason="tool_use")])
    assert indexer.index_file(path).outcome == "interrupted"


def test_outcome_error_on_api_error(write_session):
    err = _assistant()
    err["message"]["isApiErrorMessage"] = True
    path = write_session([_user("hi"), err])
    assert indexer.index_file(path).outcome == "error"


def test_compacted_flag_and_1m_window(write_session):
    path = write_session([
        _user("hi"),
        {"type": "system", "compactMetadata": {"trigger": "auto"}},
        _assistant(usage={"input_tokens": 1, "cache_read_input_tokens": 300000,
                          "cache_creation_input_tokens": 0}),
    ])
    idx = indexer.index_file(path)
    assert idx.compacted is True
    assert idx.window_size == 1_000_000


def test_sidechain_records_excluded(write_session):
    side = _assistant()
    side["isSidechain"] = True
    path = write_session([_user("hi"), _assistant(), side])
    # only 1 user + 1 assistant counted, sidechain ignored
    assert indexer.index_file(path).message_count == 2


def test_last_prompt_field_preferred(write_session):
    path = write_session([
        _user("opening", ts="2026-05-30T09:00:00Z"),
        _assistant(),
        {"type": "last-prompt", "lastPrompt": "resume here please"},
    ])
    assert indexer.index_file(path).last_prompt == "resume here please"
    assert indexer.index_file(path).first_prompt == "opening"


def test_synthetic_model_ignored_for_model_and_usage(write_session):
    synth = _assistant(model="<synthetic>", usage={"input_tokens": 9})
    path = write_session([_user("hi"), synth])
    idx = indexer.index_file(path)
    assert idx.model is None
    assert idx.context_tokens is None
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_indexer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.indexer'`.

- [ ] **Step 4: Implement `app/indexer.py` (index_file + compute_outcome)**

```python
"""Build a lightweight, cached index of all Claude Code sessions."""
from pathlib import Path

from . import tokens
from .jsonl import read_records
from .models import SessionIndex
from .text import is_real_user_prompt, message_text, truncate


def default_root() -> Path:
    return Path.home() / ".claude" / "projects"


def compute_outcome(convo: list[tuple[str, dict]], interrupted_flag: bool) -> str:
    """Classify session end state from the ordered conversation records."""
    if not convo:
        return "unknown"
    last_assistant = None
    for role, rec in convo:
        if role == "assistant":
            last_assistant = rec
    if last_assistant is None:
        return "unknown"
    msg = last_assistant.get("message", {}) or {}
    if last_assistant.get("isApiErrorMessage") or msg.get("isApiErrorMessage"):
        return "error"
    if interrupted_flag:
        return "interrupted"
    stop = msg.get("stop_reason")
    last_role = convo[-1][0]
    if stop == "tool_use" and last_role == "assistant":
        return "interrupted"          # tool call never returned a result
    if stop in ("end_turn", "stop_sequence"):
        return "clean"
    if stop is None:
        return "interrupted"          # never finalized
    return "clean"


def index_file(path: Path) -> SessionIndex:
    records, bad = read_records(path)
    stat = path.stat()

    ai_title = custom_title = None
    cwd = git_branch = None
    first_prompt = last_prompt = None
    last_prompt_field = None
    last_activity = None
    last_usage = None
    last_model = None
    compacted = False
    interrupted_flag = False
    convo: list[tuple[str, dict]] = []

    for r in records:
        t = r.get("type")
        if t == "ai-title":
            ai_title = r.get("aiTitle") or ai_title
            continue
        if t == "custom-title":
            custom_title = r.get("customTitle") or custom_title
            continue
        if t == "last-prompt":
            last_prompt_field = r.get("lastPrompt") or last_prompt_field
            continue
        if t == "system":
            if r.get("compactMetadata"):
                compacted = True
            continue
        if t not in ("user", "assistant"):
            continue
        if r.get("isSidechain"):
            continue

        cwd = cwd or r.get("cwd")
        git_branch = git_branch or r.get("gitBranch")
        ts = r.get("timestamp")
        if ts and (last_activity is None or ts > last_activity):
            last_activity = ts
        msg = r.get("message", {}) or {}

        if t == "user":
            if r.get("isMeta") or r.get("isCompactSummary"):
                continue
            if r.get("interruptedMessageId"):
                interrupted_flag = True
            convo.append(("user", r))
            if is_real_user_prompt(msg):
                txt = truncate(message_text(msg))
                if txt:
                    if first_prompt is None:
                        first_prompt = txt
                    last_prompt = txt
        else:  # assistant
            model = msg.get("model")
            convo.append(("assistant", r))
            if model and model != "<synthetic>":
                last_model = model
                if msg.get("usage"):
                    last_usage = msg["usage"]

    outcome = compute_outcome(convo, interrupted_flag)

    context_tokens = tokens.context_fill(last_usage) if last_usage else None
    win = tokens.window_size(context_tokens) if context_tokens is not None else None
    pct = tokens.context_pct(context_tokens, win) if context_tokens is not None else None

    return SessionIndex(
        session_id=path.stem,
        title=custom_title or ai_title or path.stem,
        first_prompt=first_prompt,
        last_prompt=truncate(last_prompt_field) if last_prompt_field else last_prompt,
        cwd=cwd,
        git_branch=git_branch,
        last_activity=last_activity,
        message_count=len(convo),
        context_tokens=context_tokens,
        context_pct=pct,
        window_size=win,
        model=last_model,
        outcome=outcome,
        compacted=compacted,
        unparsable_lines=bad,
        file_mtime=stat.st_mtime,
        file_size=stat.st_size,
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_indexer.py -v`
Expected: PASS (9 passed).

- [ ] **Step 6: Commit**

```bash
git add app/indexer.py tests/conftest.py tests/test_indexer.py
git commit -m "feat: per-file session index extraction and outcome classification"
```

---

### Task 7: Index building, caching, lookup (`indexer.py` additions)

**Files:**
- Modify: `app/indexer.py` (append functions)
- Test: `tests/test_indexer_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_indexer_cache.py
import json
from app import indexer


def _user(text_str, ts):
    return {"type": "user", "timestamp": ts,
            "cwd": "/home/mario/projects/demo",
            "message": {"role": "user", "content": text_str}}


def test_build_index_sorts_newest_first(tmp_path):
    root = tmp_path / "projects"
    (root / "p1").mkdir(parents=True)
    (root / "p2").mkdir(parents=True)
    (root / "p1" / "old.jsonl").write_text(
        json.dumps(_user("old", "2026-01-01T00:00:00Z")) + "\n")
    (root / "p2" / "new.jsonl").write_text(
        json.dumps(_user("new", "2026-05-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"
    sessions = indexer.build_index(root, cache)
    assert [s.session_id for s in sessions] == ["new", "old"]
    assert cache.exists()


def test_build_index_uses_cache_until_mtime_changes(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps(_user("hello", "2026-01-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"

    indexer.build_index(root, cache)
    raw = json.loads(cache.read_text())
    # tamper the cached title to prove the cache is reused (no re-parse)
    key = next(iter(raw))
    raw[key]["title"] = "FROM_CACHE"
    cache.write_text(json.dumps(raw))

    again = indexer.build_index(root, cache)
    assert again[0].title == "FROM_CACHE"   # served from cache, not re-parsed

    # changing the file invalidates the cache entry
    f.write_text(json.dumps(_user("changed", "2026-02-01T00:00:00Z")) + "\n")
    refreshed = indexer.build_index(root, cache)
    assert refreshed[0].title != "FROM_CACHE"


def test_build_index_force_ignores_cache(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps(_user("hello", "2026-01-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    raw = json.loads(cache.read_text())
    key = next(iter(raw))
    raw[key]["title"] = "FROM_CACHE"
    cache.write_text(json.dumps(raw))
    forced = indexer.build_index(root, cache, force=True)
    assert forced[0].title != "FROM_CACHE"


def test_find_session_path(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "abc123.jsonl").write_text("{}\n")
    assert indexer.find_session_path(root, "abc123").name == "abc123.jsonl"
    assert indexer.find_session_path(root, "missing") is None


def test_find_session_path_rejects_traversal(tmp_path):
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    assert indexer.find_session_path(root, "../../etc/passwd") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_indexer_cache.py -v`
Expected: FAIL with `AttributeError: module 'app.indexer' has no attribute 'build_index'`.

- [ ] **Step 3: Append to `app/indexer.py`**

Add these imports at the top of `app/indexer.py` (the `json` and `re` modules):

```python
import json
import re
```

Append at the end of `app/indexer.py`:

```python
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache_path: Path, entries: dict) -> None:
    cache_path.write_text(json.dumps(entries))


def build_index(root: Path, cache_path: Path, force: bool = False) -> list[SessionIndex]:
    """Scan root for sessions, reusing cache entries whose mtime+size match."""
    cache = {} if force else load_cache(cache_path)
    fresh: dict = {}
    sessions: list[SessionIndex] = []
    if root.exists():
        for path in root.glob("*/*.jsonl"):
            key = str(path)
            stat = path.stat()
            cached = cache.get(key)
            if (
                cached
                and cached.get("file_mtime") == stat.st_mtime
                and cached.get("file_size") == stat.st_size
            ):
                idx = SessionIndex(**cached)
            else:
                idx = index_file(path)
            fresh[key] = idx.model_dump()
            sessions.append(idx)
    save_cache(cache_path, fresh)
    sessions.sort(key=lambda s: s.last_activity or "", reverse=True)
    return sessions


def find_session_path(root: Path, session_id: str) -> Path | None:
    """Resolve a session id to its file, rejecting anything non-id-shaped."""
    if not _SESSION_ID_RE.match(session_id):
        return None
    matches = list(root.glob(f"*/{session_id}.jsonl"))
    return matches[0] if matches else None
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_indexer_cache.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add app/indexer.py tests/test_indexer_cache.py
git commit -m "feat: cached index build, sorting, and session lookup"
```

---

### Task 8: Transcript parser (`parser.py`)

**Files:**
- Create: `app/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser.py
from app import parser


def test_parse_transcript_entries(write_session):
    path = write_session([
        {"type": "ai-title", "aiTitle": "Demo"},
        {"type": "user", "timestamp": "t1", "cwd": "/home/mario/projects/demo",
         "message": {"role": "user", "content": "please help"}},
        {"type": "assistant", "timestamp": "t2", "cwd": "/home/mario/projects/demo",
         "message": {"model": "claude-opus-4-8", "stop_reason": "tool_use",
                     "usage": {"input_tokens": 1, "cache_read_input_tokens": 100,
                               "cache_creation_input_tokens": 0},
                     "content": [
                         {"type": "thinking", "thinking": "let me think"},
                         {"type": "text", "text": "I'll run a command"},
                         {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                     ]}},
        {"type": "user", "timestamp": "t3", "cwd": "/home/mario/projects/demo",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "content": "file1\nfile2"}]}},
    ])
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
    path = write_session([
        {"type": "user", "timestamp": "t1", "isCompactSummary": True,
         "message": {"role": "user", "content": "summary of prior work"}},
    ])
    tr = parser.parse_transcript(path)
    assert tr.entries[0].role == "system"
    assert tr.entries[0].kind == "system_note"
    assert "compaction summary" in tr.entries[0].content


def test_parse_transcript_marks_sidechain(write_session):
    path = write_session([
        {"type": "assistant", "timestamp": "t1", "isSidechain": True,
         "message": {"model": "claude-opus-4-8", "stop_reason": "end_turn",
                     "content": [{"type": "text", "text": "subagent output"}]}},
    ])
    tr = parser.parse_transcript(path)
    assert tr.entries[0].is_sidechain is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.parser'`.

- [ ] **Step 3: Implement `app/parser.py`**

```python
"""Parse a single session file into a render-ready transcript."""
import json
from pathlib import Path

from . import tokens
from .jsonl import read_records
from .models import Transcript, TranscriptEntry
from .text import message_text, truncate


def _stringify(data) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def parse_transcript(path: Path) -> Transcript:
    records, bad = read_records(path)
    entries: list[TranscriptEntry] = []
    ai_title = custom_title = None
    cwd = None
    last_usage = None
    last_model = None

    for r in records:
        t = r.get("type")
        if t == "ai-title":
            ai_title = r.get("aiTitle") or ai_title
            continue
        if t == "custom-title":
            custom_title = r.get("customTitle") or custom_title
            continue
        if t == "system":
            content = r.get("content")
            if isinstance(content, str) and content.strip():
                entries.append(TranscriptEntry(
                    role="system", kind="system_note",
                    content=truncate(content, 500), timestamp=r.get("timestamp")))
            continue
        if t not in ("user", "assistant"):
            continue

        cwd = cwd or r.get("cwd")
        ts = r.get("timestamp")
        sc = bool(r.get("isSidechain"))
        msg = r.get("message", {}) or {}

        if t == "user":
            if r.get("isCompactSummary"):
                entries.append(TranscriptEntry(
                    role="system", kind="system_note",
                    content="[compaction summary] " + truncate(message_text(msg), 500),
                    timestamp=ts, is_sidechain=sc))
                continue
            content = msg.get("content")
            handled = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        out = block.get("content")
                        text = out if isinstance(out, str) else message_text({"content": out})
                        entries.append(TranscriptEntry(
                            role="user", kind="tool_result",
                            content=truncate(text or "", 2000),
                            timestamp=ts, is_sidechain=sc))
                        handled = True
            if not handled:
                txt = message_text(msg)
                if txt.strip():
                    entries.append(TranscriptEntry(
                        role="user", kind="text", content=txt,
                        timestamp=ts, is_sidechain=sc))
        else:  # assistant
            model = msg.get("model")
            if model and model != "<synthetic>":
                last_model = model
                if msg.get("usage"):
                    last_usage = msg["usage"]
            content = msg.get("content")
            if isinstance(content, str):
                if content.strip():
                    entries.append(TranscriptEntry(
                        role="assistant", kind="text", content=content,
                        timestamp=ts, is_sidechain=sc))
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get("type")
                    if bt == "text" and (block.get("text") or "").strip():
                        entries.append(TranscriptEntry(
                            role="assistant", kind="text", content=block["text"],
                            timestamp=ts, is_sidechain=sc))
                    elif bt == "thinking" and (block.get("thinking") or "").strip():
                        entries.append(TranscriptEntry(
                            role="assistant", kind="thinking", content=block["thinking"],
                            timestamp=ts, is_sidechain=sc))
                    elif bt == "tool_use":
                        entries.append(TranscriptEntry(
                            role="assistant", kind="tool_use",
                            tool_name=block.get("name"),
                            content=truncate(_stringify(block.get("input")), 2000),
                            timestamp=ts, is_sidechain=sc))

    context_tokens = tokens.context_fill(last_usage) if last_usage else None
    win = tokens.window_size(context_tokens) if context_tokens is not None else None
    pct = tokens.context_pct(context_tokens, win) if context_tokens is not None else None

    return Transcript(
        session_id=path.stem,
        title=custom_title or ai_title or path.stem,
        cwd=cwd,
        model=last_model,
        context_tokens=context_tokens,
        context_pct=pct,
        outcome="unknown",
        entries=entries,
        unparsable_lines=bad,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser.py
git commit -m "feat: render-ready transcript parser"
```

---

### Task 9: FastAPI app + API tests (`main.py`)

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py
import json
import importlib
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps({"type": "ai-title", "aiTitle": "Hello World"}) + "\n"
        + json.dumps({"type": "user", "timestamp": "2026-05-01T00:00:00Z",
                      "cwd": "/home/mario/projects/demo",
                      "message": {"role": "user", "content": "do the thing"}}) + "\n"
        + json.dumps({"type": "assistant", "timestamp": "2026-05-01T00:01:00Z",
                      "cwd": "/home/mario/projects/demo",
                      "message": {"model": "claude-opus-4-8", "stop_reason": "end_turn",
                                  "usage": {"input_tokens": 1, "cache_read_input_tokens": 100,
                                            "cache_creation_input_tokens": 0},
                                  "content": [{"type": "text", "text": "done"}]}}) + "\n"
    )
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    return TestClient(main.app)


def test_list_sessions(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"][0]["title"] == "Hello World"
    assert data["sessions"][0]["context_tokens"] == 101
    assert "/home/mario/projects/demo" in data["projects"]


def test_search_filters(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    assert len(client.get("/api/sessions?q=hello").json()["sessions"]) == 1
    assert len(client.get("/api/sessions?q=nomatch").json()["sessions"]) == 0


def test_project_filter(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    url = "/api/sessions?project=/home/mario/projects/demo"
    assert len(client.get(url).json()["sessions"]) == 1
    assert len(client.get("/api/sessions?project=/nope").json()["sessions"]) == 0


def test_get_transcript(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    resp = client.get("/api/sessions/sess1")
    assert resp.status_code == 200
    tr = resp.json()
    assert tr["title"] == "Hello World"
    assert any(e["kind"] == "text" and e["role"] == "user" for e in tr["entries"])


def test_get_transcript_404(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    assert client.get("/api/sessions/missing").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Implement `app/main.py`**

```python
"""FastAPI app: session index API + transcript API + static frontend."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import indexer, parser

ROOT = indexer.default_root()
_BASE = Path(__file__).resolve().parent.parent
CACHE = _BASE / "cache.json"
STATIC = _BASE / "static"

app = FastAPI(title="Claude Session Browser")


@app.get("/api/sessions")
def list_sessions(q: str | None = None, project: str | None = None,
                  refresh: bool = False):
    all_sessions = indexer.build_index(ROOT, CACHE, force=refresh)
    projects = sorted({s.cwd for s in all_sessions if s.cwd})
    sessions = all_sessions
    if project:
        sessions = [s for s in sessions if s.cwd == project]
    if q:
        ql = q.lower()
        sessions = [
            s for s in sessions
            if any(ql in (v or "").lower()
                   for v in (s.title, s.first_prompt, s.last_prompt))
        ]
    return {"sessions": [s.model_dump() for s in sessions], "projects": projects}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    path = indexer.find_session_path(ROOT, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    return parser.parse_transcript(path).model_dump()


@app.get("/")
def index_page():
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
```

Note: the route order matters — `/api/sessions/{session_id}` is declared after the static-list route, and the literal `/api/sessions` path takes precedence over the parameterized one in FastAPI, so there is no collision.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: FastAPI routes for session list and transcript"
```

---

### Task 10: Frontend (table + transcript view) and launcher

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`
- Create: `run.sh`

This task is verified manually (the JS is exercised against the running server), not by pytest.

- [ ] **Step 1: Create `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Claude Sessions</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <header>
    <h1>Claude Sessions</h1>
    <div class="controls">
      <input id="search" type="search" placeholder="Search title / prompts…" />
      <select id="project"><option value="">All projects</option></select>
      <button id="rescan" title="Re-scan logs">↻ Rescan</button>
    </div>
  </header>

  <main>
    <div id="list-view">
      <table id="sessions">
        <thead>
          <tr>
            <th data-sort="title">Title</th>
            <th data-sort="cwd">Project</th>
            <th>Description</th>
            <th data-sort="outcome">State</th>
            <th data-sort="context_pct">Context</th>
            <th data-sort="last_activity">Last active</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
      <p id="count" class="muted"></p>
    </div>

    <div id="detail-view" hidden>
      <button id="back">← Back</button>
      <div id="detail-header"></div>
      <div id="entries"></div>
    </div>
  </main>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `static/styles.css`**

```css
:root {
  --bg: #0f1115; --panel: #181b22; --line: #272b34;
  --fg: #e6e8ec; --muted: #8b93a1; --accent: #6ea8fe;
  --clean: #4 caf50; --interrupted: #e6a23c; --error: #f56c6c;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif;
}
header {
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
  padding: 0.75rem 1rem; border-bottom: 1px solid var(--line);
  position: sticky; top: 0; background: var(--bg); z-index: 5;
}
header h1 { font-size: 1.1rem; margin: 0; }
.controls { display: flex; gap: 0.5rem; margin-left: auto; }
input, select, button {
  background: var(--panel); color: var(--fg);
  border: 1px solid var(--line); border-radius: 6px; padding: 0.4rem 0.6rem;
}
button { cursor: pointer; }
main { padding: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td {
  text-align: left; padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--line); vertical-align: top;
}
th[data-sort] { cursor: pointer; user-select: none; }
th[data-sort]:hover { color: var(--accent); }
tbody tr { cursor: pointer; }
tbody tr:hover { background: var(--panel); }
.muted { color: var(--muted); }
.desc { color: var(--muted); font-size: 0.85rem; max-width: 28rem; }
.desc .last { color: var(--fg); }
.badge { display: inline-block; padding: 0 0.4rem; border-radius: 4px;
  font-size: 0.75rem; border: 1px solid var(--line); margin-right: 0.25rem; }
.badge.clean { color: #7bd88f; }
.badge.interrupted { color: #e6a23c; }
.badge.error { color: #f56c6c; }
.badge.unknown { color: var(--muted); }
.bar { background: var(--line); border-radius: 4px; height: 8px; width: 90px; }
.bar > span { display: block; height: 100%; border-radius: 4px; background: var(--accent); }
.bar.high > span { background: var(--error); }

/* detail view */
#detail-view { max-width: 56rem; margin: 0 auto; }
#detail-header { margin: 0.5rem 0 1rem; color: var(--muted); }
.entry { border: 1px solid var(--line); border-radius: 8px;
  margin: 0.6rem 0; padding: 0.5rem 0.75rem; background: var(--panel); }
.entry.user { border-left: 3px solid var(--accent); }
.entry.assistant { border-left: 3px solid #7bd88f; }
.entry.system { border-left: 3px solid var(--muted); opacity: 0.85; }
.entry.sidechain { opacity: 0.7; margin-left: 1.5rem; }
.entry .role { font-size: 0.75rem; text-transform: uppercase; color: var(--muted); }
.entry pre { white-space: pre-wrap; word-break: break-word; margin: 0.3rem 0 0; }
details summary { cursor: pointer; color: var(--muted); }
```

Note: remove the stray space in `--clean: #4 caf50;` — set it to `#4caf50`. (Listed here so the implementer fixes it; the color is otherwise unused and harmless.)

- [ ] **Step 3: Create `static/app.js`**

```javascript
let state = { sessions: [], sort: "last_activity", dir: -1, q: "", project: "" };

const $ = (sel) => document.querySelector(sel);

async function fetchSessions(refresh = false) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.project) params.set("project", state.project);
  if (refresh) params.set("refresh", "true");
  const resp = await fetch("/api/sessions?" + params.toString());
  const data = await resp.json();
  state.sessions = data.sessions;
  populateProjects(data.projects);
  render();
}

function populateProjects(projects) {
  const sel = $("#project");
  if (sel.options.length > 1) return; // already populated
  for (const p of projects) {
    const o = document.createElement("option");
    o.value = p; o.textContent = p;
    sel.appendChild(o);
  }
}

function sortSessions() {
  const { sort, dir } = state;
  return [...state.sessions].sort((a, b) => {
    const av = a[sort] ?? "", bv = b[sort] ?? "";
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
}

function badge(outcome) {
  return `<span class="badge ${outcome}">${outcome}</span>`;
}

function recency(ts) {
  if (!ts) return "—";
  const d = new Date(ts), now = new Date();
  const days = (now - d) / 86400000;
  if (days < 1) return "today";
  if (days < 7) return "this week";
  if (days < 31) return "this month";
  return d.toISOString().slice(0, 10);
}

function sizeBucket(n) {
  if (n <= 10) return "S";
  if (n <= 60) return "M";
  return "L";
}

function ctxCell(s) {
  if (s.context_pct == null) return '<span class="muted">—</span>';
  const high = s.context_pct >= 70 ? " high" : "";
  const k = Math.round(s.context_tokens / 1000);
  return `<div class="bar${high}"><span style="width:${Math.min(100, s.context_pct)}%"></span></div>
          <span class="muted">${s.context_pct}% · ${k}k</span>`;
}

function escapeHtml(str) {
  return (str ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function render() {
  const rows = sortSessions().map((s) => {
    const compact = s.compacted ? " ⟳" : "";
    return `<tr data-id="${s.session_id}">
      <td>${escapeHtml(s.title)}</td>
      <td class="muted">${escapeHtml(s.cwd || "—")}<br><small>${escapeHtml(s.git_branch || "")}</small></td>
      <td class="desc">${escapeHtml(s.first_prompt || "")}
        <div class="last">${escapeHtml(s.last_prompt || "")}</div></td>
      <td>${badge(s.outcome)}<br><small class="muted">${recency(s.last_activity)} · ${sizeBucket(s.message_count)}${compact}</small></td>
      <td>${ctxCell(s)}</td>
      <td class="muted">${recency(s.last_activity)}</td>
    </tr>`;
  }).join("");
  $("#rows").innerHTML = rows;
  $("#count").textContent = `${state.sessions.length} sessions`;
  for (const tr of document.querySelectorAll("#rows tr")) {
    tr.addEventListener("click", () => showDetail(tr.dataset.id));
  }
}

async function showDetail(id) {
  const resp = await fetch("/api/sessions/" + encodeURIComponent(id));
  if (!resp.ok) { alert("Could not load session"); return; }
  const tr = await resp.json();
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>`;
  $("#entries").innerHTML = tr.entries.map(renderEntry).join("");
  $("#copyid").addEventListener("click", () => navigator.clipboard.writeText(tr.session_id));
  $("#list-view").hidden = true;
  $("#detail-view").hidden = false;
  window.scrollTo(0, 0);
}

function renderEntry(e) {
  const cls = `entry ${e.role}${e.is_sidechain ? " sidechain" : ""}`;
  const label = e.kind === "tool_use" ? `tool: ${escapeHtml(e.tool_name || "")}`
              : e.kind === "tool_result" ? "tool result"
              : e.role;
  const body = `<pre>${escapeHtml(e.content)}</pre>`;
  if (e.kind === "thinking" || e.kind === "tool_use" || e.kind === "tool_result") {
    return `<div class="${cls}"><div class="role">${label}</div>
      <details><summary>${e.kind}</summary>${body}</details></div>`;
  }
  return `<div class="${cls}"><div class="role">${label}</div>${body}</div>`;
}

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function init() {
  $("#search").addEventListener("input", debounce((e) => {
    state.q = e.target.value; fetchSessions();
  }, 250));
  $("#project").addEventListener("change", (e) => {
    state.project = e.target.value; fetchSessions();
  });
  $("#rescan").addEventListener("click", () => fetchSessions(true));
  $("#back").addEventListener("click", () => {
    $("#detail-view").hidden = true; $("#list-view").hidden = false;
  });
  for (const th of document.querySelectorAll("th[data-sort]")) {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.dir = state.sort === key ? -state.dir : -1;
      state.sort = key;
      render();
    });
  }
  fetchSessions();
}

init();
```

- [ ] **Step 4: Create `run.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8800 "$@"
```

Then: `chmod +x run.sh`

- [ ] **Step 5: Manual verification**

Run: `./run.sh` (in the background), then:
```bash
curl -s http://127.0.0.1:8800/api/sessions | python3 -c "import sys,json; d=json.load(sys.stdin); print('sessions:', len(d['sessions']), 'projects:', len(d['projects'])); print('top:', d['sessions'][0]['title'], d['sessions'][0]['outcome'], d['sessions'][0]['context_pct'])"
```
Expected: a non-zero session count (~308), a project list, and a plausible top (most-recent) session with an outcome and context %. Also `curl -s http://127.0.0.1:8800/ | head -1` should return the HTML doctype. Stop the server afterward.

- [ ] **Step 6: Commit**

```bash
git add static/ run.sh
git commit -m "feat: table + transcript frontend and launcher"
```

---

### Task 11: Integration check against real logs + README

**Files:**
- Create: `tests/test_integration.py`
- Create: `README.md`

- [ ] **Step 1: Write an integration test (skips if no real logs)**

```python
# tests/test_integration.py
from pathlib import Path
import pytest
from app import indexer, parser

ROOT = Path.home() / ".claude" / "projects"


@pytest.mark.skipif(not ROOT.exists(), reason="no real Claude logs present")
def test_real_index_builds(tmp_path):
    sessions = indexer.build_index(ROOT, tmp_path / "cache.json")
    assert len(sessions) > 0
    # newest first
    acts = [s.last_activity or "" for s in sessions]
    assert acts == sorted(acts, reverse=True)
    # every session has a title and valid outcome
    valid = {"clean", "interrupted", "error", "unknown"}
    for s in sessions:
        assert s.title
        assert s.outcome in valid


@pytest.mark.skipif(not ROOT.exists(), reason="no real Claude logs present")
def test_real_transcript_parses(tmp_path):
    sessions = indexer.build_index(ROOT, tmp_path / "cache.json")
    path = indexer.find_session_path(ROOT, sessions[0].session_id)
    assert path is not None
    tr = parser.parse_transcript(path)
    assert tr.session_id == sessions[0].session_id
```

- [ ] **Step 2: Run the integration test**

Run: `.venv/bin/python -m pytest tests/test_integration.py -v`
Expected: PASS (2 passed) against the real ~308 sessions.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green.

- [ ] **Step 4: Write `README.md`**

```markdown
# Claude Session Browser

A local web page to browse Claude Code session logs from `~/.claude/projects/`.

## Run

```bash
uv venv && uv pip install -e ".[dev]"
./run.sh
```

Open http://127.0.0.1:8800.

## What it shows

A sortable, searchable table of every Claude Code session (newest first):
title, project, first/last prompt, state (clean/interrupted/error, recency,
size, compacted), and context-window usage. Click a row for a read-only
transcript. Use **Rescan** to pick up new sessions.

## Tests

```bash
.venv/bin/python -m pytest
```
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "test: integration against real logs; add README"
```

---

## Self-Review

**Spec coverage:**
- Single-location scan, lossy folder names → read `cwd` ✓ (indexer Task 6)
- Title `custom-title → ai-title → id` ✓ (Task 6)
- Description first + last prompt, `last-prompt` preferred for last ✓ (Task 6)
- Context usage input-side, latest message, 200k↔1M ✓ (Tasks 2, 6)
- State badges: outcome / recency / size / compacted ✓ (Task 6 outcome+compacted; recency+size computed in frontend Task 10)
- Sidechain exclusion from index ✓ (Task 6)
- Cache keyed by mtime+size, rescan/force ✓ (Task 7)
- Lazy transcript parse, thinking/tool collapsible, compact-summary as system note, sidechain dimmed ✓ (Tasks 8, 10)
- API: list (q, project, refresh), transcript, 404, static ✓ (Task 9)
- Frontend: sortable columns, project filter, search, transcript view, copy id, back ✓ (Task 10)
- Error handling: malformed lines skipped+counted, empty file, missing fields fallback, traversal rejection ✓ (Tasks 3, 6, 7, 9)
- Testing: parser fixtures, index/cache, token math, API smoke, integration ✓
- `run.sh`, project layout, README ✓

**Placeholder scan:** No TBD/TODO. The one intentional note is the CSS typo fix (`--clean`) called out for the implementer.

**Type consistency:** `SessionIndex`, `TranscriptEntry`, `Transcript` field names are used identically across indexer, parser, main, and frontend (`session_id`, `context_pct`, `context_tokens`, `outcome`, `is_sidechain`, `first_prompt`, `last_prompt`). `build_index(root, cache_path, force=)`, `find_session_path(root, session_id)`, `index_file(path)`, `parse_transcript(path)`, `compute_outcome(convo, interrupted_flag)` signatures are consistent between definitions (Tasks 6–8) and call sites (Task 9, tests).

No gaps found.
