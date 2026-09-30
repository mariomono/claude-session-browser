"""Session index, transcript, resume and bookmark endpoints."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import LaunchConfigDep, SettingsDep
from app.schemas.session import Transcript
from app.services import bookmarks, indexer, launcher, parser

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions(
    settings: SettingsDep,
    q: str | None = None,
    project: str | None = None,
    refresh: bool = False,
    bookmarked: bool = False,
) -> dict[str, Any]:
    all_sessions = indexer.build_index(settings.claude_projects_dir, settings.cache_path, force=refresh)
    projects = sorted({s.cwd for s in all_sessions if s.cwd})
    marks = bookmarks.load(settings.bookmarks_path)
    for s in all_sessions:
        s.bookmarked = s.session_id in marks
    sessions = all_sessions
    if project:
        sessions = [s for s in sessions if s.cwd == project]
    if q:
        ql = q.lower()
        sessions = [
            s for s in sessions if any(ql in (v or "").lower() for v in (s.title, s.first_prompt, s.last_prompt))
        ]
    if bookmarked:
        sessions = [s for s in sessions if s.bookmarked]
    return {"sessions": [s.model_dump() for s in sessions], "projects": projects}


@router.get("/{session_id}")
def get_session(session_id: str, settings: SettingsDep) -> Transcript:
    path = indexer.find_session_path(settings.claude_projects_dir, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    return parser.parse_transcript(path)


@router.post("/{session_id}/resume")
def resume_session(
    session_id: str,
    settings: SettingsDep,
    config: LaunchConfigDep,
    mode: str = Query("continue"),
) -> dict[str, Any]:
    # SECURITY: this endpoint spawns a host process (a terminal running claude).
    # The server must only be reachable from localhost and never exposed to a
    # network. The session_id is validated against a strict regex by
    # find_session_path below before it reaches any command.
    if mode not in ("continue", "fork"):
        raise HTTPException(status_code=400, detail="mode must be continue or fork")
    path = indexer.find_session_path(settings.claude_projects_dir, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    cwd = indexer.session_cwd(path) or str(Path.home())
    # Resolved at call time so tests can replace the spawner on the module.
    return launcher.resume_session(session_id, cwd, mode, config, spawn=launcher.default_spawn)


@router.post("/{session_id}/bookmark")
def bookmark_session(session_id: str, settings: SettingsDep) -> dict[str, bool]:
    path = indexer.find_session_path(settings.claude_projects_dir, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    return {"bookmarked": bookmarks.toggle(settings.bookmarks_path, session_id)}
