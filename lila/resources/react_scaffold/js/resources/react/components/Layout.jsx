import { Link } from "@lila";
import { ProgressBar, ThemeToggle, Toaster } from "./ui";

export default function Layout({ children }) {
  return (
    <div className="min-h-screen">
      <ProgressBar />
      <header className="border-b border-border bg-surface dark:bg-surface-dark">
        <nav className="mx-auto flex max-w-4xl items-center gap-1 px-6 py-3 text-sm">
          <Link href="/react" exact className="mr-4 font-black text-primary">Lila React</Link>
          <Link href="/react" exact className="nav-link">Home</Link>
          <Link href="/react/about" className="nav-link">About</Link>
          <Link href="/react/checkout" className="nav-link">Checkout</Link>
          <ThemeToggle className="ml-auto" />
        </nav>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
      <Toaster />
    </div>
  );
}
