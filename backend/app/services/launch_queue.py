"""File queue between the backend and the host launch agent.

Layout under <data_dir>/launch/:
  requests/<uuid>.json  written by the backend: session_id, cwd, mode, created_at
  results/<uuid>.json   written by the agent: the launcher result (ok, command, error)
  heartbeat             touched by the agent every few seconds while it runs
  agent.pid             the running agent's pid, for single-instance enforcement

Every file is written to a dot-prefixed temp name and renamed into place, so a reader globbing
``*.json`` never sees a half-written file.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# The agent counts as running while its heartbeat is younger than this.
HEARTBEAT_FRESH_SECONDS = 10.0
# How long the backend waits for the agent to answer a request.
RESULT_TIMEOUT_SECONDS = 5.0
RESULT_POLL_SECONDS = 0.1


@dataclass(frozen=True)
class QueuePaths:
    root: Path

    @property
    def requests(self) -> Path:
        return self.root / "requests"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def heartbeat(self) -> Path:
        return self.root / "heartbeat"

    @property
    def pidfile(self) -> Path:
        return self.root / "agent.pid"


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def agent_alive(paths: QueuePaths, max_age: float = HEARTBEAT_FRESH_SECONDS) -> bool:
    """True if the agent's heartbeat file exists and was touched within max_age seconds."""
    try:
        mtime = paths.heartbeat.stat().st_mtime
    except OSError:
        return False
    return time.time() - mtime < max_age


def submit(paths: QueuePaths, session_id: str, cwd: str, mode: str) -> str:
    """Queue a launch request for the agent; returns its request id."""
    request_id = str(uuid.uuid4())
    request = {
        "session_id": session_id,
        "cwd": cwd,
        "mode": mode,
        "created_at": datetime.now(UTC).isoformat(),
    }
    write_json_atomic(paths.requests / f"{request_id}.json", request)
    return request_id


def wait_for_result(
    paths: QueuePaths, request_id: str, timeout: float | None = None, interval: float | None = None
) -> dict[str, Any] | None:
    """Poll for the agent's result and consume it; None on timeout.

    On timeout the request is withdrawn, so a late agent never opens a terminal the user
    already gave up on.
    """
    timeout = RESULT_TIMEOUT_SECONDS if timeout is None else timeout
    interval = RESULT_POLL_SECONDS if interval is None else interval
    result_path = paths.results / f"{request_id}.json"
    deadline = time.monotonic() + timeout
    while True:
        try:
            data = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
        else:
            result_path.unlink(missing_ok=True)
            return data if isinstance(data, dict) else {"ok": False, "error": "launch agent returned an invalid result"}
        if time.monotonic() >= deadline:
            (paths.requests / f"{request_id}.json").unlink(missing_ok=True)
            return None
        time.sleep(interval)


def resume_via_agent(
    paths: QueuePaths, session_id: str, cwd: str, mode: str, fallback_command: list[str]
) -> dict[str, Any]:
    """Hand the launch to the host agent and return its result, marked ``via: "agent"``.

    fallback_command is the best-guess command reported when the agent does not answer,
    for the UI's copy-it-yourself dialog.
    """
    request_id = submit(paths, session_id, cwd, mode)
    result = wait_for_result(paths, request_id)
    if result is None:
        return {"ok": False, "command": fallback_command, "error": "launch agent did not respond", "via": "agent"}
    result.setdefault("command", fallback_command)
    return {**result, "via": "agent"}
