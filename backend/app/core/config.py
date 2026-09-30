"""Deployment settings, read from ``CSB_``-prefixed environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CSB_", extra="ignore")

    # Where Claude Code writes its session logs: one directory per project, one .jsonl per session.
    claude_projects_dir: Path = Field(default_factory=lambda: Path.home() / ".claude" / "projects")

    # The app's own files: the index cache, the bookmarks and the optional launcher config.json.
    # The directory is created on first write.
    data_dir: Path = Path("data")

    @field_validator("claude_projects_dir", "data_dir")
    @classmethod
    def _expand_user(cls, value: Path) -> Path:
        return value.expanduser()

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "cache.json"

    @property
    def bookmarks_path(self) -> Path:
        return self.data_dir / "bookmarks.json"

    @property
    def launch_config_path(self) -> Path:
        return self.data_dir / "config.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
