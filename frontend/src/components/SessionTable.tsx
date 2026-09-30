import {
  memo,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { recency, sizeBucket, type SortKey } from "../format";
import type { ResumeMode, SessionIndex } from "../types";
import { OutcomeBadge } from "./Badge";
import { Icon } from "./Icon";
import { ContextMeter } from "./Meter";
import { SkeletonRows } from "./Skeleton";
import { StarButton } from "./StarButton";

/** One class per column, in order; shared by header, rows and skeleton so responsive rules hit all three. */
const COLUMNS = ["col-star", "col-title", "col-project", "col-desc", "col-state", "col-context", "col-when", "col-actions"] as const;
/** Sortable columns in header order; the card list offers the same choices as a dropdown. */
const SORT_LABELS: Record<SortKey, string> = {
  title: "Title",
  cwd: "Project",
  outcome: "State",
  context_pct: "Context",
  last_activity: "Last active",
};
/** Rows that play the entrance animation; later ones start below the fold and appear as-is. */
const ANIMATED_ROWS = 20;

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
  // Decided once at mount, so re-sorting never replays the entrance on rows that move up.
  const [enters] = useState(index < ANIMATED_ROWS);
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
      className={`session-row${enters ? " session-row--enter" : ""}${opening ? " is-opening" : ""}`}
      style={enters ? ({ "--row-i": index } as CSSProperties) : undefined}
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
        {s.model && (
          <span className="cell-sub cell-model mono" title={s.model}>
            {s.model}
          </span>
        )}
      </td>
      <td className="col-project">
        <span className="cell-path mono" title={s.cwd || undefined}>
          <bdi>{s.cwd || "—"}</bdi>
        </span>
        {s.git_branch && (
          <span className="cell-branch mono" title={s.git_branch}>
            <Icon name="branch" size={12} />
            <span className="cell-branch__name">{s.git_branch}</span>
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

/** True while any sortable column header is hidden by the responsive CSS.
 *
 * Measured from the DOM, not tied to any breakpoint: whatever current or future
 * rule hides a `th[data-sort]` (a dropped column, card mode, a new column's own
 * breakpoint), the compact sort control appears to stand in for it.
 */
function useHiddenSortableColumns(listRef: RefObject<HTMLDivElement | null>): boolean {
  const [hidden, setHidden] = useState(false);
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const measure = () => {
      const any = Array.from(list.querySelectorAll<HTMLElement>("th[data-sort]")).some((el) => el.offsetWidth === 0);
      setHidden((prev) => (prev === any ? prev : any)); // only update on change, so the observer can't loop
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [listRef]);
  return hidden;
}

export function SessionTable(props: Props) {
  const { sessions, sort, dir, onSort, onOpen, onResume, onToggleBookmark, openingId, skeleton, placeholder } = props;

  const th = { sort, dir, onSort };
  const order = dir === 1 ? "ascending" : "descending";
  const listRef = useRef<HTMLDivElement>(null);
  const sortControlNeeded = useHiddenSortableColumns(listRef);

  return (
    <div className="session-list" ref={listRef}>
      {/* Stands in for whichever sortable column headers the responsive CSS has hidden. */}
      {sortControlNeeded && (
        <div className="list-sort">
          <label className="list-sort__label" htmlFor="sort-select">
            Sort
          </label>
          <div className="field field--select list-sort__field">
            <select id="sort-select" value={sort} onChange={(e) => onSort(e.target.value as SortKey)}>
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <option key={k} value={k}>
                  {SORT_LABELS[k]}
                </option>
              ))}
            </select>
            <Icon name="chevronDown" className="field__chevron" />
          </div>
          <button
            type="button"
            className="btn btn--icon"
            title={`Sorted by ${SORT_LABELS[sort].toLowerCase()}, ${order}; click to reverse`}
            aria-label={`Reverse sort order (now ${order})`}
            onClick={() => onSort(sort)}
          >
            <Icon name={dir === 1 ? "sortUp" : "sortDown"} />
          </button>
        </div>
      )}
      <div className="table-card">
        <table id="sessions" className="sessions">
          <thead>
            <tr>
              <th className="col-star">
                <span className="visually-hidden">Bookmark</span>
              </th>
              <SortableTh k="title" label={SORT_LABELS.title} className="col-title" {...th} />
              <SortableTh k="cwd" label={SORT_LABELS.cwd} className="col-project" {...th} />
              <th className="col-desc">
                <span className="th-label">Description</span>
              </th>
              <SortableTh k="outcome" label={SORT_LABELS.outcome} className="col-state" {...th} />
              <SortableTh k="context_pct" label={SORT_LABELS.context_pct} className="col-context" {...th} />
              <SortableTh k="last_activity" label={SORT_LABELS.last_activity} className="col-when" {...th} />
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
                <td colSpan={COLUMNS.length}>{placeholder}</td>
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
    </div>
  );
}
