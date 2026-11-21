import { useEffect, useRef, type MouseEvent, type ReactNode, type SyntheticEvent } from "react";
import { cn } from "./cn";

interface BaseProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children?: ReactNode;
}

const SIZES = { sm: "24rem", md: "32rem", lg: "44rem", xl: "60rem" };

/** Native <dialog>: focus trap, Escape and backdrop click close it. */
function useDialog(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const onClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === ref.current) onClose(); // click on the backdrop
  };
  const onCancel = (event: SyntheticEvent) => {
    event.preventDefault();
    onClose();
  };
  return { ref, onClick, onCancel };
}

function Header({ title, description, onClose }: { title?: ReactNode; description?: ReactNode; onClose: () => void }) {
  if (!title && !description) return null;
  return (
    <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
      <div>
        {title && <h2 className="card-title">{title}</h2>}
        {description && <p className="card-description">{description}</p>}
      </div>
      <button type="button" onClick={onClose} className="btn-ghost btn-icon btn-sm" aria-label="Close">✕</button>
    </header>
  );
}

export function Modal({ open, onClose, title, description, footer, size = "md", className, children }: BaseProps & { size?: keyof typeof SIZES }) {
  const dialog = useDialog(open, onClose);
  return (
    <dialog {...dialog} className={cn("lila-dialog", className)} style={{ ["--dialog-width" as any]: SIZES[size] }}>
      {open && (
        <>
          <Header title={title} description={description} onClose={onClose} />
          <div className="px-6 py-5">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-border px-6 py-4">{footer}</footer>}
        </>
      )}
    </dialog>
  );
}

export function Drawer({ open, onClose, title, description, footer, side = "right", className, children }: BaseProps & { side?: "left" | "right" | "top" | "bottom" }) {
  const dialog = useDialog(open, onClose);
  return (
    <dialog {...dialog} data-side={side} className={cn("lila-dialog lila-drawer", className)}>
      {open && (
        <div className="flex h-full flex-col">
          <Header title={title ?? " "} description={description} onClose={onClose} />
          <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-border px-6 py-4">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}
