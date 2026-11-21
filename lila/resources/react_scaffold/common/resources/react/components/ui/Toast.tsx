import { useEffect, useState, type ReactNode } from "react";

export type ToastType = "info" | "success" | "error" | "warning";

export interface ToastItem {
  id: number;
  title: ReactNode;
  description?: ReactNode;
  type: ToastType;
  duration: number;
}

type Input = string | { title: ReactNode; description?: ReactNode; type?: ToastType; duration?: number };

const COLORS: Record<ToastType, string> = {
  info: "var(--info)",
  success: "var(--success)",
  error: "var(--danger)",
  warning: "var(--warning)",
};
const ICONS: Record<ToastType, string> = { info: "ℹ️", success: "✅", error: "⛔", warning: "⚠️" };

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<(items: ToastItem[]) => void>();
const emit = () => listeners.forEach((fn) => fn(items));

export function dismissToast(id: number) {
  items = items.filter((item) => item.id !== id);
  emit();
}

/** toast("Saved") · toast.success("Saved", "3 rows") · toast({ title, type, duration }) */
export function toast(input: Input): number {
  const data = typeof input === "string" ? { title: input } : input;
  const item: ToastItem = { id: nextId++, type: data.type || "info", duration: data.duration ?? 4500, title: data.title, description: data.description };
  items = [...items.slice(-4), item];
  emit();
  if (item.duration > 0) window.setTimeout(() => dismissToast(item.id), item.duration);
  return item.id;
}
toast.success = (title: ReactNode, description?: ReactNode) => toast({ title, description, type: "success" });
toast.error = (title: ReactNode, description?: ReactNode) => toast({ title, description, type: "error", duration: 6500 });
toast.info = (title: ReactNode, description?: ReactNode) => toast({ title, description, type: "info" });
toast.warning = (title: ReactNode, description?: ReactNode) => toast({ title, description, type: "warning" });

/** Mount once (layout or main.tsx): <Toaster /> */
export function Toaster() {
  const [list, setList] = useState<ToastItem[]>(items);
  useEffect(() => {
    listeners.add(setList);
    return () => {
      listeners.delete(setList);
    };
  }, []);
  return (
    <div className="toast-stack" aria-live="polite" role="region" aria-label="Notifications">
      {list.map((item) => (
        <div key={item.id} className="toast-card" role={item.type === "error" ? "alert" : "status"} style={{ ["--toast-color" as any]: COLORS[item.type] }}>
          <span aria-hidden="true">{ICONS[item.type]}</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold">{item.title}</p>
            {item.description && <p className="mt-0.5 text-xs text-muted-foreground">{item.description}</p>}
          </div>
          <button type="button" onClick={() => dismissToast(item.id)} className="text-xs opacity-60 hover:opacity-100" aria-label="Close">✕</button>
        </div>
      ))}
    </div>
  );
}
