import json

import pytest


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
    (root / "p" / "sess2.jsonl").write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-04-01T00:00:00Z",
                "cwd": "/home/mario/projects/demo",
                "message": {"role": "user", "content": "yo"},
            }
        )
        + "\n"
    )


def test_list_includes_bookmarked_false_initially(client):
    data = client.get("/api/v1/sessions").json()
    assert all(s["bookmarked"] is False for s in data["sessions"])


def test_bookmark_toggles_and_persists(client, settings):
    bfile = settings.bookmarks_path
    resp = client.post("/api/v1/sessions/sess1/bookmark")
    assert resp.status_code == 200
    assert resp.json() == {"bookmarked": True}
    assert "sess1" in json.loads(bfile.read_text())
    assert client.post("/api/v1/sessions/sess1/bookmark").json() == {"bookmarked": False}
    assert json.loads(bfile.read_text()) == []


def test_list_reflects_bookmark(client):
    client.post("/api/v1/sessions/sess1/bookmark")
    data = client.get("/api/v1/sessions").json()
    by_id = {s["session_id"]: s["bookmarked"] for s in data["sessions"]}
    assert by_id["sess1"] is True
    assert by_id["sess2"] is False


def test_bookmarked_filter(client):
    client.post("/api/v1/sessions/sess1/bookmark")
    data = client.get("/api/v1/sessions?bookmarked=true").json()
    assert [s["session_id"] for s in data["sessions"]] == ["sess1"]


def test_bookmark_missing_session_404(client):
    assert client.post("/api/v1/sessions/missing/bookmark").status_code == 404
