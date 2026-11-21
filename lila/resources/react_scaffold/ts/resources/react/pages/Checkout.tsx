import { Link } from "@lila";
import type { ReactElement } from "react";
import Layout from "../components/Layout";
import { Card, Form, Select, SubmitButton } from "../components/ui";

// Route declared with desktop=False: it does not exist in the desktop build.
export default function Checkout({ plans = [] }: { plans: string[] }) {
  return (
    <Card title="Checkout" description="Web only (desktop=False).">
      <Form action="/react/checkout" initial={{ plan: plans[0] ?? "" }} successToast className="max-w-sm">
        <Select name="plan" label="Plan" options={plans} />
        <SubmitButton>Buy</SubmitButton>
      </Form>
      <Link href="/react" className="lila-link mt-4 inline-block">Back</Link>
    </Card>
  );
}

Checkout.layout = (page: ReactElement) => <Layout>{page}</Layout>;
