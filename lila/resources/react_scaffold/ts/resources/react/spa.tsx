// Client-side SPA served by router.spa("/app", meta={...}) in Python.
import "./app.css";
import type { ReactNode } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation, useParams } from "react-router";
import { createLilaSpa, DesktopOnly, useLila, useLilaHead, WebOnly } from "@lila";

function Shell({ children }: { children: ReactNode }) {
  // Refreshes <title>, meta and JSON-LD from the server meta tree on navigation.
  useLilaHead(useLocation().pathname);
  const { desktop } = useLila();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100">
      <nav className="flex gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
        <Link to="/">Home</Link>
        <Link to="/users/1">User 1</Link>
        <WebOnly><Link to="/billing">Billing</Link></WebOnly>
        <DesktopOnly><span className="text-xs text-emerald-600">Desktop</span></DesktopOnly>
        <span className="ml-auto text-xs opacity-60">{desktop ? "desktop app" : "web"}</span>
      </nav>
      <main className="mx-auto max-w-3xl p-8">{children}</main>
    </div>
  );
}

function Home() {
  return <h1 className="text-3xl font-bold">Lila SPA</h1>;
}

function User() {
  const { id } = useParams();
  return <h1 className="text-2xl font-semibold">User {id}</h1>;
}

function Billing() {
  return <h1 className="text-2xl font-semibold">Billing (web only)</h1>;
}

createLilaSpa(({ mount }) => (
  <BrowserRouter basename={mount}>
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/users/:id" element={<User />} />
        <Route path="/billing" element={<Billing />} />
        <Route path="*" element={<h1 className="text-2xl">Not found</h1>} />
      </Routes>
    </Shell>
  </BrowserRouter>
));
