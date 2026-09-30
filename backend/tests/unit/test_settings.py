from pathlib import Path

from app.core.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("CSB_CLAUDE_PROJECTS_DIR", raising=False)
    monkeypatch.delenv("CSB_DATA_DIR", raising=False)
    s = Settings()
    assert s.claude_projects_dir == Path.home() / ".claude" / "projects"
    assert s.data_dir == Path("data")


def test_env_prefix_and_user_expansion(monkeypatch):
    monkeypatch.setenv("CSB_CLAUDE_PROJECTS_DIR", "~/logs")
    monkeypatch.setenv("CSB_DATA_DIR", "/var/csb")
    s = Settings()
    assert s.claude_projects_dir == Path.home() / "logs"
    assert s.data_dir == Path("/var/csb")


def test_data_files_live_in_data_dir(tmp_path):
    s = Settings(data_dir=tmp_path)
    assert s.cache_path == tmp_path / "cache.json"
    assert s.bookmarks_path == tmp_path / "bookmarks.json"
    assert s.launch_config_path == tmp_path / "config.json"
    assert s.launch_queue_dir == tmp_path / "launch"
