"""Detect a terminal emulator on this machine that can host a resumed Claude session.

Templates use the same argv format as LaunchConfig.launch: {distro}, {cwd} and {claude} are
whole argv tokens, each replaced by exactly one resolved token.
"""

import os
import shlex
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from app.services.launch_config import DEFAULT_LAUNCH, WSL_SHELL, LaunchConfig

Which = Callable[[str], str | None]

# Terminals without a working-directory flag run the shell through `env -C`, which changes into
# {cwd} first, so the cwd stays a single argv token instead of being spliced into a shell string.
_SHELL_IN_CWD = ["env", "-C", "{cwd}", "bash", "-lic", "{claude}"]

_WSL_TEMPLATES = [
    # A new tab in the most recently used Windows Terminal window. The -p
    # profile supplies the distro's look (colors, icon); Windows Terminal
    # auto-generates a profile named after each installed distro.
    ["wt.exe", "-w", "0", "nt", "-p", "{distro}", *WSL_SHELL],
    # A plain console window.
    list(DEFAULT_LAUNCH),
]

_LINUX_TEMPLATES = [
    ["x-terminal-emulator", "-e", *_SHELL_IN_CWD],
    ["gnome-terminal", "--working-directory", "{cwd}", "--", "bash", "-lic", "{claude}"],
    ["konsole", "--workdir", "{cwd}", "-e", "bash", "-lic", "{claude}"],
    ["xfce4-terminal", "-x", *_SHELL_IN_CWD],
    ["xterm", "-e", *_SHELL_IN_CWD],
]

# Terminal.app runs `cd <cwd> && <claude>`; the cwd arrives as an osascript argument and is shell-quoted
# by AppleScript's `quoted form of`, never spliced into the script text.
_MACOS_TEMPLATES = [
    [
        "osascript",
        "-e", "on run argv",
        "-e", 'tell application "Terminal"',
        "-e", "activate",
        "-e", 'do script "cd " & quoted form of (item 1 of argv) & " && " & (item 2 of argv)',
        "-e", "end tell",
        "-e", "end run",
        "{cwd}", "{claude}",
    ],
]  # fmt: skip

_WINDOWS_TEMPLATES = [
    ["wt.exe", "-w", "0", "nt", "-d", "{cwd}", "cmd", "/k", "{claude}"],
    ["cmd", "/c", "start", "", "/D", "{cwd}", "cmd", "/k", "{claude}"],
]


def is_wsl(environ: Mapping[str, str] | None = None, proc_version: Path = Path("/proc/version")) -> bool:
    """True when running inside WSL: WSL_DISTRO_NAME is set, or the kernel is Microsoft's."""
    env = os.environ if environ is None else environ
    if env.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in proc_version.read_text().lower()
    except OSError:
        return False


def detect_platform(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    proc_version: Path = Path("/proc/version"),
) -> str:
    """One of "wsl", "linux", "macos", "windows"."""
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        return "windows"
    if plat == "darwin":
        return "macos"
    return "wsl" if is_wsl(environ, proc_version) else "linux"


def candidate_templates(platform: str, environ: Mapping[str, str] | None = None) -> list[list[str]]:
    """Launch templates for a detected platform, most preferred first, not yet checked for availability."""
    env = os.environ if environ is None else environ
    if platform == "wsl":
        return [list(t) for t in _WSL_TEMPLATES]
    if platform == "macos":
        return [list(t) for t in _MACOS_TEMPLATES]
    if platform == "windows":
        return [list(t) for t in _WINDOWS_TEMPLATES]
    templates: list[list[str]] = []
    terminal = shlex.split(env.get("TERMINAL", ""))
    if terminal:
        templates.append([*terminal, "-e", *_SHELL_IN_CWD])
    templates.extend(list(t) for t in _LINUX_TEMPLATES)
    return templates


def available_templates(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: Which | None = None,
) -> list[list[str]]:
    """Candidate templates whose executable is on PATH, most preferred first."""
    find = shutil.which if which is None else which
    plat = detect_platform(environ=environ) if platform is None else platform
    return [t for t in candidate_templates(plat, environ) if find(t[0])]


def select_template(
    config: LaunchConfig,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    which: Which | None = None,
) -> list[str] | None:
    """The template to launch with: the config.json override, else the first available terminal, else None."""
    if config.launch_overridden:
        return config.launch
    available = available_templates(platform, environ, which)
    return available[0] if available else None
