import json
import importlib
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps({"type": "ai-title", "aiTitle": "Hello World"}) + "\n"
        + json.dumps({"type": "user", "timestamp": "2026-05-01T00:00:00Z",
                      "cwd": "/home/mario/projects/demo",
                      "message": {"role": "user", "content": "do the thing"}}) + "\n"
        + json.dumps({"type": "assistant", "timestamp": "2026-05-01T00:01:00Z",
                      "cwd": "/home/mario/projects/demo",
                      "message": {"model": "claude-opus-4-8", "stop_reason": "end_turn",
                                  "usage": {"input_tokens": 1, "cache_read_input_tokens": 100,
                                            "cache_creation_input_tokens": 0},
                                  "content": [{"type": "text", "text": "done"}]}}) + "\n"
    )
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    return TestClient(main.app)


def test_list_sessions(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"][0]["title"] == "Hello World"
    assert data["sessions"][0]["context_tokens"] == 101
    assert "/home/mario/projects/demo" in data["projects"]


def test_search_filters(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    assert len(client.get("/api/sessions?q=hello").json()["sessions"]) == 1
    assert len(client.get("/api/sessions?q=nomatch").json()["sessions"]) == 0


def test_project_filter(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    url = "/api/sessions?project=/home/mario/projects/demo"
    assert len(client.get(url).json()["sessions"]) == 1
    assert len(client.get("/api/sessions?project=/nope").json()["sessions"]) == 0


def test_get_transcript(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    resp = client.get("/api/sessions/sess1")
    assert resp.status_code == 200
    tr = resp.json()
    assert tr["title"] == "Hello World"
    assert any(e["kind"] == "text" and e["role"] == "user" for e in tr["entries"])


def test_get_transcript_404(tmp_path, monkeypatch):
    client = _make_app(tmp_path, monkeypatch)
    assert client.get("/api/sessions/missing").status_code == 404
