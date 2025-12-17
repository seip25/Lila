import typer
import asyncio
import os
import sys
import shlex
import shutil
import json

app = typer.Typer()

project_root = os.getcwd()

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
    <link rel="icon" type="image/x-icon" href="{{ public('img/lila.png') }}" />
    <link rel="stylesheet" href="{{ public('css/lila.css') }}" />
    {{ vite_assets() | safe }}
  </head>
  <body>
    <main class="mt-4 container">
      <h1>Example React integration</h1>
      <div>{{ react('Counter', {'start': 3}) | safe }}</div>
    </main>
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
                "react": "^18.3.1",
                "react-dom": "^18.3.1"
            },
            "devDependencies": {
                "@types/react": "^18.3.3",
                "@types/react-dom": "^18.3.0",
                "@vitejs/plugin-react": "^4.3.1",
                "vite": "^5.4.1"
            }
        }
        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2)
        print("✅ Created package.json")
    else:
        print("ℹ️ package.json already exists (skipping creation)")

    vite_config_path = os.path.join(project_root, "vite.config.js")
    vite_config_content = f"""import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";
import {{ resolve }} from "path";

export default defineConfig({{
  plugins: [react()],
  base: "/public/build/",
  build: {{
    manifest: true,
    outDir: "public/build",
    emptyOutDir: true,
    rollupOptions: {{
      input: "./react/main.jsx",
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
    main_jsx_content = """import React from 'react'
import ReactDOM from 'react-dom/client'

const modules = import.meta.glob('./components/*.jsx')

const components = {}
for (const path in modules) {
  const name = path.match(/\\/([^\\/]+)\\.jsx$/)[1]
  components[name] = modules[path]
}

const mountComponents = async () => {
    const nodes = document.querySelectorAll('[data-react-component]')
    
    for (const node of nodes) {
        const name = node.dataset.reactComponent
        const props = JSON.parse(node.dataset.props || '{}')
        
        if (components[name]) {
            const module = await components[name]()
            const Component = module.default
            
            ReactDOM.createRoot(node).render(
                <React.StrictMode>
                    <Component {...props} />
                </React.StrictMode>
            )
        } else {
            console.error(`React Component '${name}' not found. Available: ${Object.keys(components).join(', ')}`)
        }
    }
}

document.addEventListener('DOMContentLoaded', mountComponents)
"""
    with open(main_jsx_path, "w", encoding="utf-8") as f:
        f.write(main_jsx_content)
    print(f"✅ Created {name}/main.jsx")

    components_dir = os.path.join(react_dir, "components")
    os.makedirs(components_dir, exist_ok=True)

    counter_jsx_path = os.path.join(components_dir, "Counter.jsx")
    counter_jsx_content = """import React, { useState } from 'react'

export default function Counter({ start = 0 }) {
  const [count, setCount] = useState(start)

  return (
    <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px', maxWidth: '300px' }}>
      <h3>React Island: Counter</h3>
      <p>Current count: <strong>{count}</strong></p>
      <button 
        onClick={() => setCount(count + 1)}
        style={{ padding: '0.5rem 1rem', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
      >
        Increment
      </button>
    </div>
  )
}
"""
    with open(counter_jsx_path, "w", encoding="utf-8") as f:
        f.write(counter_jsx_content)
    print(f"✅ Created {name}/components/Counter.jsx")

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

    html_template_path = os.path.join(project_root, "templates/html/react.html")
    route_react="""
@router.get("/react")
async def react(request: Request):
    context ={
        "url": f"http://{HOST}:{PORT}"
    }
    response = render(
        request=request, template="react",context=context
    )
    return response
    """
    with open(html_template_path, "w", encoding="utf-8") as f:
        f.write(html_template())
    print("✅ Created templates/html/react.html")
    marker_route_react="#marker_react"
    routes_path = os.path.join(project_root, "app/routes/routes.py")
    with open(routes_path, "r", encoding="utf-8") as f:
        routes_content = f.read()
    routes_content = routes_content.replace(marker_route_react, route_react)
    with open(routes_path, "w", encoding="utf-8") as f:
        f.write(routes_content)
    print("✅ Updated app/routes/routes.py")
    
    

@app.command()
def create(name: str = "react"):
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
