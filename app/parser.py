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
        msg = r.get("message")
        if not isinstance(msg, dict):
            msg = {}

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
