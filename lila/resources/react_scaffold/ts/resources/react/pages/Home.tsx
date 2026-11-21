import { DesktopOnly, useLila, WebOnly } from "@lila";
import type { ReactElement } from "react";
import Layout from "../components/Layout";
import { Badge, Button, Card } from "../components/ui";

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
      <div className="grid gap-3 sm:grid-cols-2">
        {features.map((feature) => (
          <Card key={feature} title={feature} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <Button href="/react/about">About (client navigation)</Button>
        {/* desktop=False route: the link disappears in the desktop build */}
        <Button href="/react/checkout" variant="outline">Checkout (web only)</Button>
        <WebOnly>
          <a className="btn-outline" href="/app">SPA demo + UI kit</a>
        </WebOnly>
        <DesktopOnly>
          <Badge tone="success" soft>Native features enabled</Badge>
        </DesktopOnly>
      </div>
    </section>
  );
}

Home.layout = (page: ReactElement) => <Layout>{page}</Layout>;
