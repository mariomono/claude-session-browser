import { useLayoutEffect, useRef } from "react";
import type { Theme } from "../theme";
import { Icon } from "./Icon";
import { ThemeSwitcher } from "./ThemeSwitcher";

interface Props {
  searchInput: string;
  onSearchInput: (value: string) => void;
  project: string;
  projects: string[];
  onProject: (value: string) => void;
  bookmarkedOnly: boolean;
  onToggleBookmarkedOnly: () => void;
  onRescan: () => void;
  loading: boolean;
  rescanning: boolean;
  theme: Theme;
  onTheme: (theme: Theme) => void;
}

/** Sticky app bar; publishes its height as --app-header-h so sticky sub-headers sit right below it. */
export function AppHeader(props: Props) {
  const ref = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Only on a real change: a new value on <html> restyles the whole document.
    let published = "";
    const publish = () => {
      const h = `${el.getBoundingClientRect().height}px`;
      if (h === published) return;
      published = h;
      document.documentElement.style.setProperty("--app-header-h", h);
    };
    publish();
    const ro = new ResizeObserver(publish);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <header className="app-header" ref={ref}>
      <div className="app-header__inner">
        <div className="brand" aria-label="Claude Sessions">
          <span className="brand__glyph" aria-hidden="true">
            &gt;
          </span>
          <span className="brand__name">
            claude<span className="brand__dim">/</span>sessions
          </span>
          <span className="brand__cursor" aria-hidden="true" />
        </div>

        <label className="field field--search">
          <Icon name="search" className="field__icon" />
          <input
            id="search"
            type="search"
            placeholder="Search title / prompts…"
            aria-label="Search sessions"
            value={props.searchInput}
            onChange={(e) => props.onSearchInput(e.target.value)}
          />
        </label>

        <label className="field field--select">
          <select
            id="project"
            aria-label="Filter by project"
            value={props.project}
            onChange={(e) => props.onProject(e.target.value)}
          >
            <option value="">All projects</option>
            {props.projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <Icon name="chevronDown" className="field__chevron" />
        </label>

        <div className="app-header__actions">
          <button
            id="bookmarks-toggle"
            type="button"
            className="btn btn--toggle btn--star"
            title="Show only bookmarked"
            aria-pressed={props.bookmarkedOnly}
            onClick={props.onToggleBookmarkedOnly}
          >
            <Icon name="star" filled={props.bookmarkedOnly} />
            <span>Bookmarks</span>
          </button>
          <button
            id="rescan"
            type="button"
            className={`btn${props.rescanning ? " is-busy" : ""}`}
            title="Re-scan logs"
            aria-busy={props.rescanning}
            onClick={props.onRescan}
          >
            <Icon name="refresh" className="spin-on-busy" />
            <span>Rescan</span>
          </button>
          <ThemeSwitcher theme={props.theme} onChange={props.onTheme} />
        </div>
      </div>
      <div className={`app-header__progress${props.loading ? " is-active" : ""}`} aria-hidden="true" />
    </header>
  );
}
