import { useState, type AnimationEvent, type CSSProperties, type ReactNode } from "react";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";

export type ToastState =
  | { kind: "message"; content: ReactNode }
  | { kind: "launch-failed"; command: string[]; error: string };

interface Props {
  toast: ToastState | null;
  onClose: () => void;
  /** Auto-dismiss time of message toasts, drawn as the shrinking progress line. */
  durationMs: number;
}

/**
 * Bottom-right notice; a failed launch shows the command to run by hand.
 * Keeps the last toast mounted while its exit animation plays after `toast` turns null.
 */
export function Toast({ toast, onClose, durationMs }: Props) {
  const [prev, setPrev] = useState<ToastState | null>(toast);
  const [shown, setShown] = useState<{ toast: ToastState; id: number } | null>(
    toast ? { toast, id: 0 } : null,
  );
  const [leaving, setLeaving] = useState(false);

  if (toast !== prev) {
    setPrev(toast);
    if (toast) {
      setShown((s) => ({ toast, id: (s?.id ?? 0) + 1 }));
      setLeaving(false);
    } else {
      setLeaving(true);
    }
  }

  if (!shown) return null;

  const onAnimationEnd = (ev: AnimationEvent<HTMLDivElement>) => {
    if (ev.target === ev.currentTarget && leaving) {
      setShown(null);
      setLeaving(false);
    }
  };

  const t = shown.toast;
  const cls = `toast toast--${t.kind === "message" ? "info" : "danger"}${leaving ? " is-leaving" : ""}`;

  if (t.kind === "message") {
    return (
      <div
        id="toast"
        key={shown.id}
        className={cls}
        role="status"
        style={{ "--toast-ms": `${durationMs}ms` } as CSSProperties}
        onAnimationEnd={onAnimationEnd}
      >
        <div className="toast__body">{t.content}</div>
        <span className="toast__timer" aria-hidden="true" />
      </div>
    );
  }

  const cmdStr = t.command.join(" ");
  return (
    <div id="toast" key={shown.id} className={cls} role="alert" onAnimationEnd={onAnimationEnd}>
      <div className="toast__head">
        <Icon name="terminal" />
        <strong>Couldn't launch a terminal</strong>
        <button type="button" className="btn btn--icon btn--ghost toast__close" aria-label="Close" onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      <p className="toast__error">{t.error}</p>
      <p className="toast__hint">Run this yourself:</p>
      <code className="cmd">{cmdStr}</code>
      <div className="toast__actions">
        <CopyButton text={cmdStr} label="Copy" className="btn btn--primary" />
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
