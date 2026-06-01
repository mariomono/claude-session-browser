import json
import importlib
from fastapi.testclient import TestClient


def _make_client(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-05-01T00:00:00Z",
                    "cwd": "/home/mario/projects/demo",
                    "message": {"role": "user", "content": "hi"}}) + "\n")
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    spawned = []
    monkeypatch.setattr(main.launcher, "_default_spawn", lambda c: spawned.append(c))
    return TestClient(main.app), spawned


def test_resume_continue(tmp_path, monkeypatch):
    client, spawned = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "claude --resume sess1" in data["command"]
    assert "/home/mario/projects/demo" in data["command"]
    assert spawned and spawned[0] == data["command"]


def test_resume_fork(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/resume?mode=fork")
    assert resp.status_code == 200
    assert "claude --resume sess1 --fork-session" in resp.json()["command"]


def test_resume_bad_mode(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/sess1/resume?mode=nonsense").status_code == 400


def test_resume_missing_session(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/missing/resume").status_code == 404


def test_resume_spawn_failure_returns_ok_false(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    from app import main

    def boom(cmd):
        raise FileNotFoundError("no cmd.exe")
    monkeypatch.setattr(main.launcher, "_default_spawn", boom)
    resp = client.post("/api/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "no cmd.exe" in data["error"]
