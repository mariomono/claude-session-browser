import type { MouseEvent } from "react";
import { Icon } from "./Icon";

interface Props {
  on: boolean;
  onToggle: (ev: MouseEvent) => void;
  size?: number;
}

/** Bookmark star: filled when bookmarked, outlined when not. */
export function StarButton({ on, onToggle, size = 16 }: Props) {
  return (
    <button
      type="button"
      className={`star-btn${on ? " is-on" : ""}`}
      title="Toggle bookmark"
      aria-label={on ? "Remove bookmark" : "Bookmark session"}
      aria-pressed={on}
      onClick={onToggle}
    >
      <Icon name="star" size={size} filled={on} />
    </button>
  );
}
