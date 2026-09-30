"""Parse a single session file into a render-ready transcript."""

import json
import threading
from collections import OrderedDict
from pathlib import Path

from app.schemas.session import Transcript, TranscriptEntry
from app.services import tokens
from app.services.jsonl import read_records
from app.services.text import message_text, truncate

# Parsed transcripts kept for repeat opens; a large session's transcript is tens of MB in memory.
_CACHE_SIZE = 8
_cache: OrderedDict[tuple[str, int, int], Transcript] = OrderedDict()  # (path, mtime_ns, size) -> transcript
_cache_lock = threading.Lock()
_path_locks: dict[str, threading.Lock] = {}


def _stringify(data: object) -> str:
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
                entries.append(
                    TranscriptEntry(
                        role="system", kind="system_note", content=truncate(content, 500), timestamp=r.get("timestamp")
                    )
                )
            continue
        if t not in ("user", "assistant"):
            continue

        cwd = cwd or r.get("cwd")
        ts = r.get("timestamp")
        sc = bool(r.get("isSidechain"))
        msg = r.get("message")
        if not isinstance(msg, dict):
            msg = {}

        if t == "user":
            if r.get("isCompactSummary"):
                entries.append(
                    TranscriptEntry(
                        role="system",
                        kind="system_note",
                        content="[compaction summary] " + truncate(message_text(msg), 500),
                        timestamp=ts,
                        is_sidechain=sc,
                    )
                )
                continue
            content = msg.get("content")
            handled = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        out = block.get("content")
                        text = out if isinstance(out, str) else message_text({"content": out})
                        entries.append(
                            TranscriptEntry(
                                role="user",
                                kind="tool_result",
                                content=truncate(text or "", 2000),
                                timestamp=ts,
                                is_sidechain=sc,
                            )
                        )
                        handled = True
            if not handled:
                txt = message_text(msg)
                if txt.strip():
                    entries.append(
                        TranscriptEntry(role="user", kind="text", content=txt, timestamp=ts, is_sidechain=sc)
                    )
        else:  # assistant
            model = msg.get("model")
            if model and model != "<synthetic>":
                last_model = model
                if msg.get("usage"):
                    last_usage = msg["usage"]
            content = msg.get("content")
            if isinstance(content, str):
                if content.strip():
                    entries.append(
                        TranscriptEntry(role="assistant", kind="text", content=content, timestamp=ts, is_sidechain=sc)
                    )
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    bt = block.get("type")
                    if bt == "text" and (block.get("text") or "").strip():
                        entries.append(
                            TranscriptEntry(
                                role="assistant", kind="text", content=block["text"], timestamp=ts, is_sidechain=sc
                            )
                        )
                    elif bt == "thinking" and (block.get("thinking") or "").strip():
                        entries.append(
                            TranscriptEntry(
                                role="assistant",
                                kind="thinking",
                                content=block["thinking"],
                                timestamp=ts,
                                is_sidechain=sc,
                            )
                        )
                    elif bt == "tool_use":
                        entries.append(
                            TranscriptEntry(
                                role="assistant",
                                kind="tool_use",
                                tool_name=block.get("name"),
                                content=truncate(_stringify(block.get("input")), 2000),
                                timestamp=ts,
                                is_sidechain=sc,
                            )
                        )

    context_tokens = tokens.context_fill(last_usage) if last_usage else None
    win = tokens.window_size(context_tokens) if context_tokens is not None else None
    pct = tokens.context_pct(context_tokens, win) if context_tokens is not None and win is not None else None

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


def load_transcript(path: Path) -> Transcript:
    """Parse a session file, reusing the last parse while its mtime and size are unchanged.

    The returned transcript is shared between callers and must not be modified. Concurrent
    calls for the same changed file parse it once.
    """
    key_path = str(path)
    with _cache_lock:
        lock = _path_locks.setdefault(key_path, threading.Lock())
    with lock:
        stat = path.stat()
        key = (key_path, stat.st_mtime_ns, stat.st_size)
        with _cache_lock:
            cached = _cache.get(key)
            if cached is not None:
                _cache.move_to_end(key)
                return cached
        transcript = parse_transcript(path)
        with _cache_lock:
            for stale in [k for k in _cache if k[0] == key_path]:
                del _cache[stale]  # superseded by this newer parse of the same file
            _cache[key] = transcript
            while len(_cache) > _CACHE_SIZE:
                evicted, _ = _cache.popitem(last=False)
                # One cache entry per path, so the evicted path's lock is done with;
                # drop it so the lock dict can't grow without bound.
                _path_locks.pop(evicted[0], None)
    return transcript
