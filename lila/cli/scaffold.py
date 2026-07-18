import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

# lila/cli/scaffold.py
import shutil
import os
from importlib import resources
from pathlib import Path

SCAFFOLD_ITEMS = {
    "main.py": "main.py",
    "app": "app",
    "public": "public",
    "resources": "resources",
    ".gitignore": ".gitignore",
    ".dockerignore": ".dockerignore",
    ".env": ".env",
    "AGENTS.md": "AGENTS.md",
    "docker-compose.yml": "docker-compose.yml",
    "docker": "docker",
}

def copy_item(
    source_package_name, item_name_in_package, destination_base_path, item_name_in_dest
):
    def _do_copy(src_path: Path):
        dest_path = Path(destination_base_path) / item_name_in_dest
        
        if src_path.resolve() == dest_path.resolve():
            print(
                f"  ℹ️ Omitiendo '{item_name_in_package}' porque origen y destino son iguales. / "
                f"Skipping '{item_name_in_package}' because source and destination are the same."
            )
            return

        if src_path.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            print(
                f"  📂 Directorio '{item_name_in_package}' copiado a '{dest_path}'. / "
                f"Directory '{item_name_in_package}' copied to '{dest_path}'."
            )
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            print(
                f"  📄 Archivo '{item_name_in_package}' copiado a '{dest_path}'. / "
                f"File '{item_name_in_package}' copied to '{dest_path}'."
            )

    try:
        try:
            with resources.path(source_package_name, item_name_in_package) as source_path:
                if source_path.exists():
                    _do_copy(source_path)
                    return
        except (ModuleNotFoundError, ImportError):
            pass

        repo_root = Path(__file__).resolve().parent.parent
        source_path = repo_root / item_name_in_package
        if source_path.exists():
            _do_copy(source_path)
        else:
            print(
                f"  ⚠️ Advertencia: Recurso '{item_name_in_package}' no encontrado. Omitiendo. / "
                f"Warning: Resource '{item_name_in_package}' not found. Skipping."
            )
    except Exception as e:
        print(
            f"  ❌ Error al copiar '{item_name_in_package}': {e}. / "
            f"Error copying '{item_name_in_package}': {e}."
        )


def _prompt(label_en: str, label_es: str, default: str) -> str:
    """
    English: Prompts the user for input with a default value. Press Enter to accept the default.
    Español: Solicita input al usuario con un valor por defecto. Presionar Enter para aceptar el default.
    """
    value = input(f"  {label_es} / {label_en} [{default}]: ").strip()
    return value if value else default


def _to_docker_name(name: str) -> str:
    """
    English: Sanitizes a project name for Docker container/network naming.
             Replaces spaces and hyphens with underscores, lowercases everything.
    Español: Sanitiza un nombre de proyecto para contenedores/redes Docker.
    """
    import re
    name = name.strip().lower()
    name = re.sub(r'[\s\-]+', '_', name)  # spaces and hyphens -> underscores
    name = re.sub(r'[^a-z0-9_]', '', name)  # remove non-alphanumeric/underscore
    return name or "lila_project"


def _collect_project_info(project_dir_name: str) -> dict:
    """
    English: Interactively collects project metadata and optional database config.
    Español: Recolecta interactivamente los metadatos del proyecto y la config de DB opcional.
    """
    default_title = project_dir_name.replace("_", " ").replace("-", " ").title()
    default_docker_name = _to_docker_name(project_dir_name)

    print("\n📝 Configuración del proyecto / Project configuration")
    print("   (Presiona Enter para usar el valor por defecto / Press Enter to use defaults)\n")

    project_name_raw = _prompt("Project name (used for Docker containers)", "Nombre del proyecto (para Docker)", project_dir_name)
    docker_name = _to_docker_name(project_name_raw)

    info = {
        "LILA_PROJECT_NAME": docker_name,
        "TITLE_PROJECT": _prompt("Project title", "Título del proyecto", default_title),
        "DESCRIPTION_PROJECT": _prompt("Description", "Descripción", ""),
        "AUTHOR_DEFAULT": _prompt("Author", "Autor", ""),
        "LANG_DEFAULT": _prompt("Default language (en/es/...)", "Idioma por defecto (en/es/...)", "en"),
        "DESCRIPTION_DEFAULT": _prompt("SEO meta description", "SEO meta descripción", "A Python web framework"),
        "KEYWORDS_DEFAULT": _prompt("SEO keywords", "SEO palabras clave", "Python, web, framework"),
        # DB defaults (SQLite unless user sets up MySQL)
        "DB_TYPE": "sqlite",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "3306",
        "DB_NAME": docker_name,
        "DB_USER": "root",
        "DB_PASSWORD": "root",
    }

    # ── MySQL setup ────────────────────────────────────────────────────────────
    print("\n🗄️  Configuración de base de datos / Database setup")
    setup_mysql = input("  ¿Quieres configurar MySQL ahora? / Configure MySQL now? [s/N]: ").strip().lower()
    if setup_mysql in ("s", "y", "si", "yes"):
        info["DB_TYPE"] = "mysql"
        info["DB_HOST"] = _prompt("MySQL host", "Host MySQL", "127.0.0.1")
        info["DB_PORT"] = _prompt("MySQL port", "Puerto MySQL", "3306")
        info["DB_NAME"] = _prompt("Database name", "Nombre de la base de datos", docker_name)
        info["DB_USER"] = _prompt("MySQL user", "Usuario MySQL", "root")
        info["DB_PASSWORD"] = _prompt("MySQL password", "Contraseña MySQL", "root")
        print("  ✅ MySQL configurado. Las credenciales se guardarán en .env / MySQL configured. Credentials saved to .env")
    else:
        print("  ℹ️  Usando SQLite por defecto / Using SQLite by default (app/connections.py)")

    return info


def _write_env_file(env_path: Path, project_info: dict) -> None:
    """
    English: Writes the .env file with project metadata, DB config, and Docker vars.
    Español: Escribe el archivo .env con metadatos del proyecto, config DB y vars Docker.
    """
    import secrets
    secret_key = secrets.token_hex(32)
    env_content = f"""# ─── Server ────────────────────────────────────────────────
SECRET_KEY='{secret_key}'
DEBUG=True
PORT=8000
HOST="127.0.0.1"
JIT=False
WORKERS="1"

# ─── Application URL ─────────────────────────────────────────
# English: Production URL for sitemaps, robots.txt, and canonical links.
#          Leave empty in development — the framework uses http://HOST:PORT automatically.
# Español: URL de producción para sitemaps, robots.txt y links canónicos.
#          Example: APP_URL="https://my-lila-app.com"
APP_URL=""

# ─── Project Metadata ─────────────────────────────────────────
TITLE_PROJECT='{project_info["TITLE_PROJECT"]}'
VERSION_PROJECT='1'
DESCRIPTION_PROJECT='{project_info["DESCRIPTION_PROJECT"]}'
LANG_DEFAULT='{project_info["LANG_DEFAULT"]}'

# ─── SEO Defaults ───────────────────────────────────────────────
DESCRIPTION_DEFAULT="{project_info["DESCRIPTION_DEFAULT"]}"
KEYWORDS_DEFAULT="{project_info["KEYWORDS_DEFAULT"]}"
AUTHOR_DEFAULT="{project_info["AUTHOR_DEFAULT"]}"

# ─── Docker / Deployment ────────────────────────────────────────
# English: Used by docker-compose.yml to name containers and networks uniquely.
#          Change PORT / DB_PORT if another project uses the same port on this server.
# Español: Usado por docker-compose.yml para nombrar contenedores y redes de forma única.
LILA_PROJECT_NAME={project_info["LILA_PROJECT_NAME"]}
DB_NAME={project_info["DB_NAME"]}
DB_USER={project_info["DB_USER"]}
DB_PASSWORD={project_info["DB_PASSWORD"]}
DB_PORT={project_info["DB_PORT"]}
"""
    env_path.write_text(env_content.lstrip(), encoding="utf-8")


def _write_connections_file(connections_path: Path, project_info: dict) -> None:
    """
    English: Writes app/connections.py with the database configuration chosen during lila-init.
    Español: Escribe app/connections.py con la configuración de base de datos elegida en lila-init.
    """
    if project_info["DB_TYPE"] == "mysql":
        connections_content = f"""from lila.core.database import Database
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────────────────────
# MySQL connection — configured during lila-init
# Credentials are read from .env (so Docker Compose and local dev share them).
# pool_size: max threads that can hit the DB simultaneously (for async routes)
# max_overflow: extra threads allowed beyond pool_size under peak load
# ────────────────────────────────────────────────────────────────────────────
config = {{
    "type": "mysql",
    "host": os.getenv("DB_HOST", "{project_info['DB_HOST']}"),
    "port": int(os.getenv("DB_PORT", "{project_info['DB_PORT']}")),
    "user": os.getenv("DB_USER", "{project_info['DB_USER']}"),
    "password": os.getenv("DB_PASSWORD", "{project_info['DB_PASSWORD']}"),
    "database": os.getenv("DB_NAME", "{project_info['DB_NAME']}"),
    "auto_commit": False,
    "pool_size": 20,
    "max_overflow": 40,
}}
connection = Database(config=config)
connection.connect()

# Example: ORM session usage
# db_session = connection.get_session()

# Example: async route (non-blocking, with query deduplication)
# from lila.core.base_model import BaseModel
# items = await MyModel.get_all_async(limit=100)
"""
    else:
        connections_content = """from lila.core.database import Database
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────────────────────
# SQLite connection (default — no setup required for development)
# To switch to MySQL, update this config and set DB_* vars in .env
# ────────────────────────────────────────────────────────────────────────────
config = {"type": "sqlite", "database": "lila"}
connection = Database(config=config)
connection.connect()

# To use MySQL instead, replace config above with:
# import os
# config = {
#     "type": "mysql",
#     "host": os.getenv("DB_HOST", "127.0.0.1"),
#     "port": int(os.getenv("DB_PORT", "3306")),
#     "user": os.getenv("DB_USER", "root"),
#     "password": os.getenv("DB_PASSWORD", "root"),
#     "database": os.getenv("DB_NAME", "lila_db"),
#     "auto_commit": False,
#     "pool_size": 20,
#     "max_overflow": 40,
# }

# Example: async route (non-blocking, with query deduplication)
# from lila.core.base_model import BaseModel
# items = await MyModel.get_all_async(limit=100)
"""
    connections_path.write_text(connections_content.lstrip(), encoding="utf-8")


def main():
    destination_base_path = Path(os.getcwd())
    project_dir_name = os.path.basename(destination_base_path)

    if list(destination_base_path.glob('*')):
        print(
            "⚠️ Advertencia: El directorio actual no está vacío. Los archivos del proyecto Lila se copiarán aquí. / "
            "Warning: The current directory is not empty. Lila project files will be copied here."
        )
        input("Presiona Enter para continuar o Ctrl+C para cancelar. / Press Enter to continue or Ctrl+C to cancel...")

    try:
        # English: Collect project info from user BEFORE copying files.
        # Español: Recolectar info del proyecto del usuario ANTES de copiar archivos.
        project_info = _collect_project_info(project_dir_name)

        print(
            f"\n🛠️  Construyendo el esqueleto del proyecto en el directorio actual usando Lila Framework... / "
            f"Scaffolding project in the current directory using Lila Framework..."
        )

        for item_pkg_name, item_dest_name in SCAFFOLD_ITEMS.items():
            copy_item("lila", item_pkg_name, destination_base_path, item_dest_name)

        # English: Overwrite the scaffolded .env with user-customized values.
        # Español: Sobreescribir el .env scaffolded con los valores personalizados del usuario.
        env_path = destination_base_path / ".env"
        _write_env_file(env_path, project_info)
        print(
            f"  ✨ .env generado con la configuración del proyecto. / "
            f".env generated with project configuration."
        )

        # English: Overwrite app/connections.py with chosen database config.
        # Español: Sobreescribir app/connections.py con la config de DB elegida.
        connections_path = destination_base_path / "app" / "connections.py"
        if connections_path.exists():
            _write_connections_file(connections_path, project_info)
            print(
                f"  🔗 app/connections.py actualizado con la configuración de base de datos. / "
                f"app/connections.py updated with database configuration."
            )

        # English: Generate requirements.txt if it does not exist.
        # Español: Generar requirements.txt si no existe.
        req_path = destination_base_path / "requirements.txt"
        if not req_path.exists():
            req_path.write_text("lila-framework\n", encoding="utf-8")
            print(
                f"Archivo 'requirements.txt' generado. / "
                f"File 'requirements.txt' generated."
            )

        readme_content = f"""
# {project_info["TITLE_PROJECT"]}

{project_info["DESCRIPTION_PROJECT"]}

# Learning Lila
https://seip25.github.io/Lila 

# Documentación de Lila
https://seip25.github.io/Lila

¡Feliz desarrollo! 🚀
"""
        with open(destination_base_path / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print(
            f"📄 README.md básico creado en el directorio actual. / "
            f"Basic README.md created in the current directory."
        )

        print(
            "\n🎉 ¡Proyecto Lila inicializado exitosamente en el directorio actual! / "
            "Lila project initialized successfully in the current directory!"
        )
        print(
            "➡️  Ahora, revisa los archivos generados en este directorio. / "
            "Now, review the generated files in this directory."
        )
        print(
            "   Sigue las instrucciones en el README.md generado. / "
            "Follow the instructions in the generated README.md."
        )

    except Exception as e:
        print(
            f"\n❌ Ocurrió un error durante la creación del proyecto: {e}. / "
            f"An error occurred during project creation: {e}."
        )
        if destination_base_path.exists() and not any(destination_base_path.iterdir()):
            try:
                destination_base_path.rmdir()
                print(
                    f"🧹 Directorio del proyecto incompleto eliminado: {destination_base_path}. / "
                    f"Incomplete project directory deleted: {destination_base_path}."
                )
            except Exception as cleanup_e:
                print(
                    f"⚠️ No se pudo eliminar automáticamente el directorio '{destination_base_path}': {cleanup_e}. Por favor, elimínalo manualmente. / "
                    f"Could not automatically delete directory '{destination_base_path}': {cleanup_e}. Please delete it manually."
                )


if __name__ == "__main__":
    main()
