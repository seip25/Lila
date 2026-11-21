import { Link } from "react-router";
import { Card } from "@/components/ui";

export default function NotFound() {
  return (
    <Card title="404" description="This page does not exist.">
      <Link className="lila-link" to="/">Home</Link>
    </Card>
  );
}
