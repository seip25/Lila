import { forwardRef, useState, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from "react";
import { http, HttpError, Link } from "@lila";
import { cn } from "./cn";
import { Spinner } from "./Feedback";
import { toast } from "./Toast";

export type ButtonVariant =
  | "primary" | "secondary" | "outline" | "ghost" | "danger" | "success"
  | "warning" | "info" | "light" | "dark" | "link";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

/** Lila button classes (same as the Jinja pages): btn-primary, btn-outline... */
export function buttonVariants({ variant = "primary", size = "md", className }: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}) {
  return cn(`btn-${variant}`, size !== "md" && `btn-${size}`, className);
}

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onError"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  loadingText?: ReactNode;
  /** Renders a <Link> (client navigation) styled as a button. */
  href?: string;
  /** Calls this endpoint on click (CSRF included), e.g. url="/api/items/3" method="DELETE". */
  url?: string;
  method?: string;
  body?: unknown;
  /** Asks before calling `url` (native confirm dialog). */
  confirm?: string;
  /** Toast shown after a successful `url` call (or the server `message`). */
  successMessage?: string | boolean;
  onSuccess?: (data: any) => void;
  onError?: (error: HttpError) => void;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, loadingText, href, url, method = "POST", body, confirm, successMessage,
    onSuccess, onError, onClick, className, children, disabled, type, ...props },
  ref,
) {
  const [pending, setPending] = useState(false);
  const busy = loading || pending;
  const classes = buttonVariants({ variant, size, className });
  if (href) {
    return <Link href={href} className={classes}>{children}</Link>;
  }
  const handleClick = async (event: MouseEvent<HTMLButtonElement>) => {
    onClick?.(event);
    if (!url || event.defaultPrevented) return;
    if (confirm && !window.confirm(confirm)) return;
    setPending(true);
    try {
      const data = await http(url, { method, body });
      if (successMessage) toast.success(typeof successMessage === "string" ? successMessage : data?.message || data?.msg || "OK");
      onSuccess?.(data);
    } catch (error) {
      const err = error instanceof HttpError ? error : new HttpError(String(error), 0, null);
      if (onError) onError(err);
      else toast.error(err.message);
    } finally {
      setPending(false);
    }
  };
  return (
    <button ref={ref} type={type || "button"} className={classes} disabled={disabled || busy} aria-busy={busy || undefined} onClick={handleClick} {...props}>
      {busy && <Spinner />}
      {busy && loadingText ? loadingText : children}
    </button>
  );
});
