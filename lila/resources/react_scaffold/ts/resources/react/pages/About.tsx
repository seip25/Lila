import { Link } from "@lila";
import type { ReactElement } from "react";
import Layout from "../components/Layout";

export default function About({ version }: { version: string }) {
  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold">About</h1>
      <p>Title, description and JSON-LD of this page come from react_render() in Python.</p>
      <p className="text-sm opacity-70">Lila {version}</p>
      <Link href="/react" className="text-primary underline">Back</Link>
    </section>
  );
}

About.layout = (page: ReactElement) => <Layout>{page}</Layout>;
