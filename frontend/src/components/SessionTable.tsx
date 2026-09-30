import { memo, type CSSProperties, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { recency, sizeBucket, type SortKey } from "../format";
import type { ResumeMode, SessionIndex } from "../types";
import { OutcomeBadge } from "./Badge";
import { Icon } from "./Icon";
import { ContextMeter } from "./Meter";
import { SkeletonRows } from "./Skeleton";
import { StarButton } from "./StarButton";

const COLUMNS = 8;

interface Props {
  sessions: SessionIndex[];
  sort: SortKey;
  dir: 1 | -1;
  onSort: (key: SortKey) => void;
  onOpen: (id: string) => void;
  onResume: (id: string, mode: ResumeMode) => void;
  onToggleBookmark: (id: string) => void;
  /** Session whose transcript is being fetched. */
  openingId: string | null;
  /** Show shimmer rows instead of data (first load). */
  skeleton: boolean;
  /** Rendered across the table body when there are no rows. */
  placeholder?: ReactNode;
}

interface SortableThProps {
  k: SortKey;
  label: string;
  sort: SortKey;
  dir: 1 | -1;
  onSort: (key: SortKey) => void;
  className?: string;
}

function SortableTh({ k, label, sort, dir, onSort, className }: SortableThProps) {
  const active = sort === k;
  const icon = !active ? "sortBoth" : dir === 1 ? "sortUp" : "sortDown";
  return (
    <th
      className={className}
      aria-sort={active ? (dir === 1 ? "ascending" : "descending") : undefined}
      data-sort={k}
    >
      <button
        type="button"
        className={`th-sort${active ? " is-active" : ""}`}
        onClick={() => onSort(k)}
        title={`Sort by ${label.toLowerCase()}`}
      >
        <span>{label}</span>
        <Icon name={icon} size={12} className="th-sort__icon" />
      </button>
    </th>
  );
}

interface SessionRowProps {
  s: SessionIndex;
  index: number;
  opening: boolean;
  onOpen: (id: string) => void;
  onResume: (id: string, mode: ResumeMode) => void;
  onToggleBookmark: (id: string) => void;
}

/** One session; memoised, so typing, toasts and other rows' changes skip it (callbacks must be stable). */
const SessionRow = memo(function SessionRow({ s, index, opening, onOpen, onResume, onToggleBookmark }: SessionRowProps) {
  const stop = (fn: () => void) => (ev: MouseEvent) => {
    ev.stopPropagation();
    fn();
  };

  const onKeyDown = (ev: KeyboardEvent<HTMLTableRowElement>) => {
    if (ev.target !== ev.currentTarget) return; // keys on the row's own buttons act on those buttons
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      onOpen(s.session_id);
    }
  };

  return (
    <tr
      className={`session-row${opening ? " is-opening" : ""}`}
      style={{ "--row-i": Math.min(index, 20) } as CSSProperties}
      tabIndex={0}
      aria-busy={opening}
      onClick={() => onOpen(s.session_id)}
      onKeyDown={onKeyDown}
    >
      <td className="col-star">
        <StarButton on={s.bookmarked} onToggle={stop(() => onToggleBookmark(s.session_id))} />
      </td>
      <td className="col-title">
        <span className="cell-title" title={s.title}>
          {s.title}
        </span>
        {s.model && <span className="cell-sub mono">{s.model}</span>}
      </td>
      <td className="col-project">
        <span className="cell-path mono" title={s.cwd || undefined}>
          <bdi>{s.cwd || "—"}</bdi>
        </span>
        {s.git_branch && (
          <span className="cell-branch mono" title={s.git_branch}>
            <Icon name="branch" size={12} />
            {s.git_branch}
          </span>
        )}
      </td>
      <td className="col-desc">
        <span className="desc-first">{s.first_prompt || ""}</span>
        <span className="desc-last">{s.last_prompt || ""}</span>
      </td>
      <td className="col-state">
        <OutcomeBadge outcome={s.outcome} />
        <span className="cell-sub num">
          {recency(s.last_activity)} · {sizeBucket(s.message_count)}
          {s.compacted ? <span title="Compacted"> ⟳</span> : ""}
        </span>
      </td>
      <td className="col-context">
        <ContextMeter pct={s.context_pct} tokens={s.context_tokens} />
      </td>
      <td className="col-when muted num" title={s.last_activity || undefined}>
        {recency(s.last_activity)}
      </td>
      <td className="col-actions">
        <div className="row-actions">
          <button
            type="button"
            className="btn btn--icon"
            title="Resume (continue)"
            aria-label="Resume (continue)"
            onClick={stop(() => onResume(s.session_id, "continue"))}
          >
            <Icon name="play" />
          </button>
          <button
            type="button"
            className="btn btn--icon"
            title="Fork into new session"
            aria-label="Fork into new session"
            onClick={stop(() => onResume(s.session_id, "fork"))}
          >
            <Icon name="fork" />
          </button>
        </div>
      </td>
    </tr>
  );
});

export function SessionTable(props: Props) {
  const { sessions, sort, dir, onSort, onOpen, onResume, onToggleBookmark, openingId, skeleton, placeholder } = props;

  const th = { sort, dir, onSort };

  return (
    <div className="table-card">
      <table id="sessions" className="sessions">
        <thead>
          <tr>
            <th className="col-star">
              <span className="visually-hidden">Bookmark</span>
            </th>
            <SortableTh k="title" label="Title" className="col-title" {...th} />
            <SortableTh k="cwd" label="Project" className="col-project" {...th} />
            <th className="col-desc">
              <span className="th-label">Description</span>
            </th>
            <SortableTh k="outcome" label="State" className="col-state" {...th} />
            <SortableTh k="context_pct" label="Context" className="col-context" {...th} />
            <SortableTh k="last_activity" label="Last active" className="col-when" {...th} />
            <th className="col-actions">
              <span className="th-label">Resume</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {skeleton ? (
            <SkeletonRows columns={COLUMNS} />
          ) : sessions.length === 0 && placeholder ? (
            <tr className="placeholder-row">
              <td colSpan={COLUMNS}>{placeholder}</td>
            </tr>
          ) : (
            sessions.map((s, i) => (
              <SessionRow
                key={s.session_id}
                s={s}
                index={i}
                opening={openingId === s.session_id}
                onOpen={onOpen}
                onResume={onResume}
                onToggleBookmark={onToggleBookmark}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
