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
