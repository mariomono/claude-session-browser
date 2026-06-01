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
    bookmarked: bool = False
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
