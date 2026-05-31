import json
from app import indexer


def _user(text_str, ts):
    return {"type": "user", "timestamp": ts,
            "cwd": "/home/mario/projects/demo",
            "message": {"role": "user", "content": text_str}}


def test_build_index_sorts_newest_first(tmp_path):
    root = tmp_path / "projects"
    (root / "p1").mkdir(parents=True)
    (root / "p2").mkdir(parents=True)
    (root / "p1" / "old.jsonl").write_text(
        json.dumps(_user("old", "2026-01-01T00:00:00Z")) + "\n")
    (root / "p2" / "new.jsonl").write_text(
        json.dumps(_user("new", "2026-05-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"
    sessions = indexer.build_index(root, cache)
    assert [s.session_id for s in sessions] == ["new", "old"]
    assert cache.exists()


def test_build_index_uses_cache_until_mtime_changes(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps(_user("hello", "2026-01-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"

    indexer.build_index(root, cache)
    raw = json.loads(cache.read_text())
    # tamper the cached title to prove the cache is reused (no re-parse)
    key = next(iter(raw))
    raw[key]["title"] = "FROM_CACHE"
    cache.write_text(json.dumps(raw))

    again = indexer.build_index(root, cache)
    assert again[0].title == "FROM_CACHE"   # served from cache, not re-parsed

    # changing the file invalidates the cache entry
    f.write_text(json.dumps(_user("changed", "2026-02-01T00:00:00Z")) + "\n")
    refreshed = indexer.build_index(root, cache)
    assert refreshed[0].title != "FROM_CACHE"


def test_build_index_force_ignores_cache(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps(_user("hello", "2026-01-01T00:00:00Z")) + "\n")
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    raw = json.loads(cache.read_text())
    key = next(iter(raw))
    raw[key]["title"] = "FROM_CACHE"
    cache.write_text(json.dumps(raw))
    forced = indexer.build_index(root, cache, force=True)
    assert forced[0].title != "FROM_CACHE"


def test_find_session_path(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "abc123.jsonl").write_text("{}\n")
    assert indexer.find_session_path(root, "abc123").name == "abc123.jsonl"
    assert indexer.find_session_path(root, "missing") is None


def test_find_session_path_rejects_traversal(tmp_path):
    root = tmp_path / "projects"
    root.mkdir(parents=True)
    assert indexer.find_session_path(root, "../../etc/passwd") is None


def test_session_cwd_returns_first_cwd(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(
        json.dumps({"type": "ai-title", "aiTitle": "x"}) + "\n"
        + json.dumps({"type": "user", "cwd": "/home/mario/projects/demo",
                      "message": {"role": "user", "content": "hi"}}) + "\n")
    assert indexer.session_cwd(f) == "/home/mario/projects/demo"


def test_session_cwd_none_when_absent(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps({"type": "ai-title", "aiTitle": "x"}) + "\n")
    assert indexer.session_cwd(f) is None
