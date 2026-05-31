let state = { sessions: [], sort: "last_activity", dir: -1, q: "", project: "" };

const $ = (sel) => document.querySelector(sel);

async function fetchSessions(refresh = false) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.project) params.set("project", state.project);
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

function render() {
  const rows = sortSessions().map((s) => {
    const compact = s.compacted ? " ⟳" : "";
    return `<tr data-id="${s.session_id}">
      <td>${escapeHtml(s.title)}</td>
      <td class="muted">${escapeHtml(s.cwd || "—")}<br><small>${escapeHtml(s.git_branch || "")}</small></td>
      <td class="desc">${escapeHtml(s.first_prompt || "")}
        <div class="last">${escapeHtml(s.last_prompt || "")}</div></td>
      <td>${badge(s.outcome)}<br><small class="muted">${recency(s.last_activity)} · ${sizeBucket(s.message_count)}${compact}</small></td>
      <td>${ctxCell(s)}</td>
      <td class="muted">${recency(s.last_activity)}</td>
    </tr>`;
  }).join("");
  $("#rows").innerHTML = rows;
  $("#count").textContent = `${state.sessions.length} sessions`;
  for (const tr of document.querySelectorAll("#rows tr")) {
    tr.addEventListener("click", () => showDetail(tr.dataset.id));
  }
}

async function showDetail(id) {
  const resp = await fetch("/api/sessions/" + encodeURIComponent(id));
  if (!resp.ok) { alert("Could not load session"); return; }
  const tr = await resp.json();
  $("#detail-header").innerHTML =
    `<strong>${escapeHtml(tr.title)}</strong> · ${escapeHtml(tr.cwd || "")} · ${escapeHtml(tr.model || "")}
     · ${tr.context_pct != null ? tr.context_pct + "%" : ""}
     <button id="copyid">copy id</button>`;
  $("#entries").innerHTML = tr.entries.map(renderEntry).join("");
  $("#copyid").addEventListener("click", () => navigator.clipboard.writeText(tr.session_id));
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
