// Client-side SPA served by router.spa("/app", meta={...}) in Python.
// The TypeScript scaffold (default) has a bigger demo of the UI kit.
import "./app.css";
import { NavLink, Outlet, RouterProvider, useNavigation, useParams } from "react-router";
import { createLilaSpa, WebOnly } from "@lila";
import { AuthProvider, RequireAuth, useAuth } from "@lila/auth";
import { createRouter, LilaHead } from "@lila/router";
import { Button, Card, DataTable, ProgressBar, ThemeToggle, Toaster, toast } from "@/components/ui";

function AppLayout() {
  const { user, logout } = useAuth();
  const navigation = useNavigation();
  const link = ({ isActive }) => (isActive ? "nav-link active" : "nav-link");
  return (
    <div className="min-h-screen">
      <LilaHead />
      <ProgressBar active={navigation.state !== "idle"} />
      <header className="flex items-center gap-1 border-b border-border px-6 py-3">
        <NavLink to="/" end className={link}>Home</NavLink>
        <NavLink to="/users" className={link}>Users</NavLink>
        <NavLink to="/account" className={link}>Account</NavLink>
        <WebOnly><NavLink to="/billing" className={link}>Billing</NavLink></WebOnly>
        <span className="ml-auto" />
        {user ? <Button size="sm" variant="outline" onClick={logout}>Log out</Button> : <Button size="sm" variant="outline" onClick={() => window.location.assign("/login")}>Sign in</Button>}
        <ThemeToggle />
      </header>
      <main className="mx-auto max-w-4xl p-8"><Outlet /></main>
      <Toaster />
    </div>
  );
}

function Home() {
  return (
    <Card title="Lila SPA" description="React Router + Lila UI kit">
      <Button onClick={() => toast.success("Hello from Lila")}>Toast</Button>
    </Card>
  );
}

const USERS = Array.from({ length: 30 }, (_, i) => ({ id: i + 1, name: `User ${i + 1}`, email: `user${i + 1}@example.com` }));

function Users() {
  return <DataTable rows={USERS} columns={[{ key: "id", label: "#", sortable: true }, { key: "name", label: "Name", sortable: true }, { key: "email", label: "Email" }]} />;
}

function User() {
  const { id } = useParams();
  return <Card title={`User ${id}`} />;
}

function Account() {
  const { user } = useAuth();
  return <RequireAuth page redirectTo="/login"><Card title={`Hi, ${user?.name}`} description={user?.email} /></RequireAuth>;
}

const router = createRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      { path: "users", element: <Users /> },
      { path: "users/:id", element: <User /> },
      { path: "account", element: <Account /> },
      { path: "billing", element: <Card title="Billing (web only)" /> },
      { path: "*", element: <Card title="Not found" /> },
    ],
  },
]);

createLilaSpa(() => (
  <AuthProvider>
    <RouterProvider router={router} />
  </AuthProvider>
));
