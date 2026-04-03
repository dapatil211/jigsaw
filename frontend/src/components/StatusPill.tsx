import type { PropsWithChildren } from "react";

interface StatusPillProps extends PropsWithChildren {
  state: "complete" | "pending" | "warning";
}

export function StatusPill({ children, state }: StatusPillProps) {
  return <span className={`status-pill status-pill-${state}`}>{children}</span>;
}
