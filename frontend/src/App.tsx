import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as api from "./api";
import { AppHeader } from "./components/AppHeader";
import { Icon } from "./components/Icon";
import { SessionTable } from "./components/SessionTable";
import { StateMessage } from "./components/StateMessage";
import { Toast, type ToastState } from "./components/Toast";
import { TranscriptView } from "./components/TranscriptView";
import { sortSessions, type SortKey } from "./format";
import { useTheme } from "./theme";
import type { ResumeMode, SessionIndex, Transcript } from "./types";

const SEARCH_DEBOUNCE_MS = 250;
const TOAST_MS = 3000;

export default function App() {
  const [theme, setTheme] = useTheme();
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
  const [loading, setLoading] = useState(true);
  const [rescanning, setRescanning] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);

  const toastTimer = useRef<number | undefined>(undefined);
  const requestSeq = useRef(0);
  const listScroll = useRef(0);

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
      setLoading(true);
      setRescanning(refresh);
      try {
        const data = await api.listSessions({ q, project, bookmarkedOnly, refresh });
        if (seq !== requestSeq.current) return; // a newer request superseded this one
        setSessions(data.sessions);
        setProjects(data.projects);
        setLoaded(true);
        setLoadError(null);
      } catch (e) {
        if (seq === requestSeq.current) {
          setLoadError(String(e));
          showMessage(`Loading sessions failed: ${String(e)}`);
        }
      } finally {
        if (seq === requestSeq.current) {
          setLoading(false);
          setRescanning(false);
        }
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

  // Transcripts open at the top; the list comes back where it was left.
  useLayoutEffect(() => {
    window.scrollTo(0, detail ? 0 : listScroll.current);
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
            Launching <strong>{mode}</strong> for <span className="mono">{id}</span>…
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
    setOpeningId(id);
    let tr: Transcript | null = null;
    try {
      tr = await api.getTranscript(id);
    } catch {
      tr = null;
    }
    setOpeningId(null);
    if (!tr) {
      showMessage("Could not load session");
      return;
    }
    const listed = sessions.find((s) => s.session_id === tr.session_id);
    setDetailBookmarked(listed?.bookmarked ?? false);
    listScroll.current = window.scrollY;
    setDetail(tr);
  };

  const toggleDetailBookmark = async () => {
    if (!detail) return;
    const now = await toggleBookmark(detail.session_id);
    if (now !== undefined) setDetailBookmarked(now);
  };

  const filtered = q !== "" || project !== "" || bookmarkedOnly;
  const clearFilters = () => {
    setSearchInput("");
    setQ("");
    setProject("");
    setBookmarkedOnly(false);
  };

  let placeholder: ReactNode;
  if (loadError && sessions.length === 0) {
    placeholder = (
      <StateMessage
        icon="alert"
        tone="danger"
        title="Couldn't load sessions"
        action={
          <button type="button" className="btn" onClick={() => void loadSessions()}>
            <Icon name="refresh" />
            <span>Retry</span>
          </button>
        }
      >
        {loadError}
      </StateMessage>
    );
  } else if (filtered) {
    placeholder = (
      <StateMessage
        icon="filter"
        title="No sessions match"
        action={
          <button type="button" className="btn" onClick={clearFilters}>
            <Icon name="close" />
            <span>Clear filters</span>
          </button>
        }
      >
        Nothing fits the current search, project and bookmark filters.
      </StateMessage>
    );
  } else {
    placeholder = (
      <StateMessage
        icon="inbox"
        title="No sessions yet"
        action={
          <button type="button" className="btn" onClick={() => void loadSessions(true)}>
            <Icon name="refresh" />
            <span>Rescan</span>
          </button>
        }
      >
        Claude Code session logs show up here once they are scanned.
      </StateMessage>
    );
  }

  return (
    <>
      <AppHeader
        searchInput={searchInput}
        onSearchInput={setSearchInput}
        project={project}
        projects={projects}
        onProject={setProject}
        bookmarkedOnly={bookmarkedOnly}
        onToggleBookmarkedOnly={() => setBookmarkedOnly((v) => !v)}
        onRescan={() => void loadSessions(true)}
        loading={loading || openingId !== null}
        rescanning={rescanning}
        theme={theme}
        onTheme={setTheme}
      />

      <main className="app-main">
        {detail ? (
          <div key={`t-${detail.session_id}`} className="view view--transcript">
            <TranscriptView
              transcript={detail}
              bookmarked={detailBookmarked}
              onBack={() => setDetail(null)}
              onResume={resume}
              onToggleBookmark={toggleDetailBookmark}
            />
          </div>
        ) : (
          <div key="list" id="list-view" className="view view--list">
            <SessionTable
              sessions={sorted}
              sort={sort}
              dir={dir}
              onSort={onSort}
              onOpen={openDetail}
              onResume={resume}
              onToggleBookmark={toggleBookmark}
              openingId={openingId}
              skeleton={!loaded && !loadError}
              placeholder={placeholder}
            />
            <p id="count" className="list-footer muted num">
              {loaded ? `${sessions.length} sessions` : "Loading sessions…"}
            </p>
          </div>
        )}
      </main>
      <Toast toast={toast} onClose={() => setToast(null)} durationMs={TOAST_MS} />
    </>
  );
}
