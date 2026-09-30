import type { ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "info";

const OUTCOME_TONES: Record<string, Tone> = {
  clean: "success",
  interrupted: "warning",
  error: "danger",
};

/** Static status chip on a state wash. */
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

/** Session outcome chip; values without a dedicated tone (e.g. "unknown") use info. */
export function OutcomeBadge({ outcome }: { outcome: string }) {
  return <Badge tone={OUTCOME_TONES[outcome] ?? "info"}>{outcome}</Badge>;
}
