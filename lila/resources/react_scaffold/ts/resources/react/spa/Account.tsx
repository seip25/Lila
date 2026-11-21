import { RequireAuth, useAuth } from "@lila/auth";
import { Card, PageSkeleton } from "@/components/ui";

// Guests go to Lila's /login page (server route, outside the SPA): `page`.
export default function Account() {
  return (
    <RequireAuth page redirectTo="/login" fallback={<PageSkeleton />}>
      <Profile />
    </RequireAuth>
  );
}

function Profile() {
  const { user } = useAuth();
  return (
    <Card title={`Hi, ${user?.name}`} description={user?.email as string}>
      <p className="text-sm text-muted-foreground">Roles: {(user?.roles || []).join(", ") || "none"}</p>
    </Card>
  );
}
