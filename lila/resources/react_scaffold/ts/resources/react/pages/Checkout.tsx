import { Link, useForm } from "@lila";
import type { ReactElement } from "react";
import Layout from "../components/Layout";

// Route declared with desktop=False: it does not exist in the desktop build.
export default function Checkout({ plans = [] }: { plans: string[] }) {
  const form = useForm({ plan: plans[0] ?? "" });
  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold">Checkout</h1>
      <form className="flex gap-3" onSubmit={form.handleSubmit("/react/checkout")}>
        <select className="rounded-lg border px-3 py-2" {...form.field("plan")}>
          {plans.map((plan) => (
            <option key={plan}>{plan}</option>
          ))}
        </select>
        <button className="rounded-lg border px-4 py-2" disabled={form.processing}>
          {form.processing ? "..." : "Buy"}
        </button>
      </form>
      {form.message && <p role="status">{form.message}</p>}
      {form.errors._form && <p role="alert" className="text-red-600">{form.errors._form}</p>}
      <Link href="/react" className="text-primary underline">Back</Link>
    </section>
  );
}

Checkout.layout = (page: ReactElement) => <Layout>{page}</Layout>;
