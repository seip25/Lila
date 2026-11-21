import { Card } from "@/components/ui";

// Hidden in the desktop app with <WebOnly> (and keep its APIs desktop=False).
export default function Billing() {
  return <Card title="Billing" description="Web only." />;
}
