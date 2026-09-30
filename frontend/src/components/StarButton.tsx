import type { MouseEvent } from "react";

interface Props {
  on: boolean;
  onToggle: (ev: MouseEvent) => void;
}

/** Bookmark star: gold ★ when bookmarked, outlined ☆ when not. */
export function StarButton({ on, onToggle }: Props) {
  return (
    <button className={`star-btn${on ? " on" : ""}`} title="Toggle bookmark" onClick={onToggle}>
      {on ? "★" : "☆"}
    </button>
  );
}
