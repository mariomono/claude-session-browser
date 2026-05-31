"""Build and spawn the terminal command that resumes a Claude session."""
import subprocess

from .config import Config


def build_claude_cmd(session_id: str, mode: str) -> str:
    """The command run inside the shell: resume (and optionally fork)."""
    cmd = f"claude --resume {session_id}"
    if mode == "fork":
        cmd += " --fork-session"
    return cmd


def build_command(template: list[str], distro: str, cwd: str,
                  session_id: str, mode: str) -> list[str]:
    """Substitute placeholders in the argv template, one token at a time.

    Each placeholder token is replaced by exactly one resolved token, so a cwd
    containing spaces can never be re-split into extra arguments.
    """
    claude = build_claude_cmd(session_id, mode)
    out: list[str] = []
    for tok in template:
        if tok == "{distro}":
            out.append(distro)
        elif tok == "{cwd}":
            out.append(cwd)
        elif tok == "{claude}":
            out.append(claude)
        else:
            out.append(tok)
    return out


def _default_spawn(command: list[str]) -> None:
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def resume_session(session_id: str, cwd: str, mode: str, config: Config,
                   spawn=_default_spawn) -> dict:
    """Build the launch command and spawn it detached.

    Returns {"ok": True, "command": [...]} on success, or
    {"ok": False, "command": [...], "error": str} if spawning raised.
    """
    command = build_command(config.launch, config.distro, cwd, session_id, mode)
    try:
        spawn(command)
    except Exception as exc:  # noqa: BLE001 - report any spawn failure to the UI
        return {"ok": False, "command": command, "error": str(exc)}
    return {"ok": True, "command": command}
