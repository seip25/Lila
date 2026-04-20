import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer
import asyncio
import os
import sys
import orjson
from core.responses import orjson_dumps

app = typer.Typer()

project_root = os.getcwd()

def html_template_base()->str:
    html = """<!DOCTYPE html>
<html lang="{{ lang }}" >
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <meta http-equiv="X-UA-Compatible" content="ie=edge" />
    <meta name="description" content="{{ description }}" />
    <meta name="keywords" content="{{ keywords }}" />
    <meta name="author" content="{{ author }}" />
    <title>{{ title }}</title>
    <link rel="icon" type="image/x-icon" href="favicon.ico" />
    {{head | safe}}
    {{ hot_reload() | safe }}
    {{ vite_assets() | safe }}
  </head>
  <body >
        <div id="root" data-react-component="{{component}}" data-props="{{props}}"></div>
  </body>
</html>
    """
    return html


def html_template ()->str:
    html = """<!DOCTYPE html>
<html lang="{{ lang }}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <meta http-equiv="X-UA-Compatible" content="ie=edge" />
    <meta name="description" content="{{ description }}" />
    <meta name="keywords" content="{{ keywords }}" />
    <meta name="author" content="{{ author }}" />
    <title>{{ title }}</title>
    <link rel="icon" type="image/x-icon" href="favicon.ico" />
    <link rel="stylesheet" href="css/lila.css" />
    {{ hot_reload() | safe }}
  </head>
  <body>
    <main class="mt-4 container">
      <h1>Example React integration</h1>
      <div>{{ react('Counter', {'start': 3}) | safe }}</div>
    </main>
    {{ vite_assets() | safe }}
  </body>
</html>
    """
    return html

async def run_command(command, cwd=None):
    """
    Run a shell command and show output in real time.
    Ejecuta un comando de terminal mostrando la salida en vivo.
    """
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        sys.stdout.write(line.decode())
        sys.stdout.flush()

    return await process.wait()

async def create_react_env(name: str):
    """
    Scaffold React environment in project root.
    """
    react_dir = os.path.join(project_root, name)
    
    print(f"⚡ Setting up React '{name}' environment in {project_root}...\n")
    
    package_json_path = os.path.join(project_root, "package.json")
    if not os.path.exists(package_json_path):
        package_json = {
            "name": "lila-react-app",
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build"
            },
            "dependencies": {
              "react": "^19.2.4",
              "react-dom": "^19.2.4"
            },
            "devDependencies": {
               "@types/react": "^18.3.3",
                "@types/react-dom": "^18.3.0",
                "@vitejs/plugin-react": "^4.3.1",
                "vite": "^5.4.1"
            }
        }
        with open(package_json_path, "wb") as f:
            f.write(orjson.dumps(package_json, option=orjson.OPT_INDENT_2))
        print("✅ Created package.json")
    else:
        print("ℹ️ package.json already exists (skipping creation)")

    vite_config_path = os.path.join(project_root, "vite.config.js")
    vite_config_content = f"""import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";
import {{ resolve }} from "path";
import fs from 'fs';

function generateLilaPythonManifest() {{
     return {{ 
        name : 'generate-lila-manifest',
        closeBundle(){{
            const manifestPath = resolve(process.cwd(), 'public/build/.vite/manifest.json');
            const lilaOutPath= resolve(process.cwd(), 'app/build_manifest.py');
            if (!fs.existsSync(manifestPath)) {{
                console.error('manifest.json not found');
                return;
            }}
            const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
            let content=`manifest={{ \n`;
            
            for (const [key, value] of Object.entries(manifest)) {{
                const name = value["name"];
                const file = value["file"];
                if (name == "main") {{
                content += `    "file": "${{file}}" ,`;
                if(value["css"]){{
                    content +=`'css' : [${{value["css"].map(c => `'${{c}}'`).join(', ')}}],\n`;
                }}
                }}
            }}
            content += `}}`;
            fs.writeFileSync(lilaOutPath, content);
            console.log('✅ Created app/build_manifest.py');

        }} 
     }};
}}
 

function watchLilaTemplates() {{
    return {{
        name: 'watch-lila-templates',
        configureServer(server) {{
            server.watcher.add(resolve(process.cwd(), 'resources/templates/**/*.html'));
            server.watcher.add(resolve(process.cwd(), 'resources/templates/**/*.md'));
            server.watcher.add(resolve(process.cwd(), 'resources/templates/**/*.twig'));
        }},
        handleHotUpdate({{ file, server }}) {{
            if (file.includes('resources/templates') && (file.endsWith('.html') || file.endsWith('.md') || file.endsWith('.twig'))) {{
                server.ws.send({{ type: 'full-reload' }});
            }}
        }}
    }};
}}

export default defineConfig({{
  plugins: [
    react(),
    generateLilaPythonManifest(),
    watchLilaTemplates()
  ],
  base: "/public/build/",
  build: {{
    manifest: true,
    outDir: 'public/build',
    publicDir: 'public',
    emptyOutDir: true,
    rollupOptions: {{
      input: "./resources/js/main.jsx",
    }}, 
  }},
  server: {{
    origin: "http://localhost:5173",
    host: "localhost",
    port: 5173,
  }},
}});
"""
    with open(vite_config_path, "w", encoding="utf-8") as f:
        f.write(vite_config_content)
    print("✅ Created vite.config.js")

    os.makedirs(react_dir, exist_ok=True)
    
    main_jsx_path = os.path.join(react_dir, "main.jsx")
    main_jsx_content = """import { createRoot } from 'react-dom/client';

const componentModules = import.meta.glob('./pages/*.jsx');
const mountedRoots = new Map();

/**
 * Renders or re-renders React components found in the DOM.
 * 
 * @param {string} [name='all'] - The name of the component to render (matching data-react-component). Use "all" to render everything.
 */
window.renderReactComponent = async (name = 'all') => {
  document.querySelectorAll('[data-react-component]').forEach(async (el) => {
    const componentName = el.dataset.reactComponent;
    
    if (name !== 'all' && componentName !== name) return;

    const props = JSON.parse(el.dataset.props || '{}');
    const importer = componentModules[`./pages/${componentName}.jsx`];

    if (importer) {
      try {
        const module = await importer();
        const Component = module.default;

        if (!mountedRoots.has(el)) {
          mountedRoots.set(el, createRoot(el));
        }
        mountedRoots.get(el).render(<Component {...props} key={Math.random()} />);
      } catch (error) {
        console.error(`Failed to render React component: ${componentName}`, error);
      }
    }
  });
};

document.addEventListener('DOMContentLoaded', () => {
  window.renderReactComponent();
});

"""
    with open(main_jsx_path, "w", encoding="utf-8") as f:
        f.write(main_jsx_content)
    print(f"✅ Created {name}/main.jsx")

    main_css_path=os.path.join(react_dir,"globals.css")
    
    with open(main_css_path, "w", encoding="utf-8") as f:
        f.write(" ")
    print(f"✅ Created {name}/globals.css")

    components_dir = os.path.join(react_dir, "pages")
    os.makedirs(components_dir, exist_ok=True)

    counter_jsx_path = os.path.join(components_dir, "Counter.jsx")
    counter_jsx_content = """import React, { useState } from 'react'

export default function Counter({ start = 0 }) {
  const [count, setCount] = useState(start)

  return (
     <main className='container'>
     <article className="mt-8 max-w-sm">
      <h3>React Island: Counter</h3>
      <p>Current count: <strong>{count}</strong></p>
      <button 
        onClick={() => setCount(count + 1)} 
      >
        Increment
      </button>
    </article>
   </main>
  )
}
"""
    with open(counter_jsx_path, "w", encoding="utf-8") as f:
        f.write(counter_jsx_content)
    print(f"✅ Created {name}/pages/Counter.jsx")

    print("\n📦 Installing npm dependencies...\n")
    exit_code = await run_command("npm install", cwd=project_root)
    
    if exit_code == 0:
        print("\n🎉 React environment ready! / ¡Entorno React listo!\n")
        print("To start development server / Para iniciar servidor de desarrollo:")
        print("➡️  python -m cli.react dev")
        print("   OR / O")
        print("➡️  npm run dev")
    else:
        print("❌ Error installing dependencies.")

    html_template_path = os.path.join(project_root, "resources/templates/html/react.html")
    route_react="""

@router.get("/react-page")
async def react_page(request: Request):
    response =renderReact(request=request,component="Counter",
    props={
        "start": 5
    } ,
    options={
        "title": "React Page",
        "description": "A React page with a counter component",
        "keywords": "React, counter, component",
        "author": "Lila",
        "styles": ["css/lila.css"]
    }                      
    )
    return response

@router.get("/react")
async def react(request: Request):
    context ={
        "url": f"http://{HOST}:{PORT}"
    }
    response =render(
        request=request, template="react",context=context
    )
    return response
    """
    with open(html_template_path, "w", encoding="utf-8") as f:
        f.write(html_template())
    print("✅ Created resources/templates/html/react.html")
    marker_route_react="#marker_react"
    routes_path = os.path.join(project_root, "app/routes/routes.py")
    with open(routes_path, "r", encoding="utf-8") as f:
        routes_content = f.read()
    routes_content = routes_content.replace(marker_route_react, route_react)
    with open(routes_path, "w", encoding="utf-8") as f:
        f.write(routes_content)
    print("✅ Updated app/routes/routes.py")
    
    html_template_path_lila=os.path.join(project_root,"resources/templates/html/lila/react_base.html")
    with open(html_template_path_lila, "w", encoding="utf-8") as f:
        f.write(html_template_base())
    

@app.command()
def create(name: str = "resources"):
    """
    Setup React environment (Islands architecture).
    Configura el entorno React (Arquitectura de Islas).
    """
    asyncio.run(create_react_env(name))

@app.command()
def dev():
    """
    Run Vite development server.
    Ejecuta el servidor de desarrollo Vite.
    """
    print("🚀 Starting Vite dev server...")
    asyncio.run(run_command("npm run dev", cwd=project_root))

if __name__ == "__main__":
    app()
