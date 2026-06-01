# Bookmarks — Design

**Date:** 2026-06-01
**Status:** Approved (design phase)
**Builds on:** the Claude Session Browser + resume launcher.

## Problem

The user wants to mark sessions as bookmarks and quickly view only those. Each
row gets a star in the first column: a yellow filled star (★) when bookmarked,
an outlined star (☆) when not. Clicking the star toggles the bookmark. A header
control filters the table to bookmarked sessions only.

## Decisions (from brainstorming)

- **Storage:** a server-side `bookmarks.json` (gitignored), holding the set of
  bookmarked session IDs. Consistent with the existing `config.json` pattern;
  shared across any browser hitting the server.
- **Bookmarks "list":** a header **filter toggle** (not a separate page). When
  active, the existing table shows only bookmarked sessions; search/sort/project
  filter still apply.

## Architecture

```
Row star button (★/☆)
  POST /api/sessions/{id}/bookmark  → toggle → {bookmarked: bool}
Header "★ Bookmarks" toggle
  GET /api/sessions?bookmarked=true → only starred sessions
        │
FastAPI (app/main.py)
  list_sessions: build_index → annotate each with bookmarked → optional filter
  bookmark route: find_session_path (validate id) → bookmarks.toggle
        │
app/bookmarks.py   load / save / toggle a set of ids in bookmarks.json
```

**Principle: bookmark state is orthogonal to the file-index cache.** The index is
cached per file by mtime+size; a bookmark can change without the log changing.
The `bookmarked` flag is therefore set on each `SessionIndex` *after*
`build_index` has written its cache, so bookmark state never enters the cache and
a toggle never forces a re-index.

## Components

### `app/bookmarks.py`
- `load(path) -> set[str]`: read a JSON list into a set; missing file, `OSError`,
  malformed JSON, or non-list content → empty set.
- `save(path, ids: set[str]) -> None`: write `sorted(ids)` as a JSON list.
- `toggle(path, session_id) -> bool`: load the set; if present remove it, else add
  it; save; return the new state (`True` = now bookmarked).

### `app/models.py`
- `SessionIndex` gains `bookmarked: bool = False`.

### `app/main.py`
- Constant `BOOKMARKS = _BASE / "bookmarks.json"`.
- `list_sessions(..., bookmarked: bool = False)`: after `build_index`, load the
  bookmark set; set `s.bookmarked = (s.session_id in marks)` for every session;
  if the `bookmarked` query param is true, keep only bookmarked sessions. The
  `projects` list is still derived from the full (pre-bookmark-filter) set.
- `POST /api/sessions/{session_id}/bookmark`: `find_session_path` validates the id
  (regex) and confirms the session exists → 404 otherwise; then
  `bookmarks.toggle(BOOKMARKS, session_id)`; return `{"bookmarked": bool}`.

### Frontend
- **First column (new, narrow):** a star `<button>` per row. `★` with gold color
  when `s.bookmarked`, else `☆` outlined. `event.stopPropagation()` so the click
  does not open the transcript. On click → `POST …/bookmark`; update
  `s.bookmarked` in the in-memory list from the response and re-render. If the
  Bookmarks filter is active and the session became unbookmarked, refetch so it
  drops out of the list.
- **Detail header:** the same star toggle for the open session.
- **Header control:** a `★ Bookmarks` toggle button beside the project filter.
  Active → `state.bookmarkedOnly = true`, refetch with `?bookmarked=true`, button
  shows an active style; click again clears and refetches.

## Error handling

- Missing/malformed `bookmarks.json` → empty set (never crash).
- Bookmarking a missing/invalid id → 404 (via `find_session_path`).
- A bookmarked id whose log was later deleted simply never appears in the list
  (harmless orphan in `bookmarks.json`).

## Testing

- `tests/test_bookmarks.py`: `load` on a missing file → empty set; `toggle` adds
  (returns True) then removes (returns False); state persists across `load` after
  `toggle`; malformed file → empty set.
- `tests/test_api_bookmark.py` (FastAPI `TestClient`, temp root + temp bookmarks
  file): list response carries `bookmarked` (false initially); POST bookmark →
  `{"bookmarked": true}` and the id appears in the bookmarks file; second POST →
  `{"bookmarked": false}`; `GET /api/sessions?bookmarked=true` returns only the
  starred session; POST bookmark for a missing id → 404.
- Frontend verified manually against the running server (star toggles and turns
  gold; the Bookmarks filter narrows the table), consistent with prior frontend
  tasks.

## Files

- Create: `app/bookmarks.py`, `tests/test_bookmarks.py`, `tests/test_api_bookmark.py`.
- Modify: `app/models.py` (+`bookmarked`), `app/main.py` (+constant, +param,
  +annotate/filter, +route), `static/index.html`, `static/app.js`,
  `static/styles.css`, `.gitignore` (+`bookmarks.json`), `README.md`.

## Out of scope (YAGNI)

- Bookmark folders/tags or ordering.
- Per-user bookmarks (single-user local tool).
- A separate bookmarks page/route (header filter instead).
- Bulk bookmark/clear operations.
