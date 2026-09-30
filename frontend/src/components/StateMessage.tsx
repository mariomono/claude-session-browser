import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

interface Props {
  icon: IconName;
  title: string;
  tone?: "neutral" | "danger";
  children?: ReactNode;
  action?: ReactNode;
}

/** Centered empty/error panel used inside the list view. */
export function StateMessage({ icon, title, tone = "neutral", children, action }: Props) {
  return (
    <div className={`state-msg state-msg--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <span className="state-msg__icon">
        <Icon name={icon} size={24} />
      </span>
      <h2 className="state-msg__title">{title}</h2>
      {children && <p className="state-msg__body">{children}</p>}
      {action && <div className="state-msg__action">{action}</div>}
    </div>
  );
}
