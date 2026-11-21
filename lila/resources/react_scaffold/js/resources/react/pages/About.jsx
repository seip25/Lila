import { Link } from "@lila";
import Layout from "../components/Layout.jsx";

export default function About({ version }) {
  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold">About</h1>
      <p>Title, description and JSON-LD of this page come from react_render() in Python.</p>
      <p className="text-sm opacity-70">Lila {version}</p>
      <Link href="/react" className="text-primary underline">Back</Link>
    </section>
  );
}

About.layout = (page) => <Layout>{page}</Layout>;
