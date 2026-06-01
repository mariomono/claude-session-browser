# Bookmarks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user star sessions as bookmarks (per-row star toggle, gold filled vs outline) and filter the table to bookmarked sessions, with bookmarks persisted server-side in `bookmarks.json`.

**Architecture:** A new `app/bookmarks.py` loads/saves/toggles a set of bookmarked session IDs in a gitignored `bookmarks.json`. `SessionIndex` gains a `bookmarked` flag set *after* the file-index cache is written (keeping bookmark state out of the cache). `list_sessions` annotates and optionally filters by it; a new `POST /api/sessions/{id}/bookmark` toggles. The frontend adds a first-column star button, a detail-header star, and a header "★ Bookmarks" filter toggle.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, httpx (TestClient). Frontend: vanilla HTML/CSS/JS.

**Conventions for every task:** Run tests with `.venv/bin/python -m pytest`. Commit after each task with `git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit` and append the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Work on `master`. The suite currently has 63 passing tests before this plan.

---

## File Structure

- **Create `app/bookmarks.py`** — load/save/toggle a set of ids in `bookmarks.json`. One responsibility: bookmark persistence.
- **Modify `app/models.py`** — add `bookmarked: bool = False` to `SessionIndex`.
- **Modify `app/main.py`** — `BOOKMARKS` constant; annotate+filter in `list_sessions`; `POST …/bookmark` route.
- **Modify `static/{index.html,app.js,styles.css}`** — star column, detail star, header filter toggle.
- **Modify `.gitignore`** — ignore `bookmarks.json`.
- **Tests:** `tests/test_bookmarks.py`, `tests/test_api_bookmark.py`.

---

### Task 1: Bookmarks store (`bookmarks.py`)

**Files:**
- Create: `app/bookmarks.py`
- Modify: `.gitignore`
- Test: `tests/test_bookmarks.py`

- [ ] **Step 1: Write the failing test `tests/test_bookmarks.py`**

```python
from app import bookmarks


def test_load_missing_file_is_empty(tmp_path):
    assert bookmarks.load(tmp_path / "nope.json") == set()


def test_load_malformed_file_is_empty(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("{ not json")
    assert bookmarks.load(p) == set()


def test_load_non_list_is_empty(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"a": 1}')
    assert bookmarks.load(p) == set()


def test_toggle_adds_then_removes(tmp_path):
    p = tmp_path / "b.json"
    assert bookmarks.toggle(p, "sess1") is True
    assert bookmarks.load(p) == {"sess1"}
    assert bookmarks.toggle(p, "sess1") is False
    assert bookmarks.load(p) == set()


def test_toggle_persists_multiple(tmp_path):
    p = tmp_path / "b.json"
    bookmarks.toggle(p, "a")
    bookmarks.toggle(p, "b")
    assert bookmarks.load(p) == {"a", "b"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_bookmarks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.bookmarks'`.

- [ ] **Step 3: Implement `app/bookmarks.py`**

```python
"""Persist the set of bookmarked session IDs in a JSON file."""
import json
from pathlib import Path


def load(path: Path) -> set[str]:
    """Read the bookmark set; empty on missing/malformed/non-list file."""
    try:
        data = json.loads(Path(path).read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(x) for x in data}


def save(path: Path, ids: set[str]) -> None:
    Path(path).write_text(json.dumps(sorted(ids)))


def toggle(path: Path, session_id: str) -> bool:
    """Add the id if absent, remove it if present. Return the new state."""
    ids = load(path)
    if session_id in ids:
        ids.discard(session_id)
        now = False
    else:
        ids.add(session_id)
        now = True
    save(path, ids)
    return now
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_bookmarks.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Add `bookmarks.json` to `.gitignore`**

Append a line `bookmarks.json` to `.gitignore` (keep existing entries).

- [ ] **Step 6: Commit**

```bash
git add app/bookmarks.py tests/test_bookmarks.py .gitignore
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: bookmark persistence store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `bookmarked` field on `SessionIndex`

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_models.py` (append)

- [ ] **Step 1: Append the failing test to `tests/test_models.py`**

```python
def test_session_index_bookmarked_defaults_false():
    from app.models import SessionIndex
    s = SessionIndex(session_id="abc", title="abc")
    assert s.bookmarked is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL with `AttributeError: 'SessionIndex' object has no attribute 'bookmarked'`.

- [ ] **Step 3: Modify `app/models.py`**

In the `SessionIndex` class, add the field immediately after the `compacted: bool = False` line:

```python
    bookmarked: bool = False
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: add bookmarked flag to SessionIndex

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Annotate + filter in `list_sessions`, and the bookmark route

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api_bookmark.py`

The current `app/main.py` top of file is:

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, indexer, launcher, parser

ROOT = indexer.default_root()
_BASE = Path(__file__).resolve().parent.parent
CACHE = _BASE / "cache.json"
STATIC = _BASE / "static"
CONFIG = config.load(_BASE / "config.json")
```

The current `list_sessions` is:

```python
@app.get("/api/sessions")
def list_sessions(q: str | None = None, project: str | None = None,
                  refresh: bool = False):
    all_sessions = indexer.build_index(ROOT, CACHE, force=refresh)
    projects = sorted({s.cwd for s in all_sessions if s.cwd})
    sessions = all_sessions
    if project:
        sessions = [s for s in sessions if s.cwd == project]
    if q:
        ql = q.lower()
        sessions = [
            s for s in sessions
            if any(ql in (v or "").lower()
                   for v in (s.title, s.first_prompt, s.last_prompt))
        ]
    return {"sessions": [s.model_dump() for s in sessions], "projects": projects}
```

- [ ] **Step 1: Write the failing test `tests/test_api_bookmark.py`**

```python
import json
import importlib
from fastapi.testclient import TestClient


def _make_client(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    (root / "p" / "sess1.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-05-01T00:00:00Z",
                    "cwd": "/home/mario/projects/demo",
                    "message": {"role": "user", "content": "hi"}}) + "\n")
    (root / "p" / "sess2.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-04-01T00:00:00Z",
                    "cwd": "/home/mario/projects/demo",
                    "message": {"role": "user", "content": "yo"}}) + "\n")
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(main, "BOOKMARKS", tmp_path / "bookmarks.json")
    return TestClient(main.app), tmp_path / "bookmarks.json"


def test_list_includes_bookmarked_false_initially(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    data = client.get("/api/sessions").json()
    assert all(s["bookmarked"] is False for s in data["sessions"])


def test_bookmark_toggles_and_persists(tmp_path, monkeypatch):
    client, bfile = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/bookmark")
    assert resp.status_code == 200
    assert resp.json() == {"bookmarked": True}
    assert "sess1" in json.loads(bfile.read_text())
    # second toggle removes it
    assert client.post("/api/sessions/sess1/bookmark").json() == {"bookmarked": False}
    assert json.loads(bfile.read_text()) == []


def test_list_reflects_bookmark(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    client.post("/api/sessions/sess1/bookmark")
    data = client.get("/api/sessions").json()
    by_id = {s["session_id"]: s["bookmarked"] for s in data["sessions"]}
    assert by_id["sess1"] is True
    assert by_id["sess2"] is False


def test_bookmarked_filter(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    client.post("/api/sessions/sess1/bookmark")
    data = client.get("/api/sessions?bookmarked=true").json()
    assert [s["session_id"] for s in data["sessions"]] == ["sess1"]


def test_bookmark_missing_session_404(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/missing/bookmark").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_bookmark.py -v`
Expected: FAIL (no `BOOKMARKS` attr / no bookmark route / `bookmarked` key missing).

- [ ] **Step 3: Modify `app/main.py`**

(a) Replace `from . import config, indexer, launcher, parser` with:

```python
from . import bookmarks, config, indexer, launcher, parser
```

(b) After the `CONFIG = config.load(_BASE / "config.json")` line, add:

```python
BOOKMARKS = _BASE / "bookmarks.json"
```

(c) Replace the entire `list_sessions` function with this version (adds the `bookmarked` param, annotation, and filter):

```python
@app.get("/api/sessions")
def list_sessions(q: str | None = None, project: str | None = None,
                  refresh: bool = False, bookmarked: bool = False):
    all_sessions = indexer.build_index(ROOT, CACHE, force=refresh)
    projects = sorted({s.cwd for s in all_sessions if s.cwd})
    marks = bookmarks.load(BOOKMARKS)
    for s in all_sessions:
        s.bookmarked = s.session_id in marks
    sessions = all_sessions
    if project:
        sessions = [s for s in sessions if s.cwd == project]
    if q:
        ql = q.lower()
        sessions = [
            s for s in sessions
            if any(ql in (v or "").lower()
                   for v in (s.title, s.first_prompt, s.last_prompt))
        ]
    if bookmarked:
        sessions = [s for s in sessions if s.bookmarked]
    return {"sessions": [s.model_dump() for s in sessions], "projects": projects}
```

(d) Add the bookmark route immediately AFTER the existing `resume_session` route (before the `index_page` route):

```python
@app.post("/api/sessions/{session_id}/bookmark")
def bookmark_session(session_id: str):
    path = indexer.find_session_path(ROOT, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    return {"bookmarked": bookmarks.toggle(BOOKMARKS, session_id)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api_bookmark.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green (63 prior + 5 + 1 + 5 = 74 passed).

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api_bookmark.py
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: bookmark annotation, filter, and toggle route

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend — star column, detail star, bookmarks filter

**Files:**
- Modify: `static/index.html`
- Modify: `static/styles.css`
- Modify: `static/app.js`

Verified manually against the running server (no pytest).

- [ ] **Step 1: `static/index.html` — header control and star column header**

(a) In the `.controls` div, add a Bookmarks toggle button. The current controls block is:

```html
    <div class="controls">
      <input id="search" type="search" placeholder="Search title / prompts…" />
      <select id="project"><option value="">All projects</option></select>
      <button id="rescan" title="Re-scan logs">↻ Rescan</button>
    </div>
```

Replace it with:

```html
    <div class="controls">
      <input id="search" type="search" placeholder="Search title / prompts…" />
      <select id="project"><option value="">All projects</option></select>
      <button id="bookmarks-toggle" title="Show only bookmarked">★ Bookmarks</button>
      <button id="rescan" title="Re-scan logs">↻ Rescan</button>
    </div>
```

(b) In the `<thead>` row, add a star header cell as the FIRST cell, before `<th data-sort="title">Title</th>`:

```html
            <th class="star-col"></th>
```

- [ ] **Step 2: `static/styles.css` — append**

```css
.star-col { width: 1.5rem; }
.star-btn {
  background: transparent; border: none; cursor: pointer; padding: 0;
  font-size: 1.1rem; line-height: 1; color: var(--muted);
}
.star-btn.on { color: #f5c518; }   /* gold filled star */
.star-btn:hover { color: #f5c518; }
#bookmarks-toggle.active { border-color: #f5c518; color: #f5c518; }
#detail-header .star-btn { font-size: 1.3rem; vertical-align: middle; }
```

- [ ] **Step 3: `static/app.js` — add bookmarkedOnly to state and a toggle function**

(a) Change the `state` initializer at the top. Current:

```javascript
let state = { sessions: [], sort: "last_activity", dir: -1, q: "", project: "" };
```

Replace with:

```javascript
let state = { sessions: [], sort: "last_activity", dir: -1, q: "", project: "", bookmarkedOnly: false };
```

(b) In `fetchSessions`, add the bookmarked param. Current:

```javascript
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.project) params.set("project", state.project);
  if (refresh) params.set("refresh", "true");
```

Replace with:

```javascript
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.project) params.set("project", state.project);
  if (state.bookmarkedOnly) params.set("bookmarked", "true");
  if (refresh) params.set("refresh", "true");
```

(c) Add a `toggleBookmark` function right after the `resume`/`showCopyFallback` block (near the other helpers):

```javascript
async function toggleBookmark(id, ev) {
  if (ev) ev.stopPropagation();
  try {
    const resp = await fetch(`/api/sessions/${encodeURIComponent(id)}/bookmark`,
                             { method: "POST" });
    const data = await resp.json();
    const s = state.sessions.find((x) => x.session_id === id);
    if (s) s.bookmarked = data.bookmarked;
    if (state.bookmarkedOnly && s && !data.bookmarked) {
      fetchSessions();   // it dropped out of the filtered view
    } else {
      render();
    }
  } catch (e) {
    showToast(`Bookmark failed: ${escapeHtml(String(e))}`);
  }
}

function starMarkup(s) {
  const on = s.bookmarked ? " on" : "";
  const glyph = s.bookmarked ? "★" : "☆";
  return `<button class="star-btn${on}" data-bm="${s.session_id}" title="Toggle bookmark">${glyph}</button>`;
}
```

- [ ] **Step 4: `static/app.js` — render the star cell and wire clicks**

(a) In `render()`, the row template currently starts:

```javascript
    return `<tr data-id="${s.session_id}">
      <td>${escapeHtml(s.title)}</td>
```

Replace those two lines with (adds the star cell first):

```javascript
    return `<tr data-id="${s.session_id}">
      <td class="star-col">${starMarkup(s)}</td>
      <td>${escapeHtml(s.title)}</td>
```

(b) Still in `render()`, after the existing `#rows .actions button` wiring loop, add a loop to wire the star buttons:

```javascript
  for (const btn of document.querySelectorAll("#rows .star-btn")) {
    btn.addEventListener("click", (ev) => toggleBookmark(btn.dataset.bm, ev));
  }
```

- [ ] **Step 5: `static/app.js` — star in the detail header**

In `showDetail(id)`, the header assignment currently begins:

```javascript
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
```

The `Transcript` object does not carry a `bookmarked` flag, so derive it from the in-memory list. Add this line immediately BEFORE that assignment:

```javascript
  const listed = state.sessions.find((x) => x.session_id === tr.session_id);
  const bmGlyph = listed && listed.bookmarked ? "★" : "☆";
  const bmOn = listed && listed.bookmarked ? " on" : "";
```

Then change the header assignment to prepend a star button — replace:

```javascript
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>
```

with:

```javascript
  $("#detail-header").innerHTML =
    `<button class="star-btn${bmOn}" id="detail-star" title="Toggle bookmark">${bmGlyph}</button>
     <strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>
```

Then, after the existing `#copyid` and resume/fork listeners in `showDetail`, add:

```javascript
  document.getElementById("detail-star").addEventListener("click", async (ev) => {
    await toggleBookmark(tr.session_id, ev);
    const s = state.sessions.find((x) => x.session_id === tr.session_id);
    const star = document.getElementById("detail-star");
    if (s && star) {
      star.textContent = s.bookmarked ? "★" : "☆";
      star.classList.toggle("on", s.bookmarked);
    }
  });
```

- [ ] **Step 6: `static/app.js` — wire the header Bookmarks toggle**

In `init()`, after the `#rescan` listener, add:

```javascript
  $("#bookmarks-toggle").addEventListener("click", () => {
    state.bookmarkedOnly = !state.bookmarkedOnly;
    $("#bookmarks-toggle").classList.toggle("active", state.bookmarkedOnly);
    fetchSessions();
  });
```

- [ ] **Step 7: Manual verification**

1. `pkill -f "uvicorn app.main" 2>/dev/null; sleep 1` (ignore errors).
2. `./run.sh >/tmp/bm.log 2>&1 &` ; sleep 3.
3. Star column header present: `curl -s http://127.0.0.1:8800/static/index.html | grep -c 'star-col'` → expect at least `1`.
4. Star button rendered in JS: `curl -s http://127.0.0.1:8800/static/app.js | grep -c 'data-bm'` → expect `1`.
5. Toggle via API and confirm it reflects in the list:
```bash
ID=$(curl -s http://127.0.0.1:8800/api/sessions | python3 -c "import sys,json;print(json.load(sys.stdin)['sessions'][0]['session_id'])")
curl -s -X POST "http://127.0.0.1:8800/api/sessions/$ID/bookmark"   # {"bookmarked":true}
curl -s "http://127.0.0.1:8800/api/sessions?bookmarked=true" | python3 -c "import sys,json; d=json.load(sys.stdin); print('count:',len(d['sessions']),'first bookmarked:',d['sessions'][0]['bookmarked'])"
curl -s -X POST "http://127.0.0.1:8800/api/sessions/$ID/bookmark"   # back to {"bookmarked":false}
```
Expected: first POST prints `{"bookmarked":true}`; filtered list count ≥ 1 with `first bookmarked: True`; second POST prints `{"bookmarked":false}`. (This leaves bookmarks.json empty again.)
6. Stop the server: `pkill -f "uvicorn app.main"`.

- [ ] **Step 8: Commit**

```bash
git add static/index.html static/styles.css static/app.js
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: bookmark star column, detail star, and bookmarks filter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: README + full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append a "Bookmarks" section to `README.md`** (indented-code style to match the file)

```markdown
## Bookmarks

Click the star in the first column to bookmark a session — it turns gold (★)
when bookmarked, outlined (☆) when not. The same star appears in the transcript
header. Bookmarks are stored server-side in `bookmarks.json` (gitignored).

Use the **★ Bookmarks** toggle in the header to show only bookmarked sessions;
click it again to show all. Search, sort, and the project filter still apply.
```

- [ ] **Step 2: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green (74 passed).

- [ ] **Step 3: Commit**

```bash
git add README.md
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "docs: document bookmarks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Server-side `bookmarks.json` store (load/save/toggle, safe defaults) → Task 1 ✓
- `bookmarked` flag on SessionIndex → Task 2 ✓
- Annotate after cache write (orthogonal to index cache) → Task 3 (`list_sessions` sets flag after `build_index`) ✓
- `?bookmarked=true` filter → Task 3 ✓
- `POST …/bookmark` toggle with id validation/404 → Task 3 ✓
- First-column star, gold filled vs outline, toggle on click, stopPropagation → Task 4 ✓
- Detail-header star → Task 4 (Step 5) ✓
- Header "★ Bookmarks" filter toggle with active style → Task 4 (Steps 1,6) ✓
- Un-star in filtered view drops the row (refetch) → Task 4 (`toggleBookmark`) ✓
- `.gitignore` bookmarks.json → Task 1 ✓
- README → Task 5 ✓
- Error handling: malformed bookmarks file → empty set (Task 1); missing id → 404 (Task 3) ✓
- Tests: bookmarks store, models field, api (list flag/filter/toggle/404) → Tasks 1–3 ✓

No gaps found.

**Placeholder scan:** No TBD/TODO. All steps carry concrete code/commands.

**Type consistency:** `bookmarks.load(path) -> set[str]`, `save(path, ids)`, `toggle(path, id) -> bool` used consistently in Task 1 and Task 3 (`bookmarks.load(BOOKMARKS)`, `bookmarks.toggle(BOOKMARKS, session_id)`). `SessionIndex.bookmarked` (Task 2) is read in Task 3 (`s.bookmarked`) and the frontend (`s.bookmarked`, Task 4). Route `bookmark_session` returns `{"bookmarked": bool}`, which the frontend `toggleBookmark` reads as `data.bookmarked`. Frontend helpers `starMarkup(s)`, `toggleBookmark(id, ev)`, and `state.bookmarkedOnly` are referenced consistently across Task 4 steps. The detail star derives `bookmarked` from `state.sessions` because `Transcript` has no such field — correctly noted in Task 4 Step 5.
