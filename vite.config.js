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
  base: "/public/",
  build: {
    manifest: true,
    outDir: 'public/',
    emptyOutDir: false,
    rollupOptions: {
      input: {
        tailwind: resolve(__dirname, 'resources/css/tailwind.css'),
        utils: resolve(__dirname, 'resources/js/utils.js'),
        spa: resolve(__dirname, 'resources/js/spa.js')
      }
    }
  },
  server: {
    origin: "http://localhost:5173",
    host: "localhost",
    port: 5173,
  },
});
