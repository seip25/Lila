import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type BadgeTone = "default" | "primary" | "success" | "warning" | "danger" | "info";

export function Badge({ tone = "default", soft = false, className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone; soft?: boolean }) {
  return <span className={cn("badge", tone !== "default" && `badge-${tone}`, soft && "badge-soft", className)} {...props} />;
}
