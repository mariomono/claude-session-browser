from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Settings pointing both the session logs and the app data at the test's tmp dir."""
    projects = tmp_path / "projects"
    projects.mkdir()
    return Settings(claude_projects_dir=projects, data_dir=tmp_path / "data")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
