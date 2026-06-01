let state = { sessions: [], sort: "last_activity", dir: -1, q: "", project: "", bookmarkedOnly: false };

const $ = (sel) => document.querySelector(sel);

async function fetchSessions(refresh = false) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.project) params.set("project", state.project);
  if (state.bookmarkedOnly) params.set("bookmarked", "true");
  if (refresh) params.set("refresh", "true");
  const resp = await fetch("/api/sessions?" + params.toString());
  const data = await resp.json();
  state.sessions = data.sessions;
  populateProjects(data.projects);
  render();
}

function populateProjects(projects) {
  const sel = $("#project");
  if (sel.options.length > 1) return; // already populated
  for (const p of projects) {
    const o = document.createElement("option");
    o.value = p; o.textContent = p;
    sel.appendChild(o);
  }
}

function sortSessions() {
  const { sort, dir } = state;
  return [...state.sessions].sort((a, b) => {
    const av = a[sort] ?? "", bv = b[sort] ?? "";
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
}

function badge(outcome) {
  const safe = escapeHtml(outcome);
  return `<span class="badge ${safe}">${safe}</span>`;
}

function recency(ts) {
  if (!ts) return "—";
  const d = new Date(ts), now = new Date();
  const days = (now - d) / 86400000;
  if (days < 1) return "today";
  if (days < 7) return "this week";
  if (days < 31) return "this month";
  return d.toISOString().slice(0, 10);
}

function sizeBucket(n) {
  if (n <= 10) return "S";
  if (n <= 60) return "M";
  return "L";
}

function ctxCell(s) {
  if (s.context_pct == null) return '<span class="muted">—</span>';
  const high = s.context_pct >= 70 ? " high" : "";
  const k = Math.round(s.context_tokens / 1000);
  return `<div class="bar${high}"><span style="width:${Math.min(100, s.context_pct)}%"></span></div>
          <span class="muted">${s.context_pct}% · ${k}k</span>`;
}

function escapeHtml(str) {
  return (str ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

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

function render() {
  const rows = sortSessions().map((s) => {
    const compact = s.compacted ? " ⟳" : "";
    return `<tr data-id="${s.session_id}">
      <td class="star-col">${starMarkup(s)}</td>
      <td>${escapeHtml(s.title)}</td>
      <td class="muted">${escapeHtml(s.cwd || "—")}<br><small>${escapeHtml(s.git_branch || "")}</small></td>
      <td class="desc">${escapeHtml(s.first_prompt || "")}
        <div class="last">${escapeHtml(s.last_prompt || "")}</div></td>
      <td>${badge(s.outcome)}<br><small class="muted">${recency(s.last_activity)} · ${sizeBucket(s.message_count)}${compact}</small></td>
      <td>${ctxCell(s)}</td>
      <td class="muted">${recency(s.last_activity)}</td>
      <td class="actions">
        <button title="Resume (continue)" data-act="resume" data-id="${s.session_id}">▸</button>
        <button title="Fork into new session" data-act="fork" data-id="${s.session_id}">⑂</button>
      </td>
    </tr>`;
  }).join("");
  $("#rows").innerHTML = rows;
  $("#count").textContent = `${state.sessions.length} sessions`;
  for (const tr of document.querySelectorAll("#rows tr")) {
    tr.addEventListener("click", () => showDetail(tr.dataset.id));
  }
  for (const btn of document.querySelectorAll("#rows .actions button")) {
    btn.addEventListener("click", (ev) => {
      const mode = btn.dataset.act === "fork" ? "fork" : "continue";
      resume(btn.dataset.id, mode, ev);
    });
  }
  for (const btn of document.querySelectorAll("#rows .star-btn")) {
    btn.addEventListener("click", (ev) => toggleBookmark(btn.dataset.bm, ev));
  }
}

async function showDetail(id) {
  const resp = await fetch("/api/sessions/" + encodeURIComponent(id));
  if (!resp.ok) { alert("Could not load session"); return; }
  const tr = await resp.json();
  const listed = state.sessions.find((x) => x.session_id === tr.session_id);
  const bmGlyph = listed && listed.bookmarked ? "★" : "☆";
  const bmOn = listed && listed.bookmarked ? " on" : "";
  $("#detail-header").innerHTML =
    `<button class="star-btn${bmOn}" id="detail-star" title="Toggle bookmark">${bmGlyph}</button>
     <strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>
     <div class="resume-actions">
       <button id="detail-resume">▸ Resume</button>
       <button id="detail-fork">⑂ Fork</button>
     </div>`;
  $("#entries").innerHTML = tr.entries.map(renderEntry).join("");
  $("#copyid").addEventListener("click", () => navigator.clipboard.writeText(tr.session_id));
  document.getElementById("detail-resume")
    .addEventListener("click", (ev) => resume(tr.session_id, "continue", ev));
  document.getElementById("detail-fork")
    .addEventListener("click", (ev) => resume(tr.session_id, "fork", ev));
  document.getElementById("detail-star").addEventListener("click", async (ev) => {
    await toggleBookmark(tr.session_id, ev);
    const s = state.sessions.find((x) => x.session_id === tr.session_id);
    const star = document.getElementById("detail-star");
    if (s && star) {
      star.textContent = s.bookmarked ? "★" : "☆";
      star.classList.toggle("on", s.bookmarked);
    }
  });
  $("#list-view").hidden = true;
  $("#detail-view").hidden = false;
  window.scrollTo(0, 0);
}

function renderEntry(e) {
  const cls = `entry ${e.role}${e.is_sidechain ? " sidechain" : ""}`;
  const label = e.kind === "tool_use" ? `tool: ${escapeHtml(e.tool_name || "")}`
              : e.kind === "tool_result" ? "tool result"
              : e.role;
  const body = `<pre>${escapeHtml(e.content)}</pre>`;
  if (e.kind === "thinking" || e.kind === "tool_use" || e.kind === "tool_result") {
    return `<div class="${cls}"><div class="role">${label}</div>
      <details><summary>${e.kind}</summary>${body}</details></div>`;
  }
  return `<div class="${cls}"><div class="role">${label}</div>${body}</div>`;
}

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function init() {
  $("#search").addEventListener("input", debounce((e) => {
    state.q = e.target.value; fetchSessions();
  }, 250));
  $("#project").addEventListener("change", (e) => {
    state.project = e.target.value; fetchSessions();
  });
  $("#rescan").addEventListener("click", () => fetchSessions(true));
  $("#bookmarks-toggle").addEventListener("click", () => {
    state.bookmarkedOnly = !state.bookmarkedOnly;
    $("#bookmarks-toggle").classList.toggle("active", state.bookmarkedOnly);
    fetchSessions();
  });
  $("#back").addEventListener("click", () => {
    $("#detail-view").hidden = true; $("#list-view").hidden = false;
  });
  for (const th of document.querySelectorAll("th[data-sort]")) {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.dir = state.sort === key ? -state.dir : -1;
      state.sort = key;
      render();
    });
  }
  fetchSessions();
}

init();
