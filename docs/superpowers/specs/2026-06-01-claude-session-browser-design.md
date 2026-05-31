# Claude Session Browser — Design

**Date:** 2026-06-01
**Status:** Approved (design phase)

## Problem

Claude Code sessions accumulate across many projects and the home directory in
various states of completion. There is no quick way to see what exists. We want
a clean, concise local web page to preview them: a sortable, searchable table of
sessions (title, description, state, context usage) with a read-only transcript
view on click.

## Key facts about the data source

- **Single location.** Every Claude Code session — regardless of its original
  cwd (`~`, `~/projects`, any subfolder) — is stored under
  `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. So "scattered across
  folders" is actually **one directory to scan** (currently 308 files, ~191MB).
- **Folder names are lossy.** The encoded folder name replaces `/`, `.`, and `-`
  all with `-`, so it cannot be reliably decoded. The real working directory must
  be read from the `cwd` field inside the file.
- **JSONL line types** (one JSON object per line, records form a DAG via
  `uuid`/`parentUuid`):
  - `user` — a prompt, a tool_result, or a compaction summary (`isCompactSummary`).
  - `assistant` — model response; carries `message.usage` and `message.model`.
  - `ai-title` — auto-generated title sidecar (last one wins). Present in ~28% of files.
  - `custom-title` — user-set title; overrides `ai-title`.
  - `last-prompt` — bookmarks the active branch leaf (`leafUuid`, `lastPrompt`).
  - `summary` — branch summary at compaction/resume (older title source).
  - `system` — hook output, compaction notices; `compactMetadata` lives here.
  - `attachment`, `queue-operation`, `file-history-snapshot`, `permission-mode`,
    `agent-name`/`agent-color` — sidecar/metadata.
- **Context usage** is derived from `assistant.message.usage`. The reliable
  measure of "how full the window got" is the **latest** assistant message's
  input side only: `input_tokens + cache_creation_input_tokens +
  cache_read_input_tokens`. `input_tokens` can be a streaming placeholder (0/1),
  but the cache fields — which dominate — are reliable. Do NOT sum across
  messages and do NOT add `output_tokens` for context-fill.
- **Window size:** default 200,000; switch denominator to 1,000,000 if observed
  context tokens exceed ~200k (the only reliable signal the 1M beta was active).
  Model read from latest non-`<synthetic>` assistant `message.model`.
- **Sidechains:** records with `isSidechain: true` belong to subagent/Task
  branches. Exclude them from the session list and from index counts so they are
  not shown as separate sessions or double-counted.

## Build vs. reuse

No existing tool is a drop-in for a clean read-only listing page (surveyed:
claude-code-viewer, claude-code-log, simonw/claude-code-transcripts, ccusage,
claude-code-trace, clog). We build a thin page of our own, borrowing two ideas:
robust per-line parsing with fallbacks (claude-code-viewer's schema approach) and
token math (ccusage). Architecture chosen: **small local backend + clean
frontend** (Approach B), because it matches the existing FastAPI stack, stays
current on refresh, and is the only option that handles the data volume by
indexing eagerly and parsing full transcripts lazily.

## Architecture

```
Browser (table page + transcript view)
  - GET /api/sessions          → render sortable/filterable/searchable table
  - GET /api/sessions/{id}      → render one transcript
        │ JSON over localhost
FastAPI backend
  indexer.py  → scan ~/.claude/projects/, build index, persist cache.json
  parser.py   → parse ONE session file into transcript JSON (lazy)
  tokens.py   → usage / window-size math
  models.py   → pydantic schemas
  main.py     → routes + static file serving
        │ reads
  ~/.claude/projects/**/*.jsonl
```

**Core principle: index eagerly, hydrate lazily.** The table needs ~10 small
fields per session; transcripts are large and rarely opened. Build a cheap index
up front; parse a full transcript only when a row is clicked.

## Index pass (cheap, eager)

Single streaming read per file, never holding the whole file in memory. Extract:

| Field | Source |
|---|---|
| `session_id` | filename |
| `title` | `custom-title` → `ai-title` → fallback `session_id` |
| `first_prompt` | first `user` message text, truncated ~200 chars |
| `last_prompt` | `last-prompt.lastPrompt` or last `user` message, truncated ~200 chars |
| `cwd`, `git_branch` | any conversation record |
| `last_activity` | max `timestamp` across records |
| `message_count` | count of `user` + `assistant` records (excluding sidechains) |
| `context_tokens` / `context_pct` | latest assistant input-side tokens ÷ window size |
| `model` | latest non-`<synthetic>` assistant `message.model` |
| `state` flags | see below |

**Caching:** index persisted to `cache.json`, each entry keyed by file
`mtime`+`size`. On startup/refresh a file is re-parsed only if mtime/size
changed. After the first scan, reloads are near-instant; only new/changed
sessions are re-read. A manual "rescan" endpoint/button forces a refresh.

## State badges

- **Outcome:** `clean` (leaf `stop_reason: end_turn`) · `interrupted` (leaf is
  `tool_use` with no following result, or record has `interruptedMessageId`) ·
  `error` (`isApiErrorMessage`).
- **Recency:** `today` / `this week` / `this month` / `older` from `last_activity`.
- **Size:** message count plus a coarse bucket (S/M/L).
- **Compacted:** marker if any `system` record carries `compactMetadata`.

## Frontend

### Table page (`/`)

- Newest-first by default (`last_activity` desc).
- Columns: **Title** · **Project** (real cwd + git branch) · **Description**
  (first → last prompt) · **State** (outcome icon, recency, size bucket, `⟳` if
  compacted) · **Ctx** (% bar + raw token count; tooltip = model + window size).
- **Sortable** columns (date, title, context %, size).
- **Filter by project** dropdown, populated from distinct real `cwd`s.
- **Search** box: server-side substring match over title + first/last prompt;
  debounced.
- **Rescan** control to force index refresh.
- Row click → transcript view.

### Transcript view (`/session/{id}`)

- Parses just that one file on demand. Renders chronologically:
  - `user` / `assistant` turns with role styling.
  - `thinking` blocks collapsed by default.
  - `tool_use` / `tool_result` as collapsible blocks (tool name + truncated
    args/output, expandable).
  - Synthetic/meta records and `isCompactSummary` injections shown as subtle
    system notes, not user turns.
  - Sidechain/subagent branches rendered inline, visually nested/dimmed.
- Header shows index metadata (title, project, model, context %, state), a "copy
  session id" button, and a back link.

Frontend is vanilla HTML/JS/CSS — no build toolchain.

## Error handling

- **Malformed JSON line:** skip and count it; surface a small "N unparseable
  lines" note rather than failing the whole file (append-only logs can have
  partial trailing writes).
- **Missing fields:** every extracted field optional with a sane fallback
  (title→id, no usage→"unknown").
- **Empty/locked file:** show the row with whatever is available; never crash the index.
- **Huge transcript:** stream-render; if a file exceeds a size threshold,
  paginate or warn before rendering.
- **Stale cache entry:** mtime/size mismatch triggers re-parse of just that file.

## Testing

- **Parser unit tests** against small fixture `.jsonl` files: ai-title
  present/absent, interrupted leaf, API-error leaf, compaction record, sidechain
  records, 1M-context session, malformed trailing line, empty file.
- **Index tests:** sort order, project grouping, search matching, cache hit/miss
  on mtime change.
- **Token-math tests:** context-fill formula (input-side only, latest message)
  and 200k↔1M window selection.
- **API smoke tests** (FastAPI `TestClient`) for `/api/sessions` and
  `/api/sessions/{id}`.
- Build **parser-first with TDD** — JSONL parsing is the riskiest part
  (many record types, version drift, partial writes).

## Project layout

```
my-sessions/
├── pyproject.toml          # fastapi, uvicorn, pydantic
├── app/
│   ├── main.py             # routes + static serving
│   ├── models.py           # pydantic schemas (SessionIndex, Transcript…)
│   ├── indexer.py          # scan + cache.json
│   ├── parser.py           # single-file → transcript
│   └── tokens.py           # usage/window math
├── static/                 # index.html, app.js, styles.css (vanilla, no build)
├── tests/
│   └── fixtures/*.jsonl
└── run.sh                  # one-line launcher (uvicorn app.main:app)
```

## Out of scope (YAGNI)

- Resuming/continuing sessions from the UI.
- Editing, deleting, or exporting sessions.
- Live tailing / websockets for in-progress sessions.
- Cross-session DAG linking across files.
- Authentication (local-only tool).
