import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.services import indexer


def _user(text_str, ts):
    return {
        "type": "user",
        "timestamp": ts,
        "cwd": "/home/mario/projects/demo",
        "message": {"role": "user", "content": text_str},
    }


def test_build_index_sorts_newest_first(tmp_path):
    root = tmp_path / "projects"
    (root / "p1").mkdir(parents=True)
    (root / "p2").mkdir(parents=True)
    (root / "p1" / "old.jsonl").write_text(json.dumps(_user("old", "2026-01-01T00:00:00Z")) + "\n")
    (root / "p2" / "new.jsonl").write_text(json.dumps(_user("new", "2026-05-01T00:00:00Z")) + "\n")
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
    assert again[0].title == "FROM_CACHE"  # served from cache, not re-parsed

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
    found = indexer.find_session_path(root, "abc123")
    assert found is not None
    assert found.name == "abc123.jsonl"
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
        json.dumps({"type": "ai-title", "aiTitle": "x"})
        + "\n"
        + json.dumps({"type": "user", "cwd": "/home/mario/projects/demo", "message": {"role": "user", "content": "hi"}})
        + "\n"
    )
    assert indexer.session_cwd(f) == "/home/mario/projects/demo"


def test_session_cwd_none_when_absent(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps({"type": "ai-title", "aiTitle": "x"}) + "\n")
    assert indexer.session_cwd(f) is None


def test_build_index_excludes_subagent_transcripts(tmp_path):
    root = tmp_path / "projects"
    (root / "p" / "parent" / "subagents").mkdir(parents=True)
    (root / "p" / "parent.jsonl").write_text(json.dumps(_user("main", "2026-01-01T00:00:00Z")) + "\n")
    (root / "p" / "parent" / "subagents" / "agent-1.jsonl").write_text(
        json.dumps(_user("sub", "2026-01-02T00:00:00Z")) + "\n"
    )
    sessions = indexer.build_index(root, tmp_path / "cache.json")
    assert [s.session_id for s in sessions] == ["parent"]


def test_build_index_creates_missing_cache_dir(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    cache = tmp_path / "data" / "cache.json"
    indexer.build_index(root, cache)
    assert cache.exists()


def _seed_root(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps(_user("hello", "2026-01-01T00:00:00Z")) + "\n")
    return root, f


def _count_calls(monkeypatch, name):
    calls = []
    real = getattr(indexer, name)

    def _spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(indexer, name, _spy)
    return calls


def test_build_index_neither_rereads_nor_rewrites_unchanged_cache(tmp_path, monkeypatch):
    root, _ = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    loads = _count_calls(monkeypatch, "load_cache")
    saves = _count_calls(monkeypatch, "save_cache")
    for _ in range(3):
        indexer.build_index(root, cache)
    assert loads == []
    assert saves == []


def test_build_index_rewrites_cache_only_when_a_file_changed(tmp_path, monkeypatch):
    root, f = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    saves = _count_calls(monkeypatch, "save_cache")
    with f.open("a") as fh:
        fh.write(json.dumps(_user("more", "2026-01-02T00:00:00Z")) + "\n")
    assert indexer.build_index(root, cache)[0].last_prompt == "more"
    assert len(saves) == 1
    assert next(iter(json.loads(cache.read_text()).values()))["last_prompt"] == "more"


def test_build_index_drops_deleted_sessions(tmp_path):
    root, f = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    f.unlink()
    assert indexer.build_index(root, cache) == []
    assert json.loads(cache.read_text()) == {}


def test_build_index_rewrites_cache_deleted_behind_its_back(tmp_path):
    root, _ = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    cache.unlink()
    indexer.build_index(root, cache)
    assert cache.exists()


def test_build_index_returns_copies(tmp_path):
    root, _ = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)[0].bookmarked = True
    assert indexer.build_index(root, cache)[0].bookmarked is False


def test_build_index_accepts_cache_without_parse_state(tmp_path):
    """A cache entry holding only SessionIndex fields serves until its file changes, then is fully re-parsed."""
    root, f = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    stat = f.stat()
    entry = indexer.index_file(f).model_dump() | {"title": "OLD_FORMAT", "file_mtime": stat.st_mtime}
    cache.write_text(json.dumps({str(f): entry}))
    assert indexer.build_index(root, cache)[0].title == "OLD_FORMAT"

    with f.open("a") as fh:
        fh.write(json.dumps(_user("more", "2026-01-02T00:00:00Z")) + "\n")
    refreshed = indexer.build_index(root, cache)[0]
    assert refreshed.model_dump() == indexer.index_file(f).model_dump()


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        b"\xff\xfe not utf-8",
        "[1, 2, 3]",
        '{"a": 1, "b": {"title": 5}, "c": {"session_id": "x"}}',
        None,  # valid index fields with a broken parse_state
    ],
)
def test_build_index_regenerates_from_corrupt_cache(tmp_path, content):
    root, f = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    if content is None:
        entry = indexer.index_file(f).model_dump() | {"parse_state": {"v": 1, "offset": "zero"}}
        content = json.dumps({str(f): entry})
        f.write_text(f.read_text() + json.dumps(_user("more", "2026-01-02T00:00:00Z")) + "\n")
    cache.write_bytes(content if isinstance(content, bytes) else content.encode())
    sessions = indexer.build_index(root, cache)
    assert [s.model_dump() for s in sessions] == [indexer.index_file(f).model_dump()]
    assert str(f) in json.loads(cache.read_text())


def test_concurrent_builds_parse_a_changed_file_once(tmp_path, monkeypatch):
    root, f = _seed_root(tmp_path)
    cache = tmp_path / "cache.json"
    indexer.build_index(root, cache)
    with f.open("a") as fh:
        fh.write(json.dumps(_user("more", "2026-01-02T00:00:00Z")) + "\n")

    calls = []
    real = indexer._parse

    def _slow_parse(path, prev):
        calls.append(path)
        time.sleep(0.2)
        return real(path, prev)

    monkeypatch.setattr(indexer, "_parse", _slow_parse)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: indexer.build_index(root, cache), range(6)))
    assert len(calls) == 1
    assert all(r[0].last_prompt == "more" for r in results)


def test_find_session_path_uses_index_without_globbing(tmp_path, monkeypatch):
    root, f = _seed_root(tmp_path)
    indexer.build_index(root, tmp_path / "cache.json")
    globs = []
    real_glob = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pattern: globs.append(pattern) or real_glob(self, pattern))
    assert indexer.find_session_path(root, "s") == f
    assert globs == []
    assert indexer.find_session_path(root, "missing") is None
    assert globs == ["*/missing.jsonl"]


def test_find_session_path_falls_back_when_indexed_file_moved(tmp_path):
    root, f = _seed_root(tmp_path)
    indexer.build_index(root, tmp_path / "cache.json")
    (root / "q").mkdir()
    moved = f.rename(root / "q" / "s.jsonl")
    assert indexer.find_session_path(root, "s") == moved
    moved.unlink()
    assert indexer.find_session_path(root, "s") is None
