import { NavLink, Outlet, useNavigation } from "react-router";
import { DesktopOnly, WebOnly } from "@lila";
import { useAuth } from "@lila/auth";
import { LilaHead } from "@lila/router";
import { Badge, Button, ProgressBar, ThemeToggle, Toaster } from "@/components/ui";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigation = useNavigation();
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");
  return (
    <div className="min-h-screen">
      <LilaHead />
      <ProgressBar active={navigation.state !== "idle"} />
      <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur dark:bg-surface-dark/80">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <span className="mr-4 bg-gradient-to-r from-lila-800 via-lila-700 to-lila-500 dark:from-[#e5c2ff] dark:via-lila-300 dark:to-indigo-400 bg-clip-text text-xl font-black text-transparent">Lila</span>
          <nav className="flex flex-1 flex-wrap gap-1">
            <NavLink to="/" end className={link}>Components</NavLink>
            <NavLink to="/users" className={link}>Users</NavLink>
            <NavLink to="/account" className={link}>Account</NavLink>
            <NavLink to="/live" className={link}>Live</NavLink>
            <WebOnly><NavLink to="/billing" className={link}>Billing</NavLink></WebOnly>
          </nav>
          <DesktopOnly><Badge tone="success" soft>Desktop</Badge></DesktopOnly>
          {user ? (
            <Button size="sm" variant="outline" onClick={logout}>{user.name} · Log out</Button>
          ) : (
            // Lila's server-rendered (or React) login page lives outside the SPA.
            <Button size="sm" variant="outline" onClick={() => window.location.assign("/login")}>Sign in</Button>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
}
