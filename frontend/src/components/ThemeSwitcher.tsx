import { THEMES, THEME_LABELS, type Theme } from "../theme";

interface Props {
  theme: Theme;
  onChange: (theme: Theme) => void;
}

/** Segmented control; each option previews its theme's surface and accent colours. */
export function ThemeSwitcher({ theme, onChange }: Props) {
  return (
    <div className="theme-switch" role="group" aria-label="Colour theme">
      {THEMES.map((t) => (
        <button
          key={t}
          type="button"
          className="theme-switch__opt"
          aria-pressed={t === theme}
          title={`${THEME_LABELS[t]} theme`}
          onClick={() => onChange(t)}
        >
          <span className={`theme-swatch theme-swatch--${t}`} aria-hidden="true" />
          <span className="theme-switch__label">{THEME_LABELS[t]}</span>
        </button>
      ))}
    </div>
  );
}
