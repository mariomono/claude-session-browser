import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

const CONFIRM_MS = 1500;

interface Props {
  text: string;
  label: string;
  className?: string;
}

/** Copies `text` to the clipboard and briefly confirms with a check mark. */
export function CopyButton({ text, label, className = "btn" }: Props) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = () => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), CONFIRM_MS);
    });
  };

  return (
    <button type="button" className={`${className}${copied ? " is-confirmed" : ""}`} onClick={copy}>
      <Icon name={copied ? "check" : "copy"} />
      <span>{copied ? "Copied" : label}</span>
    </button>
  );
}
