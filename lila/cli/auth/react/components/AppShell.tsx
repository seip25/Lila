// Layout for authenticated React pages (dashboard, profile...).
import type { ReactNode } from "react";
import { http, Link, usePage, useT, visit } from "@lila";
import type { SessionUser } from "./Auth";

const LANGS = [
  ["es", "🇪🇸 Español"],
  ["en", "🇺🇸 English"],
  ["pt", "🇧🇷 Português"],
];

export default function AppShell({ user, children }: { user: SessionUser; children: ReactNode }) {
  const t = useT();
  const { url } = usePage();
  const item = (href: string, label: ReactNode) => (
    <Link
      href={href}
      className={
        "flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition " +
        (url.split("?")[0] === href
          ? "bg-blue-600 text-white shadow-sm"
          : "text-slate-600 hover:bg-slate-50 hover:text-blue-600 dark:text-slate-400 dark:hover:bg-slate-800")
      }
    >
      {label}
    </Link>
  );
  const logout = async () => {
    try {
      await http("/logout", { method: "POST" });
    } finally {
      await visit("/login", { replace: true });
    }
  };
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-200">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4">
          <Link href="/dashboard" className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-2xl font-black text-transparent">
            Lila
          </Link>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
            {user.name}
          </span>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-8 px-4 py-8 md:grid-cols-4">
        <aside className="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:col-span-1">
          <h2 className="mb-2 px-3 text-xs font-black uppercase tracking-wider text-slate-400">{t("menu", "Menu")}</h2>
          {item("/dashboard", <>🏠 {t("home", "Home")}</>)}
          {item("/profile", <>👤 {t("profile", "Profile")}</>)}
          {LANGS.map(([code, label]) => (
            // Full reload: the server switches the locale.
            <a key={code} href={`?lang=${code}`} className="rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800">
              {label}
            </a>
          ))}
          <hr className="my-2 border-slate-200 dark:border-slate-800" />
          <button onClick={logout} className="rounded-xl border border-blue-600 px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-600 hover:text-white">
            {t("logout", "Log Out")}
          </button>
        </aside>
        <main className="flex flex-col gap-6 md:col-span-3">{children}</main>
      </div>
    </div>
  );
}
