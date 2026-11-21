import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  /** Header actions (buttons) next to the title. */
  actions?: ReactNode;
  padding?: boolean;
}

/** Lila `.card` (rounded, soft shadow, dark mode). */
export function Card({ title, description, footer, actions, padding = true, className, children, ...props }: CardProps) {
  return (
    <section className={cn("card", padding && "p-6", className)} {...props}>
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {description && <p className="card-description">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
        </header>
      )}
      {children}
      {footer && <footer className="mt-6 flex justify-end gap-2 border-t border-border pt-4">{footer}</footer>}
    </section>
  );
}
