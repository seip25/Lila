import { useT } from "@lila";
import type { ReactElement } from "react";
import AppShell from "../../components/AppShell";
import type { SessionUser } from "../../components/Auth";
import { Card } from "../../components/ui";

// GET /dashboard (login_required) -> react_render(request, "Account/Dashboard", {"user": session})
export default function Dashboard({ user }: { user: SessionUser }) {
  const t = useT();
  return (
    <Card>
      <h1 className="mb-2 text-3xl font-black tracking-tight">
        {t("welcome", "Welcome")}, {user.name}!
      </h1>
      <p className="text-sm text-muted-foreground">{user.email}</p>
    </Card>
  );
}

Dashboard.layout = (page: ReactElement<{ user: SessionUser }>) => <AppShell user={page.props.user}>{page}</AppShell>;
