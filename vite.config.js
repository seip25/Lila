import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";


function watchLilaTemplates() {
  return {
    name: 'watch-lila-templates',
    configureServer(server) {
      const templateDir = resolve(process.cwd(), 'resources');
      server.watcher.add(templateDir);
    },
    handleHotUpdate({ file, server }) {
      const normalizedFile = file.replace(/\\/g, '/');
      if (normalizedFile.includes('/resources/') &&
        (normalizedFile.endsWith('.html') || normalizedFile.endsWith('.jinja') || normalizedFile.endsWith('.md'))) {
        server.ws.send({ type: 'full-reload' });
      }
    }
  };
}

export default defineConfig({
  plugins: [
    tailwindcss(),
    watchLilaTemplates()
  ],
  base: "/public/build/",
  build: {
    manifest: true,
    outDir: 'public/build',
    publicDir: 'public',
    emptyOutDir: true,
  },
  server: {
    origin: "http://localhost:5173",
    host: "localhost",
    port: 5173,
  },
});
