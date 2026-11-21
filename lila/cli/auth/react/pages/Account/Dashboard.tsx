import { useT } from "@lila";
import type { ReactElement } from "react";
import AppShell from "../../components/AppShell";
import type { SessionUser } from "../../components/Auth";

// GET /dashboard (login_required) -> react_render(request, "Account/Dashboard", {"user": session})
export default function Dashboard({ user }: { user: SessionUser }) {
  const t = useT();
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-8 dark:border-slate-800 dark:bg-slate-900">
      <h1 className="mb-4 text-3xl font-black tracking-tight">
        {t("welcome", "Welcome")}, {user.name}!
      </h1>
      <p className="text-sm text-slate-500">{user.email}</p>
    </article>
  );
}

Dashboard.layout = (page: ReactElement<{ user: SessionUser }>) => <AppShell user={page.props.user}>{page}</AppShell>;
