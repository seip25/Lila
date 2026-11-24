// Layout for authenticated React pages (dashboard, profile...).
import type { ReactNode } from "react";
import { http, Link, useT, visit } from "@lila";
import { Badge, Button, ProgressBar, ThemeToggle, Toaster } from "./ui";
import type { SessionUser } from "./Auth";

const LANGS = [
  ["es", "🇪🇸 Español"],
  ["en", "🇺🇸 English"],
  ["pt", "🇧🇷 Português"],
];

export default function AppShell({ user, children }: { user: SessionUser; children: ReactNode }) {
  const t = useT();
  const logout = async () => {
    try {
      await http("/logout", { method: "POST" });
    } finally {
      await visit("/login", { replace: true });
    }
  };
  return (
    <div className="flex min-h-screen flex-col">
      <ProgressBar />
      <header className="sticky top-0 z-40 border-b border-border bg-surface py-3 shadow-sm dark:bg-surface-dark">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4">
          <Link href="/dashboard" className="bg-gradient-to-r from-lila-800 via-lila-700 to-lila-500 dark:from-[#e5c2ff] dark:via-lila-300 dark:to-indigo-400 bg-clip-text text-2xl font-black text-transparent">
            Lila
          </Link>
          <div className="flex items-center gap-2">
            <Badge tone="primary" soft>{user.name}</Badge>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-8 px-4 py-8 md:grid-cols-4">
        <aside className="card flex h-fit flex-col gap-1 p-4 md:col-span-1">
          <h2 className="field-label mb-2 px-3">{t("menu", "Menu")}</h2>
          <Link href="/dashboard" className="nav-link">🏠 {t("home", "Home")}</Link>
          <Link href="/profile" className="nav-link">👤 {t("profile", "Profile")}</Link>
          {LANGS.map(([code, label]) => (
            // Full reload: the server switches the locale.
            <a key={code} href={`?lang=${code}`} className="nav-link">{label}</a>
          ))}
          <hr className="my-2 border-border" />
          <Button variant="secondary" size="sm" onClick={logout}>{t("logout", "Log Out")}</Button>
        </aside>
        <main className="flex flex-col gap-6 md:col-span-3">{children}</main>
      </div>
      <Toaster />
    </div>
  );
}
