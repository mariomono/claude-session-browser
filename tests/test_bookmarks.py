from app import bookmarks


def test_load_missing_file_is_empty(tmp_path):
    assert bookmarks.load(tmp_path / "nope.json") == set()


def test_load_malformed_file_is_empty(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("{ not json")
    assert bookmarks.load(p) == set()


def test_load_non_list_is_empty(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"a": 1}')
    assert bookmarks.load(p) == set()


def test_toggle_adds_then_removes(tmp_path):
    p = tmp_path / "b.json"
    assert bookmarks.toggle(p, "sess1") is True
    assert bookmarks.load(p) == {"sess1"}
    assert bookmarks.toggle(p, "sess1") is False
    assert bookmarks.load(p) == set()


def test_toggle_persists_multiple(tmp_path):
    p = tmp_path / "b.json"
    bookmarks.toggle(p, "a")
    bookmarks.toggle(p, "b")
    assert bookmarks.load(p) == {"a", "b"}
