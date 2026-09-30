import { memo, useEffect, useState } from "react";
import type { ResumeMode, Transcript, TranscriptEntry as Entry } from "../types";
import { OutcomeBadge } from "./Badge";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
import { ContextMeter } from "./Meter";
import { StarButton } from "./StarButton";
import { TranscriptEntry } from "./TranscriptEntry";

/** Cards mounted with the view itself: enough to fill the first screen. */
const FIRST_CHUNK = 60;
/** Cards mounted per idle slot afterwards. */
const CHUNK = 250;
/** Longest wait for an idle slot before a chunk is mounted anyway. */
const IDLE_TIMEOUT_MS = 100;

/** Run `fn` when the main thread is idle (next macrotask where requestIdleCallback is missing); returns a canceller. */
function whenIdle(fn: () => void): () => void {
  if (typeof window.requestIdleCallback === "function") {
    const handle = window.requestIdleCallback(fn, { timeout: IDLE_TIMEOUT_MS });
    return () => window.cancelIdleCallback(handle);
  }
  const handle = window.setTimeout(fn, 16);
  return () => window.clearTimeout(handle);
}

/** One slice of cards; memoised, so mounting the next slice leaves the earlier ones untouched. */
const EntryChunk = memo(function EntryChunk({ entries, start, end }: { entries: Entry[]; start: number; end: number }) {
  return (
    <>
      {entries.slice(start, end).map((e, i) => (
        <TranscriptEntry key={start + i} e={e} />
      ))}
    </>
  );
});

/**
 * The entry cards, memoised so header, toast and theme updates leave thousands of cards untouched.
 * Long transcripts mount progressively: the first screenful with the view, the rest in idle-time
 * chunks appended below it, so the view appears at once and stays responsive.
 */
const EntryList = memo(function EntryList({ entries }: { entries: Entry[] }) {
  const [shown, setShown] = useState(() => Math.min(entries.length, FIRST_CHUNK));

  useEffect(() => {
    if (shown >= entries.length) return;
    return whenIdle(() => setShown(Math.min(entries.length, shown + CHUNK)));
  }, [shown, entries.length]);

  const bounds = [0, Math.min(shown, FIRST_CHUNK)];
  for (let end = FIRST_CHUNK + CHUNK; bounds[bounds.length - 1] < shown; end += CHUNK) {
    bounds.push(Math.min(shown, end));
  }

  return (
    <div id="entries" className="transcript__entries">
      {bounds.slice(1).map((end, i) => (
        <EntryChunk key={bounds[i]} entries={entries} start={bounds[i]} end={end} />
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
