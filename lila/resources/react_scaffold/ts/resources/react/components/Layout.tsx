import type { ReactNode } from "react";
import { Link } from "@lila";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-800">
        <nav className="mx-auto flex max-w-4xl gap-4 px-6 py-4 text-sm">
          <Link href="/react" className="font-semibold">Lila React</Link>
          <Link href="/react/about">About</Link>
          <Link href="/react/checkout">Checkout</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
    </div>
  );
}
