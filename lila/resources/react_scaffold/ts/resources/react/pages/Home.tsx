import { DesktopOnly, Link, useLila, WebOnly } from "@lila";
import type { ReactElement } from "react";
import Layout from "../components/Layout";

// Props come from Python: react_render(request, "Home", {"framework": ..., "features": [...]})
interface HomeProps {
  framework: string;
  features: string[];
}

export default function Home({ framework, features = [] }: HomeProps) {
  const { desktop } = useLila();
  return (
    <section className="space-y-6">
      <h1 className="text-4xl font-bold tracking-tight">{framework} + React</h1>
      <p className="text-slate-600 dark:text-slate-300">
        Running as <strong>{desktop ? "desktop app" : "website"}</strong>. Edit{" "}
        <code>resources/react/pages/Home.tsx</code> and the page updates instantly (HMR).
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {features.map((feature) => (
          <li key={feature} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
            {feature}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <Link className="rounded-lg bg-primary px-4 py-2 text-white" href="/react/about">
          About (client navigation)
        </Link>
        {/* desktop=False route: the link disappears in the desktop build */}
        <Link className="rounded-lg border px-4 py-2" href="/react/checkout">
          Checkout (web only)
        </Link>
        <WebOnly>
          <a className="rounded-lg border px-4 py-2" href="/app">SPA demo</a>
        </WebOnly>
        <DesktopOnly>
          <span className="rounded-lg bg-emerald-100 px-4 py-2 text-emerald-800">Native features enabled</span>
        </DesktopOnly>
      </div>
    </section>
  );
}

Home.layout = (page: ReactElement) => <Layout>{page}</Layout>;
