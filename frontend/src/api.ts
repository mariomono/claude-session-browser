import type { BookmarkResult, ResumeMode, ResumeResult, SessionList, Transcript } from "./types";

const BASE = "/api/v1/sessions";

export interface SessionQuery {
  q: string;
  project: string;
  bookmarkedOnly: boolean;
  refresh?: boolean;
}

export async function listSessions(query: SessionQuery): Promise<SessionList> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.project) params.set("project", query.project);
  if (query.bookmarkedOnly) params.set("bookmarked", "true");
  if (query.refresh) params.set("refresh", "true");
  const resp = await fetch(`${BASE}?${params.toString()}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

/** Returns null when the session cannot be loaded (non-2xx response). */
export async function getTranscript(id: string): Promise<Transcript | null> {
  const resp = await fetch(`${BASE}/${encodeURIComponent(id)}`);
  if (!resp.ok) return null;
  return resp.json();
}

/**
 * Raw response of a resume request: the HTTP status plus the parsed body,
 * which is a ResumeResult on success or an error body (e.g. `{detail}`).
 */
export async function resumeSession(
  id: string,
  mode: ResumeMode,
): Promise<{ ok: boolean; status: number; data: Partial<ResumeResult> }> {
  const resp = await fetch(`${BASE}/${encodeURIComponent(id)}/resume?mode=${mode}`, {
    method: "POST",
  });
  const data = await resp.json();
  return { ok: resp.ok, status: resp.status, data };
}

export async function toggleBookmark(id: string): Promise<BookmarkResult> {
  const resp = await fetch(`${BASE}/${encodeURIComponent(id)}/bookmark`, { method: "POST" });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}
