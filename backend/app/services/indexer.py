"""Build a lightweight, cached index of all Claude Code sessions.

The index lives in memory per cache file and is refreshed with a cheap stat scan on each
build. Session files are append-only in normal operation, so a changed file is parsed
incrementally: each entry keeps the byte offset it has consumed plus the running aggregates
the index needs, and only the appended bytes are read. Anything that breaks the append-only
assumption (the file shrank, or the bytes at its start or just before the offset changed)
falls back to a full re-parse. cache.json seeds the memory on cold start and is rewritten
only when an entry changed.
"""

import copy
import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from app.schemas.session import SessionIndex
from app.services import tokens
from app.services.jsonl import iter_chunk_records, iter_records
from app.services.text import is_real_user_prompt, message_text, truncate

# Bump when _ParseState's fields or meaning change; cached states of another version are
# dropped, so their files get one full re-parse.
_STATE_VERSION = 1
# Bytes hashed at the start of a file and just before the parsed offset to detect a rewrite.
_GUARD_BYTES = 4096
# Read size for parsing; bounds memory on the largest files.
_BLOCK_BYTES = 8 * 1024 * 1024


@dataclass
class _ParseState:
    """Running index aggregates over a file's first ``offset`` bytes (always whole lines)."""

    v: int = _STATE_VERSION
    offset: int = 0
    head_len: int = 0
    head_hash: str = ""
    anchor_hash: str = ""  # hash of the (up to) _GUARD_BYTES bytes ending at offset
    ai_title: str | None = None
    custom_title: str | None = None
    last_prompt_field: str | None = None
    compacted: bool = False
    cwd: str | None = None
    git_branch: str | None = None
    last_activity: str | None = None
    first_prompt: str | None = None
    last_prompt: str | None = None
    last_model: str | None = None
    last_usage: dict | None = None
    message_count: int = 0
    interrupted_flag: bool = False
    last_role: str | None = None
    has_assistant: bool = False
    last_assistant_error: bool = False
    last_assistant_stop: object = None
    bad: int = 0

    def feed(self, r: dict | None) -> None:
        """Fold one line into the aggregates; None is an unparsable line."""
        if r is None:
            self.bad += 1
            return
        t = r.get("type")
        if t == "ai-title":
            self.ai_title = r.get("aiTitle") or self.ai_title
            return
        if t == "custom-title":
            self.custom_title = r.get("customTitle") or self.custom_title
            return
        if t == "last-prompt":
            self.last_prompt_field = r.get("lastPrompt") or self.last_prompt_field
            return
        if t == "system":
            if r.get("compactMetadata"):
                self.compacted = True
            return
        if t not in ("user", "assistant"):
            return
        if r.get("isSidechain"):
            return
        if t == "user" and (r.get("isMeta") or r.get("isCompactSummary")):
            return

        self.cwd = self.cwd or r.get("cwd")
        self.git_branch = self.git_branch or r.get("gitBranch")
        ts = r.get("timestamp")
        if ts and (self.last_activity is None or ts > self.last_activity):
            self.last_activity = ts
        raw_msg = r.get("message")
        msg = raw_msg if isinstance(raw_msg, dict) else {}
        self.message_count += 1
        self.last_role = t

        if t == "user":
            if r.get("interruptedMessageId"):
                self.interrupted_flag = True
            if is_real_user_prompt(msg):
                txt = truncate(message_text(msg))
                if txt:
                    if self.first_prompt is None:
                        self.first_prompt = txt
                    self.last_prompt = txt
        else:  # assistant
            self.has_assistant = True
            self.last_assistant_error = bool(r.get("isApiErrorMessage") or msg.get("isApiErrorMessage"))
            self.last_assistant_stop = msg.get("stop_reason")
            model = msg.get("model")
            if model and model != "<synthetic>":
                self.last_model = model
                usage = msg.get("usage")
                if isinstance(usage, dict) and usage:
                    self.last_usage = usage

    def outcome(self) -> str:
        """Classify the session end state: clean | interrupted | error | unknown."""
        if not self.has_assistant:
            return "unknown"
        if self.last_assistant_error:
            return "error"
        if self.interrupted_flag:
            return "interrupted"
        stop = self.last_assistant_stop
        if stop == "tool_use" and self.last_role == "assistant":
            return "interrupted"  # tool call never returned a result
        if stop in ("end_turn", "stop_sequence"):
            return "clean"
        if stop is None:
            return "interrupted"  # never finalized
        return "clean"

    def to_index(self, session_id: str, stat: os.stat_result) -> SessionIndex:
        context_tokens = tokens.context_fill(self.last_usage) if self.last_usage else None
        win = tokens.window_size(context_tokens) if context_tokens is not None else None
        pct = tokens.context_pct(context_tokens, win) if context_tokens is not None and win is not None else None
        return SessionIndex(
            session_id=session_id,
            title=self.custom_title or self.ai_title or session_id,
            first_prompt=self.first_prompt,
            last_prompt=truncate(self.last_prompt_field) if self.last_prompt_field else self.last_prompt,
            cwd=self.cwd,
            git_branch=self.git_branch,
            last_activity=self.last_activity,
            message_count=self.message_count,
            context_tokens=context_tokens,
            context_pct=pct,
            window_size=win,
            model=self.last_model,
            outcome=self.outcome(),
            compacted=self.compacted,
            unparsable_lines=self.bad,
            file_mtime=stat.st_mtime,
            file_size=stat.st_size,
        )

    @classmethod
    def from_json(cls, raw: object) -> "_ParseState | None":
        """Rebuild a persisted state; None if it is missing, of another version or malformed."""
        if not isinstance(raw, dict) or raw.get("v") != _STATE_VERSION or set(raw) != {f.name for f in fields(cls)}:
            return None
        state = cls(**raw)
        ints = (state.offset, state.head_len, state.message_count, state.bad)
        if not all(type(n) is int and n >= 0 for n in ints) or state.head_len > state.offset:
            return None
        if not isinstance(state.head_hash, str) or not isinstance(state.anchor_hash, str):
            return None
        opt_strs = (
            state.ai_title,
            state.custom_title,
            state.last_prompt_field,
            state.cwd,
            state.git_branch,
            state.last_activity,
            state.first_prompt,
            state.last_prompt,
            state.last_model,
            state.last_role,
        )
        if not all(s is None or isinstance(s, str) for s in opt_strs):
            return None
        flags = (state.compacted, state.interrupted_flag, state.has_assistant, state.last_assistant_error)
        if not all(type(b) is bool for b in flags):
            return None
        if state.last_usage is not None and not isinstance(state.last_usage, dict):
            return None
        return state


def _digest(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _read_at(fh: BinaryIO, start: int, length: int) -> bytes:
    fh.seek(start)
    return fh.read(length)


def _can_resume(fh: BinaryIO, size: int, state: _ParseState) -> bool:
    """True if the file still starts with the bytes the state was built from."""
    if state.offset == 0 or state.offset > size:
        return False
    anchor_start = max(0, state.offset - _GUARD_BYTES)
    return (
        _digest(_read_at(fh, 0, state.head_len)) == state.head_hash
        and _digest(_read_at(fh, anchor_start, state.offset - anchor_start)) == state.anchor_hash
    )


def _consume(fh: BinaryIO, state: _ParseState, limit: int) -> bytes:
    """Feed whole lines from the state's offset up to `limit`; return the unterminated remainder."""
    fh.seek(state.offset)
    carry = b""
    remaining = limit - state.offset
    while remaining > 0:
        block = fh.read(min(_BLOCK_BYTES, remaining))
        if not block:
            break
        remaining -= len(block)
        buf = carry + block
        cut = buf.rfind(b"\n") + 1
        if cut:
            for r in iter_chunk_records(buf[:cut]):
                state.feed(r)
            state.offset += cut
        carry = buf[cut:]
    return carry


def _parse(path: Path, prev: _ParseState | None) -> tuple[SessionIndex, _ParseState]:
    """Index a file, resuming from `prev` when the file only grew since it was recorded.

    A resume state that turns out to be unusable mid-parse (however it got that way) must
    never break indexing, so any non-I/O failure falls back to reading from scratch.
    """
    if prev is not None:
        try:
            return _parse_once(path, prev)
        except OSError:
            raise
        except Exception:
            pass
    return _parse_once(path, None)


def _parse_once(path: Path, prev: _ParseState | None) -> tuple[SessionIndex, _ParseState]:
    """One indexing pass over a file, resuming from `prev` when it still anchors.

    The committed state never covers a trailing line without its newline: a writer may be
    mid-append. That line still counts toward the returned index (as a record, or as an
    unparsable line), exactly as a from-scratch read of the file sees it.
    """
    with path.open("rb") as fh:
        stat = os.fstat(fh.fileno())
        if prev is not None and _can_resume(fh, stat.st_size, prev):
            state = copy.copy(prev)
        else:
            state = _ParseState()
        tail = _consume(fh, state, stat.st_size)
        state.head_len = min(state.offset, _GUARD_BYTES)
        state.head_hash = _digest(_read_at(fh, 0, state.head_len))
        anchor_start = max(0, state.offset - _GUARD_BYTES)
        state.anchor_hash = _digest(_read_at(fh, anchor_start, state.offset - anchor_start))
    view = state
    if tail:
        view = copy.copy(state)
        for r in iter_chunk_records(tail):
            view.feed(r)
    return view.to_index(path.stem, stat), state


def index_file(path: Path) -> SessionIndex:
    return _parse(path, None)[0]


_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class _Entry:
    index: SessionIndex
    state: _ParseState | None  # None for an entry seeded from a cache without parse state

    def matches(self, stat: os.stat_result) -> bool:
        return self.index.file_mtime == stat.st_mtime and self.index.file_size == stat.st_size


def _file_sig(path: Path) -> tuple[int, int, int] | None:
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return st.st_ino, st.st_mtime_ns, st.st_size


def load_cache(cache_path: Path) -> dict[str, _Entry]:
    """Read cache.json; unreadable or malformed content (whole file or single entries) is dropped.

    Format: {file path: SessionIndex fields + optional "parse_state"}. An entry without a
    usable parse state still serves its file until the file changes, then gets a full parse.
    """
    try:
        data = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries: dict[str, _Entry] = {}
    for key, raw in data.items():
        if not isinstance(raw, dict):
            continue
        raw = dict(raw)
        raw_state = raw.pop("parse_state", None)
        try:
            index = SessionIndex(**raw)
            state = _ParseState.from_json(raw_state)
        except (ValidationError, TypeError):
            continue
        entries[key] = _Entry(index, state)
    return entries


def save_cache(cache_path: Path, entries: dict[str, _Entry]) -> None:
    """Write cache.json atomically, so a concurrent reader never sees a half-written file."""
    payload = {
        key: {**e.index.model_dump(), "parse_state": asdict(e.state) if e.state else None} for key, e in entries.items()
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(payload))
    os.replace(tmp, cache_path)


@dataclass
class _Store:
    """In-memory index for one cache file. `lock` guards every field; parsing runs outside it."""

    cache_path: Path
    lock: threading.Lock = field(default_factory=threading.Lock)
    entries: dict[str, _Entry] = field(default_factory=dict)
    path_locks: dict[str, threading.Lock] = field(default_factory=dict)
    disk_sig: tuple[int, int, int] | None = None  # cache.json as last read or written
    loaded: bool = False
    dirty: bool = False

    def sync_from_disk(self) -> None:
        """Reload from cache.json when it changed behind our back (or on first use); caller holds lock."""
        sig = _file_sig(self.cache_path)
        if self.loaded and sig == self.disk_sig and sig is not None:
            return
        if sig is None:
            self.loaded = True
            self.dirty = True  # nothing on disk yet: write on this build even if nothing changed
            self.disk_sig = None
            return
        self.entries = load_cache(self.cache_path)
        self.disk_sig = sig
        self.loaded = True
        self.dirty = False

    def path_lock(self, key: str) -> threading.Lock:
        with self.lock:
            return self.path_locks.setdefault(key, threading.Lock())

    def refresh(self, key: str, path: Path, stat: os.stat_result, force: bool) -> _Entry:
        """Re-index one changed file; concurrent callers for the same file parse it once."""
        with self.path_lock(key):
            with self.lock:
                current = self.entries.get(key)
            if current is not None and not force and current.matches(stat):
                return current  # another request re-indexed it while we waited
            prev = None if force or current is None else current.state
            index, state = _parse(path, prev)
            entry = _Entry(index, state)
            with self.lock:
                self.entries[key] = entry
                self.dirty = True
            return entry

    def save_if_dirty(self) -> None:
        """Write cache.json if an entry changed since the last write (or it does not exist yet)."""
        with self.lock:
            if not self.dirty:
                return
            save_cache(self.cache_path, self.entries)
            self.disk_sig = _file_sig(self.cache_path)
            self.dirty = False


_registry_lock = threading.Lock()
_stores: dict[Path, _Store] = {}
_session_paths: dict[Path, dict[str, Path]] = {}  # root -> session id -> file, from the last scan


def _store_for(cache_path: Path) -> _Store:
    with _registry_lock:
        return _stores.setdefault(cache_path, _Store(cache_path))


def build_index(root: Path, cache_path: Path, force: bool = False) -> list[SessionIndex]:
    """Scan root for sessions, re-indexing only files whose mtime or size changed.

    `force` re-parses every file from scratch. The returned objects are copies the caller may modify.
    """
    store = _store_for(cache_path)
    with store.lock:
        store.sync_from_disk()
        known = dict(store.entries)

    seen: dict[str, _Entry] = {}
    by_id: dict[str, Path] = {}
    if root.exists():
        for path in root.glob("*/*.jsonl"):
            key = str(path)
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue  # deleted between the glob and the stat
            entry = known.get(key)
            if force or entry is None or not entry.matches(stat):
                try:
                    entry = store.refresh(key, path, stat, force)
                except FileNotFoundError:
                    continue
            seen[key] = entry
            by_id.setdefault(path.stem, path)

    with store.lock:
        for key in [k for k in store.entries if k not in seen]:
            del store.entries[key]
            store.dirty = True
        # Drop locks for files that no longer exist so they don't accumulate forever.
        # A concurrent refresh holding a pruned lock at worst parses its file twice.
        for key in [k for k in store.path_locks if k not in seen]:
            del store.path_locks[key]
    store.save_if_dirty()
    with _registry_lock:
        _session_paths[root] = by_id

    sessions = [e.index.model_copy() for e in seen.values()]
    sessions.sort(key=lambda s: s.last_activity or "", reverse=True)
    return sessions


def is_valid_session_id(session_id: str) -> bool:
    """True if session_id is id-shaped: safe to use in a file glob and a shell command."""
    return bool(_SESSION_ID_RE.match(session_id))


def find_session_path(root: Path, session_id: str) -> Path | None:
    """Resolve a session id to its file, rejecting anything non-id-shaped.

    Ids seen by the last index build resolve without a directory scan; unknown ids fall back to a glob.
    """
    if not is_valid_session_id(session_id):
        return None
    with _registry_lock:
        known = _session_paths.get(root, {}).get(session_id)
    if known is not None and known.is_file():
        return known
    matches = list(root.glob(f"*/{session_id}.jsonl"))
    if not matches:
        return None
    with _registry_lock:
        _session_paths.setdefault(root, {})[session_id] = matches[0]
    return matches[0]


def session_cwd(path: Path) -> str | None:
    """Return the first cwd recorded in a session file, reading lazily."""
    for r in iter_records(path):
        cwd = r.get("cwd")
        if cwd:
            return cwd
    return None
