"""Load the resume-launch configuration with safe defaults."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DISTRO = os.environ.get("WSL_DISTRO_NAME") or "Ubuntu-24.04"
# The Windows-side command that opens a shell in the WSL distro, in the session's cwd, running claude.
WSL_SHELL = ["wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--", "bash", "-lic", "{claude}"]
DEFAULT_LAUNCH = ["cmd.exe", "/c", "start", "", *WSL_SHELL]


@dataclass
class LaunchConfig:
    distro: str = DEFAULT_DISTRO
    launch: list[str] = field(default_factory=lambda: list(DEFAULT_LAUNCH))
    # True when config.json sets its own launch template, which then wins over terminal auto-detection.
    launch_overridden: bool = False


def load(path: Path) -> LaunchConfig:
    """Read config.json; fall back to defaults on missing/invalid file."""
    try:
        data = json.loads(Path(path).read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return LaunchConfig()
    if not isinstance(data, dict):
        return LaunchConfig()
    distro = data.get("distro")
    launch = data.get("launch")
    overridden = isinstance(launch, list) and bool(launch)
    return LaunchConfig(
        distro=distro if isinstance(distro, str) and distro else DEFAULT_DISTRO,
        launch=launch if overridden else list(DEFAULT_LAUNCH),
        launch_overridden=overridden,
    )
