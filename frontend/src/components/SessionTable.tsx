import type { MouseEvent } from "react";
import { recency, sizeBucket, type SortKey } from "../format";
import type { ResumeMode, SessionIndex } from "../types";
import { StarButton } from "./StarButton";

interface Props {
  sessions: SessionIndex[];
  onSort: (key: SortKey) => void;
  onOpen: (id: string) => void;
  onResume: (id: string, mode: ResumeMode) => void;
  onToggleBookmark: (id: string) => void;
}

function ContextCell({ s }: { s: SessionIndex }) {
  if (s.context_pct == null) return <span className="muted">—</span>;
  const k = Math.round((s.context_tokens ?? 0) / 1000);
  return (
    <>
      <div className={`bar${s.context_pct >= 70 ? " high" : ""}`}>
        <span style={{ width: `${Math.min(100, s.context_pct)}%` }} />
      </div>
      <span className="muted">
        {s.context_pct}% · {k}k
      </span>
    </>
  );
}

function SortableTh({ k, label, onSort }: { k: SortKey; label: string; onSort: (key: SortKey) => void }) {
  return (
    <th data-sort={k} onClick={() => onSort(k)}>
      {label}
    </th>
  );
}

export function SessionTable({ sessions, onSort, onOpen, onResume, onToggleBookmark }: Props) {
  const stop = (fn: () => void) => (ev: MouseEvent) => {
    ev.stopPropagation();
    fn();
  };

  return (
    <table id="sessions">
      <thead>
        <tr>
          <th className="star-col"></th>
          <SortableTh k="title" label="Title" onSort={onSort} />
          <SortableTh k="cwd" label="Project" onSort={onSort} />
          <th>Description</th>
          <SortableTh k="outcome" label="State" onSort={onSort} />
          <SortableTh k="context_pct" label="Context" onSort={onSort} />
          <SortableTh k="last_activity" label="Last active" onSort={onSort} />
          <th>Resume</th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((s) => (
          <tr key={s.session_id} onClick={() => onOpen(s.session_id)}>
            <td className="star-col">
              <StarButton on={s.bookmarked} onToggle={stop(() => onToggleBookmark(s.session_id))} />
            </td>
            <td>{s.title}</td>
            <td className="muted">
              {s.cwd || "—"}
              <br />
              <small>{s.git_branch || ""}</small>
            </td>
            <td className="desc">
              {s.first_prompt || ""}
              <div className="last">{s.last_prompt || ""}</div>
            </td>
            <td>
              <span className={`badge ${s.outcome}`}>{s.outcome}</span>
              <br />
              <small className="muted">
                {recency(s.last_activity)} · {sizeBucket(s.message_count)}
                {s.compacted ? " ⟳" : ""}
              </small>
            </td>
            <td>
              <ContextCell s={s} />
            </td>
            <td className="muted">{recency(s.last_activity)}</td>
            <td className="actions">
              <button title="Resume (continue)" onClick={stop(() => onResume(s.session_id, "continue"))}>
                ▸
              </button>
              <button title="Fork into new session" onClick={stop(() => onResume(s.session_id, "fork"))}>
                ⑂
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
