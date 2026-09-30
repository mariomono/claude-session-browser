import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as api from "./api";
import { SessionTable } from "./components/SessionTable";
import { Toast, type ToastState } from "./components/Toast";
import { TranscriptView } from "./components/TranscriptView";
import { sortSessions, type SortKey } from "./format";
import type { ResumeMode, SessionIndex, Transcript } from "./types";

const SEARCH_DEBOUNCE_MS = 250;
const TOAST_MS = 3000;

export default function App() {
  const [sessions, setSessions] = useState<SessionIndex[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [sort, setSort] = useState<SortKey>("last_activity");
  const [dir, setDir] = useState<1 | -1>(-1);
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [project, setProject] = useState("");
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false);
  const [detail, setDetail] = useState<Transcript | null>(null);
  const [detailBookmarked, setDetailBookmarked] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  const toastTimer = useRef<number | undefined>(undefined);
  const requestSeq = useRef(0);

  const showMessage = useCallback((content: ReactNode) => {
    window.clearTimeout(toastTimer.current);
    setToast({ kind: "message", content });
    toastTimer.current = window.setTimeout(() => setToast(null), TOAST_MS);
  }, []);

  const showLaunchFailed = useCallback((command: string[], error: string) => {
    window.clearTimeout(toastTimer.current);
    setToast({ kind: "launch-failed", command, error });
  }, []);

  const loadSessions = useCallback(
    async (refresh = false) => {
      const seq = ++requestSeq.current;
      try {
        const data = await api.listSessions({ q, project, bookmarkedOnly, refresh });
        if (seq !== requestSeq.current) return; // a newer request superseded this one
        setSessions(data.sessions);
        setProjects(data.projects);
      } catch (e) {
        if (seq === requestSeq.current) showMessage(`Loading sessions failed: ${String(e)}`);
      }
    },
    [q, project, bookmarkedOnly, showMessage],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    const t = window.setTimeout(() => setQ(searchInput), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    if (detail) window.scrollTo(0, 0);
  }, [detail]);

  useEffect(() => () => window.clearTimeout(toastTimer.current), []);

  const sorted = useMemo(() => sortSessions(sessions, sort, dir), [sessions, sort, dir]);

  const onSort = (key: SortKey) => {
    setDir(sort === key ? (-dir as 1 | -1) : -1);
    setSort(key);
  };

  const resume = async (id: string, mode: ResumeMode) => {
    try {
      const { ok, status, data } = await api.resumeSession(id, mode);
      if (ok && data.ok) {
        showMessage(
          <>
            Launching <strong>{mode}</strong> for {id}…
          </>,
        );
      } else {
        showLaunchFailed(data.command || [], data.error || `HTTP ${status}`);
      }
    } catch (e) {
      showLaunchFailed([], String(e));
    }
  };

  /** Toggle a bookmark; returns the new state, or undefined if the request failed. */
  const toggleBookmark = async (id: string): Promise<boolean | undefined> => {
    try {
      const { bookmarked } = await api.toggleBookmark(id);
      const listed = sessions.some((s) => s.session_id === id);
      if (bookmarkedOnly && listed && !bookmarked) {
        void loadSessions(); // it dropped out of the filtered view
      } else {
        setSessions((prev) => prev.map((s) => (s.session_id === id ? { ...s, bookmarked } : s)));
      }
      return bookmarked;
    } catch (e) {
      showMessage(`Bookmark failed: ${String(e)}`);
      return undefined;
    }
  };

  const openDetail = async (id: string) => {
    let tr: Transcript | null = null;
    try {
      tr = await api.getTranscript(id);
    } catch {
      tr = null;
    }
    if (!tr) {
      alert("Could not load session");
      return;
    }
    const listed = sessions.find((s) => s.session_id === tr.session_id);
    setDetailBookmarked(listed?.bookmarked ?? false);
    setDetail(tr);
  };

  const toggleDetailBookmark = async () => {
    if (!detail) return;
    const now = await toggleBookmark(detail.session_id);
    if (now !== undefined) setDetailBookmarked(now);
  };

  return (
    <>
      <header>
        <h1>Claude Sessions</h1>
        <div className="controls">
          <input
            id="search"
            type="search"
            placeholder="Search title / prompts…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <select id="project" value={project} onChange={(e) => setProject(e.target.value)}>
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button
            id="bookmarks-toggle"
            className={bookmarkedOnly ? "active" : undefined}
            title="Show only bookmarked"
            onClick={() => setBookmarkedOnly((v) => !v)}
          >
            ★ Bookmarks
          </button>
          <button id="rescan" title="Re-scan logs" onClick={() => void loadSessions(true)}>
            ↻ Rescan
          </button>
        </div>
      </header>

      <main>
        {detail ? (
          <TranscriptView
            transcript={detail}
            bookmarked={detailBookmarked}
            onBack={() => setDetail(null)}
            onResume={resume}
            onToggleBookmark={toggleDetailBookmark}
          />
        ) : (
          <div id="list-view">
            <SessionTable
              sessions={sorted}
              onSort={onSort}
              onOpen={openDetail}
              onResume={resume}
              onToggleBookmark={toggleBookmark}
            />
            <p id="count" className="muted">
              {sessions.length} sessions
            </p>
          </div>
        )}
        {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
      </main>
    </>
  );
}
