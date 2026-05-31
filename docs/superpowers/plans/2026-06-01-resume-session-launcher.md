# Resume-Session Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-row resume action to the Claude Session Browser that opens a past session in a new WSL terminal running `claude --resume <id>` (continue or fork), with a copy-command fallback if the launch fails.

**Architecture:** A new `POST /api/sessions/{id}/resume` route resolves the session's cwd and calls `launcher.resume_session`, which builds an argv list from a configurable template (`config.json`, defaults to a plain WSL window via `cmd.exe /c start … wsl.exe`) and spawns it detached. Substitution is per-token so there is no shell-injection surface. The frontend adds resume/fork icons that POST to the route and show a toast, or a copy-the-command fallback on failure.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, httpx (TestClient). Frontend: vanilla HTML/CSS/JS. Runs in WSL2 (Ubuntu-24.04) with Windows interop (`cmd.exe`, `wsl.exe` on PATH).

**Conventions for every task:** Run tests with `.venv/bin/python -m pytest`. Commit after each task with `git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit` and append the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Work on `master`. The current suite has 45 passing tests before this plan.

---

## File Structure

- **Create `app/config.py`** — load `config.json` (template + distro) with safe defaults. One responsibility: configuration.
- **Create `app/launcher.py`** — build the resume argv and spawn it detached. One responsibility: turning (session, mode, config) into a launched process.
- **Create `config.example.json`** — committed documentation of the config format.
- **Modify `app/indexer.py`** — add `session_cwd(path)` (cheap early-exit cwd read).
- **Modify `app/main.py`** — add the resume route; load config at import.
- **Modify `static/index.html`, `static/app.js`, `static/styles.css`** — row icons, detail-header buttons, toast + copy fallback.
- **Modify `.gitignore`** — ignore `config.json`.
- **Tests:** `tests/test_config.py`, `tests/test_launcher.py`, `tests/test_api_resume.py`.

---

### Task 1: `session_cwd` helper in indexer

**Files:**
- Modify: `app/indexer.py` (append a function)
- Test: `tests/test_indexer_cache.py` (append tests)

- [ ] **Step 1: Append the failing tests to `tests/test_indexer_cache.py`**

```python
def test_session_cwd_returns_first_cwd(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(
        json.dumps({"type": "ai-title", "aiTitle": "x"}) + "\n"
        + json.dumps({"type": "user", "cwd": "/home/mario/projects/demo",
                      "message": {"role": "user", "content": "hi"}}) + "\n")
    assert indexer.session_cwd(f) == "/home/mario/projects/demo"


def test_session_cwd_none_when_absent(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    f = root / "p" / "s.jsonl"
    f.write_text(json.dumps({"type": "ai-title", "aiTitle": "x"}) + "\n")
    assert indexer.session_cwd(f) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_indexer_cache.py -v`
Expected: FAIL with `AttributeError: module 'app.indexer' has no attribute 'session_cwd'`.

- [ ] **Step 3: Append to `app/indexer.py`**

Add this import near the top of `app/indexer.py` if not already present (it imports `read_records` already; add `iter_records`):

```python
from .jsonl import iter_records, read_records
```

(Replace the existing `from .jsonl import read_records` line with the line above.)

Append at the end of `app/indexer.py`:

```python
def session_cwd(path: Path) -> str | None:
    """Return the first cwd recorded in a session file, reading lazily."""
    for r in iter_records(path):
        cwd = r.get("cwd")
        if cwd:
            return cwd
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_indexer_cache.py -v`
Expected: PASS (7 passed: 5 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
git add app/indexer.py tests/test_indexer_cache.py
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: session_cwd helper for cheap cwd lookup

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Config loader (`config.py`)

**Files:**
- Create: `app/config.py`
- Create: `config.example.json`
- Modify: `.gitignore`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test `tests/test_config.py`**

```python
import json
from app import config


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = config.load(tmp_path / "nope.json")
    assert cfg.distro == config.DEFAULT_DISTRO
    assert cfg.launch == config.DEFAULT_LAUNCH


def test_load_valid_file_overrides(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "Debian", "launch": ["echo", "{claude}"]}))
    cfg = config.load(p)
    assert cfg.distro == "Debian"
    assert cfg.launch == ["echo", "{claude}"]


def test_load_malformed_file_returns_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{ this is not json")
    cfg = config.load(p)
    assert cfg.distro == config.DEFAULT_DISTRO
    assert cfg.launch == config.DEFAULT_LAUNCH


def test_load_partial_file_fills_missing_keys(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"distro": "OnlyDistro"}))
    cfg = config.load(p)
    assert cfg.distro == "OnlyDistro"
    assert cfg.launch == config.DEFAULT_LAUNCH
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Implement `app/config.py`**

```python
"""Load the resume-launch configuration with safe defaults."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DISTRO = os.environ.get("WSL_DISTRO_NAME") or "Ubuntu-24.04"
DEFAULT_LAUNCH = [
    "cmd.exe", "/c", "start", "",
    "wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--",
    "bash", "-lic", "{claude}",
]


@dataclass
class Config:
    distro: str = DEFAULT_DISTRO
    launch: list[str] = field(default_factory=lambda: list(DEFAULT_LAUNCH))


def load(path: Path) -> Config:
    """Read config.json; fall back to defaults on missing/invalid file."""
    try:
        data = json.loads(Path(path).read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    distro = data.get("distro")
    launch = data.get("launch")
    return Config(
        distro=distro if isinstance(distro, str) and distro else DEFAULT_DISTRO,
        launch=launch if isinstance(launch, list) and launch else list(DEFAULT_LAUNCH),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Create `config.example.json`**

```json
{
  "distro": "Ubuntu-24.04",
  "launch": [
    "cmd.exe", "/c", "start", "",
    "wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--",
    "bash", "-lic", "{claude}"
  ]
}
```

- [ ] **Step 6: Add `config.json` to `.gitignore`**

Append a line `config.json` to `.gitignore` (keep existing entries).

- [ ] **Step 7: Commit**

```bash
git add app/config.py tests/test_config.py config.example.json .gitignore
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: launch config loader with safe defaults

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Launcher (`launcher.py`)

**Files:**
- Create: `app/launcher.py`
- Test: `tests/test_launcher.py`

- [ ] **Step 1: Write the failing test `tests/test_launcher.py`**

```python
from app import launcher
from app.config import Config


def test_build_claude_cmd_continue():
    assert launcher.build_claude_cmd("abc123", "continue") == "claude --resume abc123"


def test_build_claude_cmd_fork():
    assert launcher.build_claude_cmd("abc123", "fork") == "claude --resume abc123 --fork-session"


def test_build_command_substitutes_tokens():
    template = ["wsl.exe", "-d", "{distro}", "--cd", "{cwd}", "--", "bash", "-lic", "{claude}"]
    cmd = launcher.build_command(template, "Ubuntu-24.04", "/home/m/proj", "abc123", "continue")
    assert cmd == ["wsl.exe", "-d", "Ubuntu-24.04", "--cd", "/home/m/proj",
                   "--", "bash", "-lic", "claude --resume abc123"]


def test_build_command_cwd_with_spaces_stays_one_token():
    template = ["wsl.exe", "--cd", "{cwd}"]
    cmd = launcher.build_command(template, "D", "/home/m/my proj/x", "id1", "continue")
    assert cmd == ["wsl.exe", "--cd", "/home/m/my proj/x"]
    assert len(cmd) == 3  # the space did not create an extra argument


def test_resume_session_ok_records_command():
    calls = []
    cfg = Config(distro="Ubuntu-24.04", launch=["wsl.exe", "--cd", "{cwd}", "--", "bash", "-lic", "{claude}"])
    result = launcher.resume_session("abc123", "/home/m/proj", "continue", cfg,
                                     spawn=lambda c: calls.append(c))
    assert result["ok"] is True
    assert calls == [result["command"]]
    assert "claude --resume abc123" in result["command"]


def test_resume_session_fork_includes_flag():
    cfg = Config(distro="D", launch=["bash", "-lic", "{claude}"])
    result = launcher.resume_session("abc123", "/cwd", "fork", cfg, spawn=lambda c: None)
    assert "claude --resume abc123 --fork-session" in result["command"]


def test_resume_session_spawn_failure_returns_error():
    def boom(cmd):
        raise FileNotFoundError("cmd.exe not found")
    cfg = Config(distro="D", launch=["cmd.exe", "{claude}"])
    result = launcher.resume_session("abc123", "/cwd", "continue", cfg, spawn=boom)
    assert result["ok"] is False
    assert "cmd.exe not found" in result["error"]
    assert result["command"][0] == "cmd.exe"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_launcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.launcher'`.

- [ ] **Step 3: Implement `app/launcher.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_launcher.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app/launcher.py tests/test_launcher.py
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: resume-launch command builder and detached spawner

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Resume route in `main.py`

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api_resume.py`

- [ ] **Step 1: Write the failing test `tests/test_api_resume.py`**

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
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "CACHE", tmp_path / "cache.json")
    # capture spawned commands instead of launching anything
    spawned = []
    monkeypatch.setattr(main.launcher, "_default_spawn", lambda c: spawned.append(c))
    return TestClient(main.app), spawned


def test_resume_continue(tmp_path, monkeypatch):
    client, spawned = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "claude --resume sess1" in data["command"]
    assert "/home/mario/projects/demo" in data["command"]
    assert spawned and spawned[0] == data["command"]


def test_resume_fork(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    resp = client.post("/api/sessions/sess1/resume?mode=fork")
    assert resp.status_code == 200
    assert "claude --resume sess1 --fork-session" in resp.json()["command"]


def test_resume_bad_mode(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/sess1/resume?mode=nonsense").status_code == 400


def test_resume_missing_session(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    assert client.post("/api/sessions/missing/resume").status_code == 404


def test_resume_spawn_failure_returns_ok_false(tmp_path, monkeypatch):
    client, _ = _make_client(tmp_path, monkeypatch)
    from app import main

    def boom(cmd):
        raise FileNotFoundError("no cmd.exe")
    monkeypatch.setattr(main.launcher, "_default_spawn", boom)
    resp = client.post("/api/sessions/sess1/resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "no cmd.exe" in data["error"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_resume.py -v`
Expected: FAIL (404 from the not-yet-existing POST route, or assertion errors).

- [ ] **Step 3: Modify `app/main.py`**

(a) Update the imports/constants block at the top. Replace:

```python
from . import indexer, parser
```

with:

```python
from . import config, indexer, launcher, parser
```

(b) After the `STATIC = _BASE / "static"` line, add:

```python
CONFIG = config.load(_BASE / "config.json")
```

(c) Also add `Path` is already imported and `HTTPException` is already imported. Add this import at the top with the other stdlib/fastapi imports:

```python
from fastapi import FastAPI, HTTPException, Query
```

(Replace the existing `from fastapi import FastAPI, HTTPException` line with the line above.)

(d) Add the route immediately after the existing `get_session` route:

```python
@app.post("/api/sessions/{session_id}/resume")
def resume_session(session_id: str,
                   mode: str = Query("continue")):
    if mode not in ("continue", "fork"):
        raise HTTPException(status_code=400, detail="mode must be continue or fork")
    path = indexer.find_session_path(ROOT, session_id)
    if not path:
        raise HTTPException(status_code=404, detail="session not found")
    cwd = indexer.session_cwd(path) or str(Path.home())
    return launcher.resume_session(session_id, cwd, mode, CONFIG)
```

Note: the route calls `launcher.resume_session(... )` which uses `launcher._default_spawn`; tests monkeypatch `main.launcher._default_spawn`, so this wiring is required for spawn capture to work.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api_resume.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green (45 prior + 2 + 4 + 7 + 5 = 63 passed).

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api_resume.py
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: POST /api/sessions/{id}/resume route

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Frontend — resume/fork icons, toast, copy fallback

**Files:**
- Modify: `static/index.html`
- Modify: `static/styles.css`
- Modify: `static/app.js`

Verified manually against the running server (no pytest).

- [ ] **Step 1: Add a header cell and toast container to `static/index.html`**

In the `<thead>` table row, add an empty header cell at the END (after the `Last active` th):

```html
            <th>Resume</th>
```

Immediately before the closing `</body>` (after the `<script>` tag is fine, but place it before the script tag), add a toast container inside `<main>` — specifically, add this as the LAST element inside `<main>`, right before `</main>`:

```html
    <div id="toast" hidden></div>
```

- [ ] **Step 2: Add styles to `static/styles.css`**

Append:

```css
.actions { white-space: nowrap; }
.actions button {
  background: transparent; border: 1px solid var(--line); border-radius: 6px;
  padding: 0.15rem 0.4rem; margin-right: 0.25rem; cursor: pointer; color: var(--fg);
}
.actions button:hover { border-color: var(--accent); color: var(--accent); }
#toast {
  position: fixed; right: 1rem; bottom: 1rem; max-width: 32rem;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 0.6rem 0.8rem; color: var(--fg); z-index: 20;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
#toast .cmd { display: block; margin: 0.4rem 0; color: var(--muted);
  white-space: pre-wrap; word-break: break-all; font-size: 0.8rem; }
#toast button { margin-right: 0.4rem; }
#detail-header .resume-actions { margin-top: 0.5rem; }
```

- [ ] **Step 3: Add the resume logic to `static/app.js`**

Add these functions near the other helpers (e.g. after the `escapeHtml` function):

```javascript
function showToast(html, sticky = false) {
  const t = $("#toast");
  t.innerHTML = html;
  t.hidden = false;
  if (!sticky) {
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.hidden = true; }, 3000);
  }
}

async function resume(id, mode, ev) {
  if (ev) ev.stopPropagation();
  try {
    const resp = await fetch(`/api/sessions/${encodeURIComponent(id)}/resume?mode=${mode}`,
                             { method: "POST" });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      showToast(`Launching <strong>${escapeHtml(mode)}</strong> for ${escapeHtml(id)}…`);
    } else {
      showCopyFallback(data.command || [], data.error || `HTTP ${resp.status}`);
    }
  } catch (e) {
    showCopyFallback([], String(e));
  }
}

function showCopyFallback(command, error) {
  const cmdStr = Array.isArray(command) ? command.join(" ") : "";
  showToast(
    `Couldn't launch a terminal (${escapeHtml(error)}).<br>Run this yourself:` +
    `<code class="cmd">${escapeHtml(cmdStr)}</code>` +
    `<button id="toast-copy">Copy</button><button id="toast-close">Close</button>`,
    true);
  const copy = document.getElementById("toast-copy");
  if (copy) copy.addEventListener("click", () => navigator.clipboard.writeText(cmdStr));
  const close = document.getElementById("toast-close");
  if (close) close.addEventListener("click", () => { $("#toast").hidden = true; });
}
```

- [ ] **Step 4: Render the row action cell in `static/app.js`**

In the `render()` function, the row template currently ends with the `Last active` cell:

```javascript
      <td class="muted">${recency(s.last_activity)}</td>
    </tr>`;
```

Replace that with an added actions cell:

```javascript
      <td class="muted">${recency(s.last_activity)}</td>
      <td class="actions">
        <button title="Resume (continue)" data-act="resume" data-id="${s.session_id}">▸</button>
        <button title="Fork into new session" data-act="fork" data-id="${s.session_id}">⑂</button>
      </td>
    </tr>`;
```

Then, still in `render()`, AFTER the existing loop that wires row-click handlers, add wiring for the action buttons (which stops propagation so the row's transcript handler does not also fire):

```javascript
  for (const btn of document.querySelectorAll("#rows .actions button")) {
    btn.addEventListener("click", (ev) => {
      const mode = btn.dataset.act === "fork" ? "fork" : "continue";
      resume(btn.dataset.id, mode, ev);
    });
  }
```

- [ ] **Step 5: Add resume/fork buttons to the detail header in `static/app.js`**

In `showDetail(id)`, the header is set via `$("#detail-header").innerHTML = ...`. Append a resume-actions block. Replace the existing assignment:

```javascript
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>`;
```

with:

```javascript
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>
     <div class="resume-actions">
       <button id="detail-resume">▸ Resume</button>
       <button id="detail-fork">⑂ Fork</button>
     </div>`;
```

Then, still in `showDetail`, after the existing `#copyid` click listener, add:

```javascript
  document.getElementById("detail-resume")
    .addEventListener("click", (ev) => resume(tr.session_id, "continue", ev));
  document.getElementById("detail-fork")
    .addEventListener("click", (ev) => resume(tr.session_id, "fork", ev));
```

- [ ] **Step 6: Manual verification**

1. Ensure no stale server: `pkill -f "uvicorn app.main" 2>/dev/null; sleep 1` (ignore errors).
2. Start: `./run.sh &` ; wait ~3s.
3. Verify the resume endpoint works WITHOUT actually opening windows by checking the command is built and returned. Because the default spawn would really open a terminal, test failure-path command construction with a temporarily bad config is overkill; instead verify the happy path returns ok and a sane command:
```bash
ID=$(curl -s http://127.0.0.1:8800/api/sessions | python3 -c "import sys,json;print(json.load(sys.stdin)['sessions'][0]['session_id'])")
curl -s -X POST "http://127.0.0.1:8800/api/sessions/$ID/resume?mode=continue" | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok:',d['ok']); print('cmd:',' '.join(d['command']))"
```
Expected: `ok: True` and a command containing `wsl.exe`, `--cd <real cwd>`, and `claude --resume <ID>`. (This WILL open a real WSL window since the spawn runs — that is the feature working. Close the window afterward.)
4. Verify bad mode → 400:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://127.0.0.1:8800/api/sessions/$ID/resume?mode=bogus"
```
Expected: `400`.
5. Verify the page renders the icons: `curl -s http://127.0.0.1:8800/static/app.js | grep -c 'data-act="fork"'` → expect `1`.
6. Stop the server: `pkill -f "uvicorn app.main"`.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/styles.css static/app.js
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "feat: resume/fork row icons with toast and copy fallback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: README + full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Resume" section to `README.md`**

Append this section to `README.md` (indented-code style to avoid nested fences):

```markdown
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
```

- [ ] **Step 2: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all green (63 passed).

- [ ] **Step 3: Commit**

```bash
git add README.md
git -c user.name='Claude' -c user.email='noreply@anthropic.com' commit -m "docs: document session resume actions and config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Configurable template, default plain WSL window, safe defaults → Task 2 (`config.py`, `config.example.json`) ✓
- argv-list substitution / no shell injection → Task 3 (`build_command` per-token) + tests ✓
- continue vs fork modes → Task 3 (`build_claude_cmd`) + Task 4 (route `mode`) + Task 5 (two icons) ✓
- cheap cwd resolution → Task 1 (`session_cwd`) ✓
- POST resume route, 400 bad mode, 404 missing, always-200 with ok/command/error → Task 4 ✓
- spawn detached, failure surfaced → Task 3 (`_default_spawn`, `resume_session`) ✓
- row icons + detail-header buttons + stopPropagation → Task 5 ✓
- toast + copy fallback (Approach B) → Task 5 (`showCopyFallback`) ✓
- config in project file, gitignored → Task 2 (.gitignore) ✓
- README/docs → Task 6 ✓
- Error handling: malformed config → defaults (Task 2), missing cwd → home (Task 4), spawn failure (Task 3) ✓
- Testing: config, launcher, api_resume, plus session_cwd → Tasks 1–4 ✓

No gaps found.

**Placeholder scan:** No TBD/TODO. All steps contain concrete code/commands. The `{distro}`/`{cwd}`/`{claude}` strings are intentional template placeholders, not plan placeholders.

**Type consistency:** `config.load(path) -> Config` with `.distro`/`.launch`; `launcher.build_claude_cmd(session_id, mode)`, `build_command(template, distro, cwd, session_id, mode)`, `resume_session(session_id, cwd, mode, config, spawn=_default_spawn) -> {ok, command, error?}`; `indexer.session_cwd(path) -> str|None`; route `resume_session(session_id, mode)`. Names/signatures are consistent across Tasks 1–5 and the tests (tests monkeypatch `main.launcher._default_spawn`, which Task 3 defines and Task 4 uses indirectly). The frontend `resume(id, mode, ev)`, `showToast`, `showCopyFallback` are referenced consistently in Task 5.
