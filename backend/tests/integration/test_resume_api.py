import json

import pytest

from app.services import launcher


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
