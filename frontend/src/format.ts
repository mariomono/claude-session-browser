import type { SessionIndex } from "./types";

export type SortKey = "title" | "cwd" | "outcome" | "context_pct" | "last_activity";

export function recency(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  const days = (Date.now() - d.getTime()) / 86400000;
  if (days < 1) return "today";
  if (days < 7) return "this week";
  if (days < 31) return "this month";
  return d.toISOString().slice(0, 10);
}

/** Local wall-clock time (HH:MM:SS) of an ISO timestamp, or "" when missing/invalid. */
export function clockTime(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function sizeBucket(n: number): "S" | "M" | "L" {
  if (n <= 10) return "S";
  if (n <= 60) return "M";
  return "L";
}

/** Sort by one column; missing values compare as "" (so they sort first ascending). */
export function sortSessions(sessions: SessionIndex[], key: SortKey, dir: 1 | -1): SessionIndex[] {
  return [...sessions].sort((a, b) => {
    const av: string | number = a[key] ?? "";
    const bv: string | number = b[key] ?? "";
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
}
