import type { ResumeMode, Transcript, TranscriptEntry } from "../types";
import { StarButton } from "./StarButton";

interface Props {
  transcript: Transcript;
  bookmarked: boolean;
  onBack: () => void;
  onResume: (id: string, mode: ResumeMode) => void;
  onToggleBookmark: () => void;
}

const COLLAPSED_KINDS = new Set(["thinking", "tool_use", "tool_result"]);

function Entry({ e }: { e: TranscriptEntry }) {
  const cls = `entry ${e.role}${e.is_sidechain ? " sidechain" : ""}`;
  const label =
    e.kind === "tool_use" ? `tool: ${e.tool_name || ""}` : e.kind === "tool_result" ? "tool result" : e.role;
  const body = <pre>{e.content}</pre>;
  return (
    <div className={cls}>
      <div className="role">{label}</div>
      {COLLAPSED_KINDS.has(e.kind) ? (
        <details>
          <summary>{e.kind}</summary>
          {body}
        </details>
      ) : (
        body
      )}
    </div>
  );
}

export function TranscriptView({ transcript: tr, bookmarked, onBack, onResume, onToggleBookmark }: Props) {
  return (
    <div id="detail-view">
      <button id="back" onClick={onBack}>
        ← Back
      </button>
      <div id="detail-header">
        <StarButton on={bookmarked} onToggle={onToggleBookmark} /> <strong>{tr.title}</strong> · {tr.cwd || ""} ·{" "}
        {tr.model || ""} · {tr.context_pct != null ? `${tr.context_pct}%` : ""}{" "}
        <button onClick={() => navigator.clipboard.writeText(tr.session_id)}>copy id</button>
        <div className="resume-actions">
          <button onClick={() => onResume(tr.session_id, "continue")}>▸ Resume</button>{" "}
          <button onClick={() => onResume(tr.session_id, "fork")}>⑂ Fork</button>
        </div>
      </div>
      <div id="entries">
        {tr.entries.map((e, i) => (
          <Entry key={i} e={e} />
        ))}
      </div>
    </div>
  );
}
