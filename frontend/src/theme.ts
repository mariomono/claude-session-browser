import { useCallback, useState } from "react";
import { flushSync } from "react-dom";

export const THEMES = ["rust", "dark", "light", "cyber"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_LABELS: Record<Theme, string> = {
  rust: "Rust",
  dark: "Dark",
  light: "Light",
  cyber: "Cyber",
};

/** Must match the key and default in the pre-paint snippet in index.html. */
const STORAGE_KEY = "csb-theme";
const DEFAULT_THEME: Theme = "rust";

function isTheme(v: unknown): v is Theme {
  return typeof v === "string" && (THEMES as readonly string[]).includes(v);
}

function readTheme(): Theme {
  const applied = document.documentElement.dataset.theme;
  if (isTheme(applied)) return applied;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isTheme(stored)) return stored;
  } catch {
    // storage unavailable (private mode, blocked site data)
  }
  return DEFAULT_THEME;
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // not persisted; the theme still applies for this page load
  }
}

/**
 * Cross-fades between themes as a view transition: the browser fades a snapshot of the old page
 * into the new one on the compositor, so no element runs a colour transition of its own.
 * Without view-transition support, or with reduced motion, the theme switches instantly.
 */
function canCrossFade(): boolean {
  return "startViewTransition" in document && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const setTheme = useCallback((next: Theme) => {
    if (!canCrossFade()) {
      applyTheme(next);
      setThemeState(next);
      return;
    }
    // flushSync puts the switcher's pressed state into the same "new" snapshot as the colours.
    document.startViewTransition(() => {
      applyTheme(next);
      flushSync(() => setThemeState(next));
    });
  }, []);
  return [theme, setTheme];
}
