"""Host-side launch agent: opens the resume terminals the containerized backend asks for.

A container cannot open a terminal on the host, so the backend drops launch requests into
<data_dir>/launch/requests/ and this agent, running natively on the host, spawns them.
Run it from the repo root so the default data dir (./data) is the one mounted into the container:

    uv run --project backend python -m app.services.launch_agent
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.services import indexer, launch_config, launcher, terminals
from app.services.launch_queue import QueuePaths, write_json_atomic

POLL_SECONDS = 0.3
HEARTBEAT_SECONDS = 2.0
RESULT_MAX_AGE_SECONDS = 3600.0
CLEANUP_SECONDS = 60.0

log = logging.getLogger("launch_agent")


class AlreadyRunning(Exception):
    def __init__(self, pid: int, pidfile: Path) -> None:
        super().__init__(f"launch agent already running (pid {pid}); if it is not, delete {pidfile}")
        self.pid = pid


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = getattr(ctypes, "windll").kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_pidfile(pidfile: Path) -> None:
    """Claim the pidfile for this process, or raise AlreadyRunning if a live agent holds it."""
    try:
        pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        pid = 0
    if pid != os.getpid() and pid_alive(pid):
        raise AlreadyRunning(pid, pidfile)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(f"{os.getpid()}\n")


def release(paths: QueuePaths) -> None:
    """Remove the heartbeat, and the pidfile if it is still ours."""
    paths.heartbeat.unlink(missing_ok=True)
    try:
        if int(paths.pidfile.read_text().strip()) == os.getpid():
            paths.pidfile.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def parse_request(data: Any) -> tuple[str, str, str]:
    """Validate a request body; returns (session_id, cwd, mode) or raises ValueError.

    Re-checked here even though the backend validated it: this process runs commands on the host.
    """
    if not isinstance(data, dict):
        raise ValueError("request is not an object")
    session_id, cwd, mode = data.get("session_id"), data.get("cwd"), data.get("mode")
    if not isinstance(session_id, str) or not indexer.is_valid_session_id(session_id):
        raise ValueError("invalid session_id")
    if not isinstance(cwd, str) or not cwd or "\0" in cwd:
        raise ValueError("invalid cwd")
    if mode not in ("continue", "fork"):
        raise ValueError("invalid mode")
    return session_id, cwd, mode


def process_request(
    request_path: Path,
    paths: QueuePaths,
    config_path: Path,
    spawn: launcher.Spawn = launcher.default_spawn,
    which: terminals.Which | None = None,
) -> dict[str, Any] | None:
    """Launch one request, write its result and delete the request.

    Returns the result, or None if the request vanished first (the backend withdrew it).
    """
    request_id = request_path.stem
    try:
        raw = request_path.read_text()
    except FileNotFoundError:
        return None
    try:
        session_id, cwd, mode = parse_request(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        result: dict[str, Any] = {"ok": False, "command": [], "error": f"invalid launch request: {exc}"}
    else:
        config = launch_config.load(config_path)
        template = terminals.select_template(config, which=which)
        if template is None:
            result = {
                "ok": False,
                "command": launcher.build_command(config.launch, config.distro, cwd, session_id, mode),
                "error": "no supported terminal found on the host",
            }
        else:
            result = launcher.resume_session(session_id, cwd, mode, replace(config, launch=template), spawn=spawn)
    write_json_atomic(paths.results / f"{request_id}.json", result)
    request_path.unlink(missing_ok=True)
    if result["ok"]:
        log.info("launched %s: %s", request_id, result["command"])
    else:
        log.info("failed %s: %s", request_id, result["error"])
    return result


def cleanup_results(results_dir: Path, max_age: float = RESULT_MAX_AGE_SECONDS) -> int:
    """Delete result files nobody collected within max_age seconds; returns how many."""
    cutoff = time.time() - max_age
    removed = 0
    for path in results_dir.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        log.info("removed %d stale result(s)", removed)
    return removed


def run(
    paths: QueuePaths,
    config_path: Path,
    stop: threading.Event,
    spawn: launcher.Spawn = launcher.default_spawn,
    which: terminals.Which | None = None,
) -> None:
    """Serve requests until stop is set."""
    paths.requests.mkdir(parents=True, exist_ok=True)
    paths.results.mkdir(parents=True, exist_ok=True)
    last_heartbeat = last_cleanup = float("-inf")
    while not stop.is_set():
        now = time.monotonic()
        if now - last_heartbeat >= HEARTBEAT_SECONDS:
            paths.heartbeat.touch()
            last_heartbeat = now
        if now - last_cleanup >= CLEANUP_SECONDS:
            cleanup_results(paths.results)
            last_cleanup = now
        for request_path in sorted(paths.requests.glob("*.json")):
            try:
                process_request(request_path, paths, config_path, spawn=spawn, which=which)
            except Exception:  # noqa: BLE001 - one bad request must not take the agent down
                log.exception("error processing %s", request_path.name)
                request_path.unlink(missing_ok=True)
        stop.wait(POLL_SECONDS)


def main(settings: Settings | None = None) -> int:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s launch-agent %(message)s")
    settings = settings or get_settings()
    paths = QueuePaths(settings.launch_queue_dir)
    try:
        acquire_pidfile(paths.pidfile)
    except AlreadyRunning as exc:
        log.error("%s", exc)
        return 1

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    platform = terminals.detect_platform()
    config = launch_config.load(settings.launch_config_path)
    if config.launch_overridden:
        log.info("using the launch template from %s", settings.launch_config_path.resolve())
    else:
        found = [t[0] for t in terminals.available_templates(platform)]
        log.info("platform %s, terminals found: %s", platform, ", ".join(found) or "none")
    log.info("started (pid %d), watching %s", os.getpid(), paths.root.resolve())
    try:
        run(paths, settings.launch_config_path, stop)
    finally:
        release(paths)
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
