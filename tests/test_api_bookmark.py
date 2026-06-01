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
    (root / "p" / "sess2.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-04-01T00:00:00Z",
                    "cwd": "/home/mario/projects/demo",
                    "message": {"role": "user", "content": "yo"}}) + "\n")
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(main, "BOOKMARKS", tmp_path / "bookmarks.json")
    return TestClient(main.app), tmp_path / "bookmarks.json"


def test_list_includes_bookmarked_false_initially(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    data = client.get("/api/sessions").json()
    assert all(s["bookmarked"] is False for s in data["sessions"])


def test_bookmark_toggles_and_persists(tmp_path, monkeypatch):
    client, bfile = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/bookmark")
    assert resp.status_code == 200
    assert resp.json() == {"bookmarked": True}
    assert "sess1" in json.loads(bfile.read_text())
    assert client.post("/api/sessions/sess1/bookmark").json() == {"bookmarked": False}
    assert json.loads(bfile.read_text()) == []


def test_list_reflects_bookmark(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    client.post("/api/sessions/sess1/bookmark")
    data = client.get("/api/sessions").json()
    by_id = {s["session_id"]: s["bookmarked"] for s in data["sessions"]}
    assert by_id["sess1"] is True
    assert by_id["sess2"] is False


def test_bookmarked_filter(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    client.post("/api/sessions/sess1/bookmark")
    data = client.get("/api/sessions?bookmarked=true").json()
    assert [s["session_id"] for s in data["sessions"]] == ["sess1"]


def test_bookmark_missing_session_404(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/missing/bookmark").status_code == 404
