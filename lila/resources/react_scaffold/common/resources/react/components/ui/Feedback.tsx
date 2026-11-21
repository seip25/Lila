import { useEffect, useRef, useState, type CSSProperties } from "react";
import { cn } from "./cn";

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("spinner", className)} aria-hidden="true" />;
}

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={cn("skeleton h-4", className)} style={style} aria-hidden="true" />;
}

/** Full-page placeholder (lazy pages, auth checks). */
export function PageSkeleton() {
  return (
    <div role="status" className="mx-auto w-full max-w-4xl space-y-4 p-8">
      <span className="sr-only">Loading...</span>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="w-2/3" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    </div>
  );
}

/**
 * Top progress bar. Without `active` it follows Lila navigations (<Link>, visit()).
 * With React Router data routers: <ProgressBar active={useNavigation().state !== "idle"} />
 */
export function ProgressBar({ active }: { active?: boolean }) {
  const [navigating, setNavigating] = useState(false);
  const [width, setWidth] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const running = active ?? navigating;

  useEffect(() => {
    if (active !== undefined) return undefined;
    const start = () => setNavigating(true);
    const end = () => setNavigating(false);
    window.addEventListener("lila:navigate-start", start);
    window.addEventListener("lila:navigate-end", end);
    return () => {
      window.removeEventListener("lila:navigate-start", start);
      window.removeEventListener("lila:navigate-end", end);
    };
  }, [active]);

  useEffect(() => {
    window.clearInterval(timer.current);
    if (running) {
      setWidth(15);
      timer.current = window.setInterval(() => setWidth((w) => Math.min(w + (90 - w) * 0.15, 90)), 200);
    } else {
      setWidth((w) => (w > 0 ? 100 : 0));
      const done = window.setTimeout(() => setWidth(0), 300);
      return () => window.clearTimeout(done);
    }
    return () => window.clearInterval(timer.current);
  }, [running]);

  return <div className="progress-bar" style={{ width: `${width}%`, opacity: width > 0 && width < 100 ? 1 : 0 }} aria-hidden="true" />;
}
