# Claude Session Browser

A local web app to browse Claude Code session logs from `~/.claude/projects/`.
FastAPI backend + React frontend, run as containers.

## Quick start

Requires [docker](https://docs.docker.com/engine/install/) with compose,
[just](https://just.systems/man/en/) (`uv tool install rust-just`),
[uv](https://docs.astral.sh/uv/), and Node 22+ (uv/Node only for the dev
tooling and git hooks — the running app is containers only).

    just setup      # once after cloning: deps, git hooks, data dir, images
    just start      # -> http://localhost:43210
    just stop       # stop and remove the containers

`just update` re-syncs dependencies and rebuilds the images after changes.
`just logs`, `just test` and `just lint` do what they say; bare `just` lists
everything.

The published port (43210, localhost-only) is deliberately uncommon so it
doesn't clash with other local containers.

## What it shows

A sortable, searchable table of every Claude Code session (newest first):
title, project, first/last prompt, state (clean/interrupted/error, recency,
size, compacted), and context-window usage. Click a row for a read-only
transcript. Use **Rescan** to pick up new sessions.

Subagent transcripts (stored under `<session>/subagents/`) are intentionally
excluded from the list so they are not shown as standalone sessions.

## Resuming a session

Each row has two actions:

- **▸ Resume** — `claude --resume <id>` in the session's working directory
  (continues the same session).
- **⑂ Fork** — same, but `--fork-session` starts a fresh session seeded from
  the old one, leaving the original untouched.

Inside the container the backend cannot spawn a terminal on the host, so the
UI shows the exact command with a **Copy** button — paste it into a terminal
yourself. When the backend runs natively (see Development), it launches the
terminal directly; the launch command is configurable: copy
`backend/config.example.json` to `data/config.json` and edit `launch` /
`distro`. Placeholders `{distro}`, `{cwd}`, and `{claude}` are substituted as
single argv tokens.

> **Security:** the resume endpoint can spawn a process on your machine. The
> compose file binds the app to `127.0.0.1` only — do not expose it to a
> network.

## Bookmarks

Click the star in the first column to bookmark a session — gold (★) when
bookmarked, outlined (☆) when not. The same star appears in the transcript
header. Use the **★ Bookmarks** toggle in the header to show only bookmarked
sessions; search, sort, and the project filter still apply.

## Data & config

Everything the app writes lives in `./data/` (gitignored), mounted into the
backend container at `/data`:

- `cache.json` — session index cache (rebuilt on demand)
- `bookmarks.json` — your bookmarks
- `config.json` — optional launcher config (see above)

Session logs are mounted read-only from `~/.claude/projects` — the app never
writes there. Those files are chmod 600, so the backend container runs as
your host user (default `1000:1000`; override with `CSB_UID`/`CSB_GID` env
vars if yours differ).

## Development

Layout: `backend/` is a FastAPI app in the `app/api/v1` / `core` / `schemas` /
`services` style, managed by uv and checked with ruff + ty. `frontend/` is
Vite + React + TypeScript, served by nginx in the container. Dev ports are
also uncommon on purpose: backend 43211, Vite 43212.

    cd backend && uv sync
    CSB_DATA_DIR=../data uv run uvicorn app.main:app --port 43211

    cd frontend && npm install
    npm run dev     # -> http://localhost:43212, proxies /api to 43211

Backend settings come from `CSB_`-prefixed env vars
(`backend/app/core/config.py`): `CSB_CLAUDE_PROJECTS_DIR`, `CSB_DATA_DIR`.

Tests and checks: `just test` (pytest), `just lint` (ruff, ruff format, ty).
Git hooks are installed by `just setup`; commit messages follow Conventional
Commits (commitlint), and committing to `master` is blocked.
