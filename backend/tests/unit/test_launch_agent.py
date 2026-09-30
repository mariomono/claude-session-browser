import json
import os
import subprocess
import sys
import threading
import time

import pytest

from app.services import launch_agent, launch_config, terminals
from app.services.launch_queue import QueuePaths


@pytest.fixture(autouse=True)
def _on_wsl(monkeypatch):
    """Detect WSL regardless of the machine running the tests."""
    monkeypatch.setattr(terminals, "detect_platform", lambda *a, **k: "wsl")


@pytest.fixture
def paths(tmp_path):
    p = QueuePaths(tmp_path / "launch")
    p.requests.mkdir(parents=True)
    p.results.mkdir()
    return p


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


@pytest.fixture
def spawned():
    return []


def _request(paths, request_id="r1", **overrides):
    body = {"session_id": "sess1", "cwd": "/home/m/proj", "mode": "continue", "created_at": "x"}
    body.update(overrides)
    path = paths.requests / f"{request_id}.json"
    path.write_text(json.dumps(body))
    return path


def _result(paths, request_id="r1"):
    return json.loads((paths.results / f"{request_id}.json").read_text())


def test_valid_request_spawns_and_writes_result(paths, config_path, spawned):
    req = _request(paths)
    which = lambda name: "/x" if name == "cmd.exe" else None  # noqa: E731
    launch_agent.process_request(req, paths, config_path, spawn=spawned.append, which=which)
    result = _result(paths)
    assert result["ok"] is True
    assert spawned == [result["command"]]
    assert result["command"][0] == "cmd.exe"
    assert "claude --resume sess1" in result["command"]
    assert not req.exists()


def test_config_override_is_used(paths, config_path, spawned):
    config_path.write_text(json.dumps({"launch": ["echo", "{cwd}", "{claude}"]}))
    launch_agent.process_request(_request(paths, mode="fork"), paths, config_path, spawn=spawned.append)
    assert spawned == [["echo", "/home/m/proj", "claude --resume sess1 --fork-session"]]


@pytest.mark.parametrize(
    "overrides",
    [{"session_id": "x; rm -rf ~"}, {"session_id": 5}, {"mode": "evil"}, {"cwd": ""}, {"cwd": None}],
)
def test_invalid_request_fails_without_spawning(paths, config_path, spawned, overrides):
    req = _request(paths, **overrides)
    launch_agent.process_request(req, paths, config_path, spawn=spawned.append, which=lambda n: "/x")
    result = _result(paths)
    assert result["ok"] is False
    assert "invalid launch request" in result["error"]
    assert spawned == []
    assert not req.exists()


def test_malformed_json_fails_without_spawning(paths, config_path, spawned):
    req = paths.requests / "r1.json"
    req.write_text("{ nope")
    launch_agent.process_request(req, paths, config_path, spawn=spawned.append, which=lambda n: "/x")
    assert _result(paths)["ok"] is False
    assert spawned == []


def test_no_terminal_reports_best_guess_command(paths, config_path, spawned):
    launch_agent.process_request(_request(paths), paths, config_path, spawn=spawned.append, which=lambda n: None)
    result = _result(paths)
    assert result["ok"] is False
    assert "no supported terminal" in result["error"]
    assert result["command"][:4] == launch_config.DEFAULT_LAUNCH[:4]
    assert spawned == []


def test_spawn_failure_is_reported(paths, config_path):
    def boom(cmd):
        raise FileNotFoundError("no wt.exe")

    launch_agent.process_request(_request(paths), paths, config_path, spawn=boom, which=lambda n: "/x")
    result = _result(paths)
    assert result["ok"] is False
    assert "no wt.exe" in result["error"]


def test_withdrawn_request_is_skipped(paths, config_path, spawned):
    missing = paths.requests / "gone.json"
    assert launch_agent.process_request(missing, paths, config_path, spawn=spawned.append) is None
    assert not (paths.results / "gone.json").exists()


def test_cleanup_removes_only_stale_results(paths):
    old = paths.results / "old.json"
    new = paths.results / "new.json"
    old.write_text("{}")
    new.write_text("{}")
    two_hours_ago = time.time() - 7200
    os.utime(old, (two_hours_ago, two_hours_ago))
    assert launch_agent.cleanup_results(paths.results) == 1
    assert not old.exists()
    assert new.exists()


def test_pidfile_claimed_when_absent_or_stale(paths):
    launch_agent.acquire_pidfile(paths.pidfile)
    assert paths.pidfile.read_text().strip() == str(os.getpid())
    # A pid of a process that has exited is stale and gets overwritten.
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    paths.pidfile.write_text(str(dead.pid))
    launch_agent.acquire_pidfile(paths.pidfile)
    assert paths.pidfile.read_text().strip() == str(os.getpid())


def test_pidfile_of_live_process_refuses_start(paths):
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        paths.pidfile.write_text(str(other.pid))
        with pytest.raises(launch_agent.AlreadyRunning, match="already running"):
            launch_agent.acquire_pidfile(paths.pidfile)
        assert paths.pidfile.read_text().strip() == str(other.pid)
    finally:
        other.kill()
        other.wait()


def test_release_removes_own_files_only(paths):
    paths.heartbeat.touch()
    paths.pidfile.write_text(str(os.getpid()))
    launch_agent.release(paths)
    assert not paths.heartbeat.exists()
    assert not paths.pidfile.exists()
    paths.pidfile.write_text("999999999")
    launch_agent.release(paths)
    assert paths.pidfile.exists()


def test_run_loop_heartbeats_and_serves_until_stopped(paths, config_path, spawned):
    stop = threading.Event()
    config_path.write_text(json.dumps({"launch": ["echo", "{claude}"]}))
    worker = threading.Thread(
        target=launch_agent.run, args=(paths, config_path, stop), kwargs={"spawn": spawned.append}
    )
    worker.start()
    try:
        _request(paths)
        deadline = time.monotonic() + 3
        while not (paths.results / "r1.json").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert paths.heartbeat.exists()
        assert _result(paths)["ok"] is True
        assert spawned == [["echo", "claude --resume sess1"]]
    finally:
        stop.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
