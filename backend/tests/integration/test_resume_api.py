import json
import os
import threading
import time

import pytest

from app.services import launch_queue, launcher


@pytest.fixture(autouse=True)
def _seed(settings):
    root = settings.claude_projects_dir
    (root / "p").mkdir()
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-05-01T00:00:00Z",
                "cwd": "/home/mario/projects/demo",
                "message": {"role": "user", "content": "hi"},
            }
        )
        + "\n"
    )


@pytest.fixture
def spawned(monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "default_spawn", lambda c: calls.append(c))
    return calls


def test_resume_continue(client, spawned):
    resp = client.post("/api/v1/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "claude --resume sess1" in data["command"]
    assert "/home/mario/projects/demo" in data["command"]
    assert spawned and spawned[0] == data["command"]


def test_resume_fork(client, spawned):
    resp = client.post("/api/v1/sessions/sess1/resume?mode=fork")
    assert resp.status_code == 200
    assert "claude --resume sess1 --fork-session" in resp.json()["command"]


def test_resume_bad_mode(client, spawned):
    assert client.post("/api/v1/sessions/sess1/resume?mode=nonsense").status_code == 400


def test_resume_missing_session(client, spawned):
    assert client.post("/api/v1/sessions/missing/resume").status_code == 404


def test_resume_spawn_failure_returns_ok_false(client, monkeypatch):
    def boom(cmd):
        raise FileNotFoundError("no cmd.exe")

    monkeypatch.setattr(launcher, "default_spawn", boom)
    resp = client.post("/api/v1/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "no cmd.exe" in data["error"]


def test_resume_uses_launch_config_from_data_dir(client, settings, spawned):
    settings.data_dir.mkdir()
    settings.launch_config_path.write_text(json.dumps({"distro": "Debian", "launch": ["echo", "{distro}", "{claude}"]}))
    resp = client.post("/api/v1/sessions/sess1/resume")
    assert resp.json()["command"] == ["echo", "Debian", "claude --resume sess1"]


@pytest.fixture
def queue(settings):
    paths = launch_queue.QueuePaths(settings.launch_queue_dir)
    paths.requests.mkdir(parents=True)
    paths.results.mkdir()
    return paths


def _answer_first_request(paths, result):
    """Play the host agent: answer the first request that appears with result."""

    def _serve():
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            for req in paths.requests.glob("*.json"):
                received.append(json.loads(req.read_text()))
                launch_queue.write_json_atomic(paths.results / req.name, result)
                req.unlink()
                return
            time.sleep(0.02)

    received: list[dict] = []
    thread = threading.Thread(target=_serve)
    thread.start()
    return thread, received


def test_resume_with_live_agent_returns_agent_result(client, queue, spawned):
    queue.heartbeat.touch()
    agent_result = {"ok": True, "command": ["wt.exe", "claude --resume sess1"]}
    thread, received = _answer_first_request(queue, agent_result)
    resp = client.post("/api/v1/sessions/sess1/resume?mode=fork")
    thread.join()
    assert resp.status_code == 200
    assert resp.json() == {**agent_result, "via": "agent"}
    assert received[0]["session_id"] == "sess1"
    assert received[0]["cwd"] == "/home/mario/projects/demo"
    assert received[0]["mode"] == "fork"
    assert "created_at" in received[0]
    assert spawned == []  # the backend itself spawned nothing
    assert list(queue.results.iterdir()) == []  # the result was consumed


def test_resume_with_silent_agent_times_out(client, queue, spawned, monkeypatch):
    monkeypatch.setattr(launch_queue, "RESULT_TIMEOUT_SECONDS", 0.3)
    queue.heartbeat.touch()
    data = client.post("/api/v1/sessions/sess1/resume").json()
    assert data["ok"] is False
    assert data["error"] == "launch agent did not respond"
    assert "claude --resume sess1" in data["command"]
    assert spawned == []
    assert list(queue.requests.glob("*.json")) == []  # the request was withdrawn


def test_resume_with_stale_heartbeat_spawns_directly(client, queue, spawned):
    queue.heartbeat.touch()
    stale = time.time() - 60
    os.utime(queue.heartbeat, (stale, stale))
    data = client.post("/api/v1/sessions/sess1/resume").json()
    assert data["ok"] is True
    assert "via" not in data
    assert spawned == [data["command"]]
    assert list(queue.requests.glob("*.json")) == []
