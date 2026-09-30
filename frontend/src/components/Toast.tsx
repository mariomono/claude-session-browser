import type { ReactNode } from "react";

export type ToastState =
  | { kind: "message"; content: ReactNode }
  | { kind: "launch-failed"; command: string[]; error: string };

interface Props {
  toast: ToastState;
  onClose: () => void;
}

/** Bottom-right notice; a failed launch shows the command to run by hand. */
export function Toast({ toast, onClose }: Props) {
  if (toast.kind === "message") return <div id="toast">{toast.content}</div>;

  const cmdStr = toast.command.join(" ");
  return (
    <div id="toast">
      Couldn't launch a terminal ({toast.error}).
      <br />
      Run this yourself:
      <code className="cmd">{cmdStr}</code>
      <button onClick={() => navigator.clipboard.writeText(cmdStr)}>Copy</button>
      <button onClick={onClose}>Close</button>
    </div>
  );
}
