import json

import pytest


@pytest.fixture(autouse=True)
def _seed(settings):
    root = settings.claude_projects_dir
    (root / "p").mkdir()
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps({"type": "ai-title", "aiTitle": "Hello World"})
        + "\n"
        + json.dumps(
            {
                "type": "user",
                "timestamp": "2026-05-01T00:00:00Z",
                "cwd": "/home/mario/projects/demo",
                "message": {"role": "user", "content": "do the thing"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-05-01T00:01:00Z",
                "cwd": "/home/mario/projects/demo",
                "message": {
                    "model": "claude-opus-4-8",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 1, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
                    "content": [{"type": "text", "text": "done"}],
                },
            }
        )
        + "\n"
    )


def test_list_sessions(client):
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"][0]["title"] == "Hello World"
    assert data["sessions"][0]["context_tokens"] == 101
    assert "/home/mario/projects/demo" in data["projects"]


def test_search_filters(client):
    assert len(client.get("/api/v1/sessions?q=hello").json()["sessions"]) == 1
    assert len(client.get("/api/v1/sessions?q=nomatch").json()["sessions"]) == 0


def test_project_filter(client):
    url = "/api/v1/sessions?project=/home/mario/projects/demo"
    assert len(client.get(url).json()["sessions"]) == 1
    assert len(client.get("/api/v1/sessions?project=/nope").json()["sessions"]) == 0


def test_get_transcript(client):
    resp = client.get("/api/v1/sessions/sess1")
    assert resp.status_code == 200
    tr = resp.json()
    assert tr["title"] == "Hello World"
    assert any(e["kind"] == "text" and e["role"] == "user" for e in tr["entries"])


def test_get_transcript_404(client):
    assert client.get("/api/v1/sessions/missing").status_code == 404


def test_cache_written_to_data_dir(client, settings):
    assert not settings.data_dir.exists()
    client.get("/api/v1/sessions")
    assert settings.cache_path.exists()


def test_get_transcript_deleted_between_lookup_and_read_gives_404(client, monkeypatch):
    def _vanished(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr("app.services.parser.load_transcript", _vanished)
    resp = client.get("/api/v1/sessions/sess1")
    assert resp.status_code == 404
