# Resume-Session Launcher — Design

**Date:** 2026-06-01
**Status:** Approved (design phase)
**Builds on:** the Claude Session Browser (`2026-06-01-claude-session-browser-design.md`)

## Problem

From the session table, the user wants to relaunch a past Claude Code session in
a new terminal window with one click. The browser runs on Windows; the FastAPI
server runs inside WSL2 (Ubuntu-24.04). Each row should offer a resume action
that opens a terminal running `claude --resume <id>` in the session's working
directory.

## Environment facts (verified)

- `claude` CLI: `claude --resume <id>` (alias `-r`) resumes by session ID;
  `--fork-session` resumes into a NEW session ID seeded from the old one.
  Binary at `/home/mario/.local/bin/claude`.
- WSL interop: `wt.exe`, `cmd.exe`, `powershell.exe` are all on PATH from inside
  WSL. Distro is `Ubuntu-24.04` (`$WSL_DISTRO_NAME`).
- A new visible console window requires `cmd.exe /c start ...` (or `wt.exe`);
  invoking `wsl.exe` directly from the server would not surface a window.

## Decisions (from brainstorming)

- **Approach A with B fallback:** the server spawns the terminal via WSL interop;
  if the spawn fails, the UI shows the exact command with a Copy button.
- **Resume mode configurable:** support both *continue* (same session) and *fork*
  (`--fork-session`). Two affordances in the UI.
- **Terminal configurable, defaults to a plain WSL window** (`cmd.exe /c start "" wsl.exe …`).
- **Config lives in a project file** `config.json` (gitignored); a committed
  `config.example.json` documents the format.

## Architecture

```
Browser row icons (▸ resume / ⑂ fork)
  POST /api/sessions/{id}/resume?mode=continue|fork
        │
FastAPI (app/main.py)
  validate id (find_session_path) + mode → resolve cwd (indexer.session_cwd)
  → launcher.resume_session(...) → returns {ok, command, error}
        │
app/launcher.py   build argv from template + spawn detached (injectable spawn)
app/config.py     load config.json (template + distro) with safe defaults
        │ spawns
  cmd.exe /c start "" wsl.exe -d <distro> --cd <cwd> -- bash -lic "claude --resume <id> [--fork-session]"
```

**Principle: argv-list, never a shell string.** The launch template is a list of
argument tokens with placeholders. Substitution replaces a placeholder token with
exactly one resolved token, so a `cwd` containing spaces (or anything else) can
never be re-parsed into extra arguments. The only shell-interpreted token is the
`bash -lic` argument `{claude}`, which is composed solely of the static `claude`
command, the static `--resume`/`--fork-session` flags, and the session id — and
the id is already constrained to `^[A-Za-z0-9_-]+$` by `find_session_path`. There
is therefore no shell-injection surface.

## Components

### `app/config.py`
- `DEFAULT_DISTRO`: `$WSL_DISTRO_NAME` or `"Ubuntu-24.04"`.
- `DEFAULT_LAUNCH`: argv template (see below).
- `load(path) -> Config`: read `config.json`; on missing file or JSON error,
  return defaults. Unknown keys ignored; missing keys filled from defaults.
- `Config` exposes `.distro: str` and `.launch: list[str]`.

Default template:
```json
{
  "distro": "Ubuntu-24.04",
  "launch": ["cmd.exe","/c","start","","wsl.exe","-d","{distro}","--cd","{cwd}","--","bash","-lic","{claude}"]
}
```

### `app/launcher.py`
- `build_claude_cmd(session_id, mode) -> str`: returns `claude --resume <id>` and
  appends ` --fork-session` when `mode == "fork"`.
- `build_command(template, distro, cwd, session_id, mode) -> list[str]`:
  copy the template; for each token, replace `{distro}` → distro, `{cwd}` → cwd,
  `{claude}` → `build_claude_cmd(...)`. Substitution is per-token (a token equal
  to a placeholder becomes the single resolved value).
- `resume_session(session_id, cwd, mode, config, spawn=_default_spawn) -> dict`:
  builds the command, calls `spawn(command)` (default spawns detached via
  `subprocess.Popen` with stdout/stderr to DEVNULL and start_new_session=True),
  returns `{"ok": True, "command": [...]}`; on any exception returns
  `{"ok": False, "command": [...], "error": str(exc)}`.

### `app/indexer.py` (addition)
- `session_cwd(path) -> str | None`: iterate `iter_records(path)` and return the
  first record's `cwd`, stopping early. Avoids loading large files just to read
  the working directory.

### `app/main.py` (addition)
- `POST /api/sessions/{session_id}/resume?mode=continue` (default `continue`):
  1. `mode` not in `{"continue","fork"}` → 400.
  2. `find_session_path(ROOT, id)` → 404 if not found.
  3. `cwd = indexer.session_cwd(path)` or `str(Path.home())` fallback.
  4. `result = launcher.resume_session(id, cwd, mode, CONFIG)`.
  5. Always return 200 with `result` (`{ok, command, error?}`) so the frontend
     can show the copy-fallback when `ok` is false.
- `CONFIG = config.load(_BASE / "config.json")` loaded at import (reload picks up
  edits on server restart).

## Frontend

- **Row actions:** two icon buttons per row — `▸` (resume/continue) and `⑂`
  (fork) — each with a tooltip. `event.stopPropagation()` prevents the row's
  transcript-open handler from firing.
- **Detail header:** matching **Resume** and **Fork** buttons.
- **Click handler:** `POST /api/sessions/{id}/resume?mode=…`; disable the control
  briefly. On `ok:true` show a subtle toast ("Launching <id>…"). On `ok:false`
  or a network error, show a toast containing the resolved command string with a
  **Copy** button (fallback B). The command is rendered escaped.
- **Toast:** a small fixed-position element, auto-dismiss after a few seconds
  (the copy-fallback toast stays until dismissed).

## Error handling

- Spawn failure (wt/cmd/claude missing, bad template) → caught in
  `resume_session`, surfaced as `ok:false` + `error` + the attempted `command`;
  UI shows command + Copy.
- Invalid `mode` → 400. Unknown/expired session id → 404.
- Missing/malformed `config.json` → defaults (never crash).
- Missing `cwd` in the log → fall back to the user's home directory.

## Testing

- `tests/test_config.py`: missing file → defaults; valid file → overrides;
  malformed JSON → defaults; partial file → missing keys filled.
- `tests/test_launcher.py`: `build_claude_cmd` continue vs fork; `build_command`
  substitutes distro/cwd/claude as single tokens; a `cwd` with spaces remains one
  argv element; `resume_session` with a fake spawn records the argv and returns
  `ok:true`; a spawn that raises yields `ok:false` with `error`.
- `tests/test_api_resume.py` (FastAPI `TestClient`, monkeypatched spawn):
  continue → 200, command contains `--resume` and the id; fork → command contains
  `--fork-session`; bad mode → 400; missing id → 404; spawn failure → 200 with
  `ok:false`.
- Frontend verified manually against the running server (icons spawn a window;
  forced failure shows the copy-fallback), consistent with the original Task 10.

## Files

- Create: `app/config.py`, `app/launcher.py`, `config.example.json`,
  `tests/test_config.py`, `tests/test_launcher.py`, `tests/test_api_resume.py`.
- Modify: `app/indexer.py` (+`session_cwd`), `app/main.py` (+route, load config),
  `static/index.html`, `static/app.js`, `static/styles.css`, `.gitignore`
  (+`config.json`).

## Out of scope (YAGNI)

- Editing the template from the web UI (file-based only).
- Non-WSL launch backends (native Linux/macOS terminals).
- URL-protocol-handler approach (Approach C).
- Tracking/managing the spawned terminal process after launch (fire-and-forget).
