import { http, Link } from "@lila";
import { useState } from "react";
import Layout from "../components/Layout.jsx";

// Route declared with desktop=False: it does not exist in the desktop build.
export default function Checkout({ plans = [] }) {
  const [message, setMessage] = useState("");
  const buy = async (plan) => {
    try {
      const res = await http("/react/checkout", { method: "POST", body: { plan } });
      setMessage(res.message);
    } catch (error) {
      setMessage(error.message);
    }
  };
  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold">Checkout</h1>
      <div className="flex gap-3">
        {plans.map((plan) => (
          <button key={plan} className="rounded-lg border px-4 py-2" onClick={() => buy(plan)}>
            {plan}
          </button>
        ))}
      </div>
      {message && <p role="status">{message}</p>}
      <Link href="/react" className="text-primary underline">Back</Link>
    </section>
  );
}

Checkout.layout = (page) => <Layout>{page}</Layout>;
