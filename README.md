# Claude Session Browser

A local web page to browse Claude Code session logs from `~/.claude/projects/`.

## Run

    uv venv && uv pip install -e ".[dev]"
    ./run.sh

Open http://127.0.0.1:8800.

## What it shows

A sortable, searchable table of every Claude Code session (newest first):
title, project, first/last prompt, state (clean/interrupted/error, recency,
size, compacted), and context-window usage. Click a row for a read-only
transcript. Use **Rescan** to pick up new sessions.

Subagent transcripts (stored under `<session>/subagents/`) are intentionally
excluded from the list so they are not shown as standalone sessions.

## Tests

    .venv/bin/python -m pytest

## Resuming a session

Each row has two actions:

- **▸ Resume** — opens a new terminal running `claude --resume <id>` in the
  session's working directory (continues the same session).
- **⑂ Fork** — same, but `--fork-session` starts a fresh session seeded from the
  old one, leaving the original untouched.

The launch command is configurable. Copy `config.example.json` to `config.json`
(gitignored) and edit `launch` / `distro`. Placeholders `{distro}`, `{cwd}`, and
`{claude}` are substituted as single argv tokens. The default opens a plain WSL
window via `cmd.exe /c start … wsl.exe`. If the launch fails, the UI shows the
exact command with a Copy button so you can run it yourself.
