/** Mirrors the backend data shapes (app/models.py). */

export type Outcome = "clean" | "interrupted" | "error" | "unknown";

export interface SessionIndex {
  session_id: string;
  title: string;
  first_prompt: string | null;
  last_prompt: string | null;
  cwd: string | null;
  git_branch: string | null;
  last_activity: string | null; // ISO timestamp string
  message_count: number;
  context_tokens: number | null;
  context_pct: number | null;
  window_size: number | null;
  model: string | null;
  outcome: string; // clean | interrupted | error | unknown
  compacted: boolean;
  bookmarked: boolean;
  unparsable_lines: number;
  file_mtime: number;
  file_size: number;
}

export interface TranscriptEntry {
  role: string; // user | assistant | system
  kind: string; // text | thinking | tool_use | tool_result | system_note
  content: string;
  tool_name: string | null;
  timestamp: string | null;
  is_sidechain: boolean;
}

export interface Transcript {
  session_id: string;
  title: string;
  cwd: string | null;
  model: string | null;
  context_tokens: number | null;
  context_pct: number | null;
  outcome: string;
  entries: TranscriptEntry[];
  unparsable_lines: number;
}

export interface SessionList {
  sessions: SessionIndex[];
  projects: string[];
}

export type ResumeMode = "continue" | "fork";

/** Launch result: `ok` with the spawned argv, or `ok: false` with the error. */
export interface ResumeResult {
  ok: boolean;
  command: string[];
  error?: string;
}

export interface BookmarkResult {
  bookmarked: boolean;
}
