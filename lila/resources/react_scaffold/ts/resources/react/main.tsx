// Pages rendered by react_render(request, "Name", props) in Python routes.
import "./app.css";
import { createLilaApp } from "@lila";

createLilaApp({
  // Lazy: every page is its own chunk. Use { eager: true } to bundle them all.
  pages: import.meta.glob("./pages/**/*.tsx"),
});
