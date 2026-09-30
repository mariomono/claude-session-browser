import { memo } from "react";
import type { ResumeMode, Transcript, TranscriptEntry as Entry } from "../types";
import { OutcomeBadge } from "./Badge";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
import { ContextMeter } from "./Meter";
import { StarButton } from "./StarButton";
import { TranscriptEntry } from "./TranscriptEntry";

/** The entry cards, memoised so header, toast and theme updates leave thousands of cards untouched. */
const EntryList = memo(function EntryList({ entries }: { entries: Entry[] }) {
  return (
    <div id="entries" className="transcript__entries">
      {entries.map((e, i) => (
        <TranscriptEntry key={i} e={e} />
      ))}
    </div>
  );
});

interface Props {
  transcript: Transcript;
  bookmarked: boolean;
  onBack: () => void;
  onResume: (id: string, mode: ResumeMode) => void;
  onToggleBookmark: () => void;
}

export function TranscriptView({ transcript: tr, bookmarked, onBack, onResume, onToggleBookmark }: Props) {
  return (
    <div id="detail-view" className="transcript">
      <div className="transcript__bar">
        <div className="transcript__bar-inner">
          <button id="back" type="button" className="btn btn--ghost" onClick={onBack}>
            <Icon name="back" />
            <span>Back</span>
          </button>

          <div className="transcript__heading">
            <div className="transcript__title-row">
              <StarButton on={bookmarked} onToggle={onToggleBookmark} size={18} />
              <h1 className="transcript__title" title={tr.title}>
                {tr.title}
              </h1>
            </div>
            <div className="transcript__meta">
              <OutcomeBadge outcome={tr.outcome} />
              {tr.cwd && (
                <span className="meta-item mono" title={tr.cwd}>
                  {tr.cwd}
                </span>
              )}
              {tr.model && <span className="meta-item mono">{tr.model}</span>}
              {tr.context_pct != null && <ContextMeter pct={tr.context_pct} tokens={tr.context_tokens} compact />}
              <span className="meta-item num">{tr.entries.length} entries</span>
            </div>
          </div>

          <div className="transcript__actions">
            <CopyButton text={tr.session_id} label="copy id" className="btn btn--ghost" />
            <button type="button" className="btn" onClick={() => onResume(tr.session_id, "fork")}>
              <Icon name="fork" />
              <span>Fork</span>
            </button>
            <button type="button" className="btn btn--primary" onClick={() => onResume(tr.session_id, "continue")}>
              <Icon name="play" />
              <span>Resume</span>
            </button>
          </div>
        </div>
      </div>

      <EntryList entries={tr.entries} />
    </div>
  );
}
