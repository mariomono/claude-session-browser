"""FastAPI app: session index API + transcript API + static frontend."""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, indexer, launcher, parser

ROOT = indexer.default_root()
_BASE = Path(__file__).resolve().parent.parent
CACHE = _BASE / "cache.json"
STATIC = _BASE / "static"
CONFIG = config.load(_BASE / "config.json")

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


@app.post("/api/sessions/{session_id}/resume")
def resume_session(session_id: str,
                   mode: str = Query("continue")):
    if mode not in ("continue", "fork"):
        raise HTTPException(status_code=400, detail="mode must be continue or fork")
    path = indexer.find_session_path(ROOT, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    cwd = indexer.session_cwd(path) or str(Path.home())
    return launcher.resume_session(session_id, cwd, mode, CONFIG,
                                   spawn=launcher._default_spawn)


@app.get("/")
def index_page():
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
