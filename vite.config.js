import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";
import fs from 'fs';

function generateLilaPythonManifest() {
     return { 
        name : 'generate-lila-manifest',
        closeBundle(){
            const manifestPath = resolve(process.cwd(), 'public/build/.vite/manifest.json');
            const lilaOutPath= resolve(process.cwd(), 'app/build_manifest.py');
            if (!fs.existsSync(manifestPath)) {
                console.error('manifest.json not found');
                return;
            }
            const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
            let content=`manifest={ \n`;
            
            for (const [key, value] of Object.entries(manifest)) {
                const name = value["name"];
                const file = value["file"];
                if (name == "main") {
                content += `    "file": "${file}" ,`;
                if(value["css"]){
                    content +=`'css' : [${value["css"].map(c => `'${c}'`).join(', ')}],\n`;
                }
                }
            }
            content += `}`;
            fs.writeFileSync(lilaOutPath, content);
            console.log('✅ Created app/build_manifest.py');
        } 
     };
}

function watchLilaTemplates() {
    return {
        name: 'watch-lila-templates',
        configureServer(server) {
            const templateDir = resolve(process.cwd(), 'resources/templates');
            server.watcher.add(templateDir);
        },
        handleHotUpdate({ file, server }) {
            const normalizedFile = file.replace(/\\/g, '/');
            if (normalizedFile.includes('/resources/templates/') && 
               (normalizedFile.endsWith('.html') || normalizedFile.endsWith('.jinja') || normalizedFile.endsWith('.md'))) {
                server.ws.send({ type: 'full-reload' });
            }
        }
    };
}

export default defineConfig({
  plugins: [
    tailwindcss(),
    generateLilaPythonManifest(),
    watchLilaTemplates()
  ],
  base: "/public/build/",
  build: {
    manifest: true,
    outDir: 'public/build',
    publicDir: 'public',
    emptyOutDir: true,
    rollupOptions: {
      input: "./resources/js/main.js",
    }, 
  },
  server: {
    origin: "http://localhost:5173",
    host: "localhost",
    port: 5173,
  },
});
