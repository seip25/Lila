// Vite config for Lila + React. `lila react dev` / `lila react build` run it.
import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const HOST = process.env.VITE_HOST || "127.0.0.1";
const PORT = Number(process.env.VITE_PORT || 5173);
const HOT_FILE = path.resolve("public/build/hot");

// Entries: every file listed here can be used with react_render(entry=...),
// router.spa(entry=...) or {{ vite("...") }} in Jinja templates.
const INPUT = ["resources/react/main.jsx", "resources/react/spa.jsx"];

/** Writes public/build/hot so Lila (DEBUG=True) loads scripts from Vite (HMR). */
function lila() {
  const clean = () => {
    try { fs.rmSync(HOT_FILE); } catch {}
  };
  return {
    name: "lila",
    configureServer(server) {
      server.httpServer?.once("listening", () => {
        const address = server.httpServer.address();
        const port = typeof address === "object" && address ? address.port : PORT;
        fs.mkdirSync(path.dirname(HOT_FILE), { recursive: true });
        fs.writeFileSync(HOT_FILE, `http://${HOST}:${port}`);
      });
      process.once("exit", clean);
      for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
        process.once(signal, () => { clean(); process.exit(0); });
      }
    },
    buildStart() {
      clean();
    },
  };
}

export default defineConfig(({ command }) => ({
  // Production assets are served by Lila from public/build/.
  base: command === "build" ? "/public/build/" : "/",
  // public/ belongs to Lila: never copy it into the build.
  publicDir: false,
  plugins: [lila(), react(), tailwindcss()],
  resolve: {
    alias: {
      "@lila": path.resolve("resources/react/lila/index.tsx"),
      "@": path.resolve("resources/react"),
    },
  },
  server: {
    host: HOST,
    port: PORT,
    strictPort: true,
    origin: `http://${HOST}:${PORT}`,
    cors: true,
    watch: { ignored: ["**/app/**", "**/*.py", "**/public/**", "**/.venv/**"] },
  },
  build: {
    manifest: true,
    outDir: "public/build",
    emptyOutDir: true,
    rollupOptions: { input: INPUT },
  },
}));
