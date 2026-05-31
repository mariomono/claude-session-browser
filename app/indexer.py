"""Build a lightweight, cached index of all Claude Code sessions."""
import json
import re
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
        if t == "user" and (r.get("isMeta") or r.get("isCompactSummary")):
            continue

        cwd = cwd or r.get("cwd")
        git_branch = git_branch or r.get("gitBranch")
        ts = r.get("timestamp")
        if ts and (last_activity is None or ts > last_activity):
            last_activity = ts
        msg = r.get("message")
        if not isinstance(msg, dict):
            msg = {}

        if t == "user":
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
                usage = msg.get("usage")
                if isinstance(usage, dict) and usage:
                    last_usage = usage

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
