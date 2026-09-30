/** Inline stroke icons (16px grid, currentColor) so the app needs no icon font or network. */
const PATHS = {
  search: "M7 12.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM11 11l3.5 3.5",
  star: "M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6L8 1.8Z",
  refresh: "M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2v3.2h-3.2",
  play: "M5 3.2v9.6L12.6 8 5 3.2Z",
  fork: "M4.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM11.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM8 15a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM4.5 4v1c0 1.7 1.2 2.5 3.5 2.5s3.5-.8 3.5-2.5V4M8 7.5V12",
  back: "M9.5 3.5 5 8l4.5 4.5M5.5 8H14",
  copy: "M5.5 5.5V3a1 1 0 0 1 1-1H13a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1h-2.5M3 5.5h6.5a1 1 0 0 1 1 1V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1Z",
  check: "M3 8.5 6.5 12 13 4.5",
  chevronDown: "M4 6l4 4 4-4",
  chevronRight: "M6 4l4 4-4 4",
  sortUp: "M8 13V3M4 7l4-4 4 4",
  sortDown: "M8 3v10M4 9l4 4 4-4",
  sortBoth: "M5.5 6 8 3.5 10.5 6M5.5 10 8 12.5 10.5 10",
  close: "M4 4l8 8M12 4l-8 8",
  branch: "M5 2v9M5 14a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM11 6a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM11 6c0 3-6 2.5-6 5",
  alert: "M8 2 1.5 13.5h13L8 2ZM8 6.5v3.2M8 11.8v.2",
  inbox: "M2 9.5 4 3h8l2 6.5M2 9.5V13h12V9.5M2 9.5h3.5l1 1.5h3l1-1.5H14",
  terminal: "M2.5 3h11v10h-11V3ZM5 6.5 7 8.5 5 10.5M8.5 10.5H11",
  filter: "M2.5 3.5h11L9.5 8.5V13l-3-1.5v-3L2.5 3.5Z",
} as const;

export type IconName = keyof typeof PATHS;

interface Props {
  name: IconName;
  size?: number;
  filled?: boolean;
  className?: string;
}

export function Icon({ name, size = 16, filled = false, className }: Props) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
