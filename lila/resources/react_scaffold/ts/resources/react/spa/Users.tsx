import { Link } from "react-router";
import { Badge, DataTable } from "@/components/ui";

interface Row {
  id: number;
  name: string;
  email: string;
  role: string;
  active: boolean;
}

const ROWS: Row[] = Array.from({ length: 42 }, (_, i) => ({
  id: i + 1,
  name: `User ${i + 1}`,
  email: `user${i + 1}@example.com`,
  role: i % 7 === 0 ? "admin" : "user",
  active: i % 5 !== 0,
}));

// Local rows here; for the database use <DataTable url="/api/users" /> with a
// route returning await User.paginate_async(page, per_page) ({items, total}).
export default function Users() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-black">Users</h1>
        <p className="text-sm text-muted-foreground">Search, sort and paginate</p>
      </div>
      <DataTable<Row>
        rows={ROWS}
        columns={[
          { key: "id", label: "#", sortable: true, align: "right" },
          { key: "name", label: "Name", sortable: true, render: (row) => <Link className="lila-link" to={`/users/${row.id}`}>{row.name}</Link>, value: (row) => row.name },
          { key: "email", label: "Email", hideOnMobile: true },
          { key: "role", label: "Role", sortable: true, render: (row) => <Badge tone={row.role === "admin" ? "primary" : "default"} soft>{row.role}</Badge>, value: (row) => row.role },
          { key: "active", label: "Status", render: (row) => (row.active ? <Badge tone="success" soft>active</Badge> : <Badge tone="danger" soft>inactive</Badge>), searchable: false },
        ]}
        onEdit={(row) => alert(`Edit ${row.name}`)}
        onDelete={() => undefined}
      />
    </div>
  );
}
