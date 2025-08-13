import typer
import asyncio
import os
import sys
import shlex

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

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../templates/html/react/build',
    rollupOptions: {
      output: {
        entryFileNames: `../static/build/[name].js`,
        chunkFileNames: `../static/build/[name].js`,
        assetFileNames: `../static/build/[name].[ext]`
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
#Español: para desarrollo react
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

    # Step 5: Final instructions / Paso 5: Instrucciones finales
    print("\n🎉 React app created successfully! / ¡App React creada exitosamente!\n")
    print(f"➡ cd {name}")
    print("➡ npm run dev  (start development server / iniciar servidor de desarrollo)")
    print("➡ Open your browser at http://localhost:5173 / Abre tu navegador en http://localhost:5173")
    print("➡ To build for production, run: npm run build / Para construir para producción, ejecuta: npm run build")
    print("➡ Update your routes in app/routes/routes.py to include the React app for production/ Actualiza tus rutas en app/routes/routes.py para incluir la app React para producción")
    print("""➡ Example/ Ejemplo: 
@router.route(path="/{path:path}", methods=["GET"])
async def home(request: Request):
    response = render( request=request, template="react/index") 
    return response
    """)
    print("\nYou can now start developing your React app! / ¡Ahora puedes comenzar a desarrollar tu app React!\n")

@app.command()
def create(name: str = 'react'):
    """Create a new React application using Vite / Crear nueva app React usando Vite"""
    asyncio.run(create_react_app(name))


if __name__ == "__main__":
    app()
