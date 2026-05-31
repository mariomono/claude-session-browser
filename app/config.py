"""Load the resume-launch configuration with safe defaults."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DISTRO = os.environ.get("WSL_DISTRO_NAME") or "Ubuntu-24.04"
DEFAULT_LAUNCH = [
    "cmd.exe", "/c", "start", "",
    "wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--",
    "bash", "-lic", "{claude}",
]


@dataclass
class Config:
    distro: str = DEFAULT_DISTRO
    launch: list[str] = field(default_factory=lambda: list(DEFAULT_LAUNCH))


def load(path: Path) -> Config:
    """Read config.json; fall back to defaults on missing/invalid file."""
    try:
        data = json.loads(Path(path).read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    distro = data.get("distro")
    launch = data.get("launch")
    return Config(
        distro=distro if isinstance(distro, str) and distro else DEFAULT_DISTRO,
        launch=launch if isinstance(launch, list) and launch else list(DEFAULT_LAUNCH),
    )
