import { useId, useState } from "react";
import { clockTime } from "../format";
import type { TranscriptEntry as Entry } from "../types";
import { Icon } from "./Icon";

const COLLAPSED_KINDS = new Set(["thinking", "tool_use", "tool_result"]);
const PREVIEW_CHARS = 140;

/** Colour family for the card's accent bar and label. */
function accentOf(e: Entry): string {
  if (e.kind === "thinking") return "thinking";
  if (e.kind === "tool_use" || e.kind === "tool_result") return "tool";
  return e.role;
}

function labelOf(e: Entry): string {
  if (e.kind === "tool_use") return `tool: ${e.tool_name || ""}`;
  if (e.kind === "tool_result") return "tool result";
  return e.role;
}

function preview(content: string): string {
  const line = content.trimStart().split("\n", 1)[0] ?? "";
  return line.length > PREVIEW_CHARS ? `${line.slice(0, PREVIEW_CHARS)}…` : line;
}

/** Thinking/tool body: collapsed by default, rendered on first expand, height animated via grid rows. */
function Collapsible({ e }: { e: Entry }) {
  const [open, setOpen] = useState(false);
  const [rendered, setRendered] = useState(false);
  const bodyId = useId();

  const toggle = () => {
    setRendered(true);
    setOpen((v) => !v);
  };

  return (
    <div className={`collapsible${open ? " is-open" : ""}`}>
      <button type="button" className="collapsible__toggle" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
        <Icon name="chevronRight" size={14} className="collapsible__chevron" />
        <span className="collapsible__kind">{e.kind}</span>
        {!open && <span className="collapsible__preview">{preview(e.content)}</span>}
      </button>
      <div className="collapsible__region" id={bodyId} inert={!open}>
        <div className="collapsible__inner">{rendered && <pre className="entry__body">{e.content}</pre>}</div>
      </div>
    </div>
  );
}

export function TranscriptEntry({ e }: { e: Entry }) {
  const time = clockTime(e.timestamp);
  return (
    <article className={`entry entry--${e.role}${e.is_sidechain ? " entry--sidechain" : ""}`} data-accent={accentOf(e)}>
      <header className="entry__head">
        <span className="entry__role">
          <span className="entry__dot" aria-hidden="true" />
          {labelOf(e)}
        </span>
        {e.is_sidechain && <span className="entry__tag">sidechain</span>}
        {time && (
          <time className="entry__time num" dateTime={e.timestamp ?? undefined} title={e.timestamp ?? undefined}>
            {time}
          </time>
        )}
      </header>
      {COLLAPSED_KINDS.has(e.kind) ? <Collapsible e={e} /> : <pre className="entry__body">{e.content}</pre>}
    </article>
  );
}
