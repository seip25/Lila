import typer
import asyncio
import os
import sys
import shlex
import shutil

app = typer.Typer()

# Project root path / Ruta raíz del proyecto
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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

    # Read and print output line by line / Leer e imprimir línea por línea
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        sys.stdout.write(line.decode())
        sys.stdout.flush()

    return await process.wait()


async def create_react_app(name: str):
    """
    Create a new React app in the project root with Vite.
    Crea una nueva app React en la raíz del proyecto con Vite.
    """
    file_path = os.path.join(project_root, "main.py")

    # Check if main.py exists / Verificar si main.py existe
    if not os.path.exists(file_path):
        print("❌ You must first run lila-init in the terminal to create the lila application.\n"
              "❌ Primero debes ejecutar lila-init en la terminal para crear la aplicación lila.")
        return

    # Path where the React app will be created / Ruta donde se creará la app React
    project_dir = os.path.join(project_root, name)

    # Step 1: Create React app with Vite / Paso 1: Crear app React con Vite
    print(f"⚡ Creating React app '{name}' in {project_dir}...\n"
          f"⚡ Creando la app React '{name}' en {project_dir}...\n")
    #await run_command("npm install -g create-vite")
    #exit_code = await run_command(f"npm create vite@latest {shlex.quote(project_dir)} -- --template react")
    exit_code = await run_command(
        f"npx --yes create-vite {shlex.quote(name)} --template react"
        )


    if exit_code != 0:
        print("❌ Error creating React app / Error creando la app React.")
        return

    # Step 2: Install dependencies / Paso 2: Instalar dependencias
    print("\n📦 Installing dependencies...\n"
          "📦 Instalando dependencias...\n")
    exit_code = await run_command("npm install", cwd=project_dir)
    if exit_code != 0:
        print("❌ Error installing dependencies / Error instalando dependencias.")
        return

    # Step 3: Configure vite.config.js / Paso 3: Configurar vite.config.js
    vite_config_path = os.path.join(project_dir, "vite.config.js")
    with open(vite_config_path, "w") as f:
        f.write(
            """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, '../templates/html/react'), 
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  }
})

"""
        )

    # Step 4: Update CORS config in main.py / Paso 4: Actualizar configuración CORS en main.py
    print("\n🔧 Updating CORS configuration in main.py...\n"
          "🔧 Actualizando configuración CORS en main.py...\n")
    marker = "#react"
    replace_text = """
#English: for development react
#Espanol: para desarrollo react
cors={
    "origin": ["http://localhost:5173"],
    "allow_credentials" : True,
    "allow_methods":["*"],
    "allow_headers": ["*"]
}
app = App(debug=True, routes=all_routes, cors=cors)
    """

    with open(file_path, "r") as file:
        content = file.read()

    if marker in content:
        new_content = content.replace(marker, f"{marker}\n{replace_text}")
        with open(file_path, "w") as file:
            file.write(new_content)
        print("✅ CORS configuration inserted / Configuración CORS insertada")
    else:
        print("ℹ️ Marker not found / Marcador no encontrado")

    src_logo = os.path.join(project_root, "static/img/lila.png")
    dest_logo = os.path.join(project_dir, "src/assets/lila.png")
    os.makedirs(os.path.dirname(dest_logo), exist_ok=True)
    shutil.copyfile(src_logo, dest_logo)

    css_files = ["index.css", "App.css"]
    for css_file in css_files:
        path = os.path.join(project_dir, "src", css_file)
        if os.path.exists(path):
            os.remove(path)
            

    # Step 5: Final instructions / Paso 5: Instrucciones finales
    print("\n🎉 React app created successfully! / ¡App React creada exitosamente!\n")
    print(f"➡ cd {name}")
    print("➡ npm run dev  (start development server / iniciar servidor de desarrollo)")
    print("➡ Open your browser at http://localhost:5173 / Abre tu navegador en http://localhost:5173")
    print("➡ To build for production, run: npm run build / Para construir para producción, ejecuta: npm run build")
    print("➡ Update your routes in app/routes/routes.py to include the React app for production/ Actualiza tus rutas en app/routes/routes.py para incluir la app React para producción")
    print("""➡ Example/ Ejemplo: 
router.mount(path="/assets",directory="templates/html/react/assets",name="react-assets")
@router.route(path="/{path:path}", methods=["GET"])
async def home(request: Request):
    response = render(
        request=request, template="react/index"
    )  
    return response
    """)
    print("\nYou can now start developing your React app! / ¡Ahora puedes comenzar a desarrollar tu app React!\n")

@app.command()
def create(name: str = 'react'):
    """Create a new React application using Vite / Crear nueva app React usando Vite"""
    asyncio.run(create_react_app(name))


if __name__ == "__main__":
    app()



react_app_default_lila = """
import { useState } from 'react'
import lilaLogo from './assets/lila.png'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      {/* Tailwind CDN  */}
      <link href="https://cdn.jsdelivr.net/npm/tailwindcss@3.3.3/dist/tailwind.min.css" rel="stylesheet" />

      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 p-4">
        <div className="flex space-x-4 mb-6">
          <img src={lilaLogo} alt="Lila Logo" className="h-20 w-20" />
          <h1 className="text-4xl font-bold text-gray-800 dark:text-gray-100">React + Lila</h1>
        </div>

        <p className="text-center text-gray-600 dark:text-gray-400 mb-4">
          English: This is a simple React app using Lila as the backend framework.<br />
            Español: Esta es una app React simple usando Lila como framework de backend.
        </p>

        <p className="text-center text-gray-700 dark:text-gray-300 mb-4">
        English: You can use react-router or whatever you want to handle routes with react,
        modifying app/routes/routes.py to render the react index directly like this.<br />
        Español: Puedes utilizar react-router o lo que quieras para manejar las rutas con react,
        modificando app/routes/routes.py para que renderice el index de react directamente de esta forma.
        <br />
        <code className="block bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
        @router.route(path="/{path:path}", methods=["GET"])
        async def home(request: Request):
            response = render(
                request=request, template="react/index"
            )  
            return response
        </code>
        </p>

        <p className="text-center text-gray-700 dark:text-gray-300 mb-4">
            English: Remember that in <a href="/docs" target="_blank">docs</a> you can find the automatic documentation generated by Lila in app/routes/api.py.<br />
            
            Español: Recuerda que en  <a href="/docs" target="_blank">docs</a> puedes encontrar la documentación
            automatica generada por lila en app/routes/api.py .
        </p>

        <p className="text-center text-gray-700 dark:text-gray-300 mb-4">
          English: You can use Lila to have SEO recognizable by Google Bots, AI with hydration,
            and a caching system. Read the documentation with the example at https://seip25.github.io/Lila/documentation.html#react-seo  .<br />
          
          Español: Puedes usar Lila para tener SEO reconocible por Bots de Google,IA con hidratación
            y sistema de caching , lee la documentación con el ejemplo en https://seip25.github.io/Lila/documentation.html#react-seo .
        
        </p>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-md mb-6">
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
            onClick={() => setCount(count + 1)}
          >
            Count is {count}
          </button>
          <p className="mt-2 text-gray-600 dark:text-gray-300 text-sm">
            Click to test interactivity / Haz click para probar la interactividad
          </p>
        </div>

        <p className="text-gray-500 dark:text-gray-400 text-sm">
          🔗 Documentation: <a href="https://seip25.github.io/Lila" className="text-blue-500 hover:underline">https://seip25.github.io/Lila</a>
        </p>
      </div>
    </>
  )
}

export default App
"""