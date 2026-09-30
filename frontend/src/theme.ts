import { useCallback, useState } from "react";

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
/** How long the cross-theme colour fade runs; matches --duration-slow. */
const SWITCH_FADE_MS = 400;

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

let fadeTimer: number | undefined;

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  // Colours cross-fade only while switching, so normal interactions keep their own timings.
  root.classList.add("theme-switching");
  window.clearTimeout(fadeTimer);
  fadeTimer = window.setTimeout(() => root.classList.remove("theme-switching"), SWITCH_FADE_MS);
  root.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // not persisted; the theme still applies for this page load
  }
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const setTheme = useCallback((next: Theme) => {
    applyTheme(next);
    setThemeState(next);
  }, []);
  return [theme, setTheme];
}
