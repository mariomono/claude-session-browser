/** Context usage at or above this percentage renders in the danger state. */
export const CONTEXT_DANGER_PCT = 70;

interface Props {
  pct: number | null;
  tokens: number | null;
  compact?: boolean;
}

/** Context-window usage: a fill bar plus "pct% · Nk" readout, or an em dash when unknown. */
export function ContextMeter({ pct, tokens, compact = false }: Props) {
  if (pct == null) return <span className="muted">—</span>;
  const k = Math.round((tokens ?? 0) / 1000);
  const high = pct >= CONTEXT_DANGER_PCT;
  const fill = Math.min(100, Math.max(0, pct)) / 100;
  return (
    <div className={`meter${high ? " meter--danger" : ""}${compact ? " meter--compact" : ""}`}>
      <div
        className="meter__track"
        role="meter"
        aria-label="Context used"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <span className="meter__fill" style={{ transform: `scaleX(${fill})` }} />
      </div>
      <span className="meter__label num">
        {pct}%<span className="meter__sep"> · </span>
        {k}k
      </span>
    </div>
  );
}
