import { Link, useParams } from "react-router";
import { Card } from "@/components/ui";

export default function User() {
  const { id } = useParams();
  return (
    <Card title={`User ${id}`} description="The <title> comes from the router.spa() meta tree in Python.">
      <Link className="lila-link" to="/users">← Users</Link>
    </Card>
  );
}
