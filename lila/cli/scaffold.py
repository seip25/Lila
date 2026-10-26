import sys
import os
import shutil
import socket
from pathlib import Path
from importlib import resources

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

SCAFFOLD_ITEMS = {
    "main.py": "main.py",
    "app": "app",
    "public": "public",
    "resources": "resources",
    ".gitignore": ".gitignore",
    ".env_example": ".env_example",
    "AGENTS.md": "AGENTS.md",
}

def copy_item(source_package_name, item_name_in_package, destination_base_path, item_name_in_dest):
    def _do_copy(src_path: Path):
        dest_path = Path(destination_base_path) / item_name_in_dest
        
        if src_path.resolve() == dest_path.resolve():
            return

        if src_path.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            print(f"  📂 Directoy '{item_name_in_package}' -> '{dest_path}'.")
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            print(f"  📄 File '{item_name_in_package}' -> '{dest_path}'.")

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
            print(f"  ⚠️ Warning: Resource '{item_name_in_package}' not found. Skipping.")
    except Exception as e:
        print(f"  ❌ Error copying '{item_name_in_package}': {e}")

def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

def _prompt(label_en: str, label_es: str, default: str) -> str:
    value = input(f"  {label_es} / {label_en} [{default}]: ").strip()
    return value if value else default

def _collect_project_info(project_dir_name: str) -> dict:
    default_title = project_dir_name.replace("_", " ").replace("-", " ").title()

    print("\n📝 Configuración del proyecto / Project configuration (Lila v2.0.0)")
    print("   (Presiona Enter para usar los valores por defecto / Press Enter for defaults)\n")

    suggested_port = "8000"
    if _is_port_in_use(8000):
        for p in range(8001, 8020):
            if not _is_port_in_use(p):
                suggested_port = str(p)
                break

    app_port = _prompt("HTTP port", "Puerto HTTP", suggested_port)

    info = {
        "PORT": app_port,
        "TITLE_PROJECT": _prompt("Project title", "Título del proyecto", default_title),
        "DESCRIPTION_PROJECT": _prompt("Description", "Descripción", "Full-Stack Python Application"),
        "AUTHOR_DEFAULT": _prompt("Author", "Autor", ""),
        "LANG_DEFAULT": _prompt("Default language (en/es/...)", "Idioma por defecto (en/es/...)", "en"),
        "DESCRIPTION_DEFAULT": _prompt("SEO meta description", "SEO meta descripción", "Built with Lila Framework v2.0"),
        "KEYWORDS_DEFAULT": _prompt("SEO keywords", "SEO palabras clave", "python, starlette, spa, web, framework"),
        "CACHE_DRIVER": "memory",
        "DB_TYPE": "sqlite",
        "DB_NAME": "lila",
    }

    # Database options
    print("\n🗄️  Configuración de Base de Datos / Database Setup")
    print("   Lila v2.0 incluye SQLite Async (WAL mode) con cero infraestructura.")
    setup_db = input("   ¿Deseas usar MySQL o PostgreSQL en vez de SQLite? [s/N]: ").strip().lower()
    if setup_db in ("s", "y", "si", "yes"):
        db_choice = input("   Tipo de base de datos (mysql/postgresql) [mysql]: ").strip().lower() or "mysql"
        info["DB_TYPE"] = db_choice
        info["DB_HOST"] = _prompt("Database host", "Host de Base de Datos", "127.0.0.1")
        info["DB_PORT"] = _prompt("Database port", "Puerto", "3306" if db_choice == "mysql" else "5432")
        info["DB_NAME"] = _prompt("Database name", "Nombre de la base de datos", "lila_db")
        info["DB_USER"] = _prompt("Database user", "Usuario", "root" if db_choice == "mysql" else "postgres")
        info["DB_PASSWORD"] = _prompt("Database password", "Contraseña", "")
    else:
        print("  ✅ SQLite Async WAL mode configurado por defecto.")

    return info

def _write_env_file(env_path: Path, project_info: dict) -> None:
    import secrets
    secret_key = secrets.token_hex(32)
    db_type = project_info.get("DB_TYPE", "sqlite")
    
    db_extra = ""
    if db_type != "sqlite":
        db_extra = f"""DB_HOST="{project_info.get('DB_HOST', '127.0.0.1')}"
DB_PORT={project_info.get('DB_PORT', 3306)}
DB_USER="{project_info.get('DB_USER', 'root')}"
DB_PASSWORD="{project_info.get('DB_PASSWORD', '')}"
"""

    env_content = f"""# ─── Server Configuration ────────────────────────────────
SECRET_KEY='{secret_key}'
DEBUG=True
PORT={project_info.get("PORT", "8000")}
HOST="127.0.0.1"
JIT=False
WORKERS="2"

# ─── Application URL ────────────────────────────────────
APP_URL=""

# ─── Project Metadata ───────────────────────────────────
TITLE_PROJECT='{project_info["TITLE_PROJECT"]}'
VERSION_PROJECT='2.0.0'
DESCRIPTION_PROJECT='{project_info["DESCRIPTION_PROJECT"]}'
LANG_DEFAULT='{project_info["LANG_DEFAULT"]}'

# ─── SEO Defaults ───────────────────────────────────────
DESCRIPTION_DEFAULT="{project_info["DESCRIPTION_DEFAULT"]}"
KEYWORDS_DEFAULT="{project_info["KEYWORDS_DEFAULT"]}"
AUTHOR_DEFAULT="{project_info["AUTHOR_DEFAULT"]}"

# ─── Cache Driver (memory | redis) ───────────────────────
CACHE_DRIVER="memory"

# If CACHE_DRIVER="redis":
REDIS_HOST="127.0.0.1"
REDIS_PORT=6379
REDIS_PASSWORD=""
REDIS_URL=""

# ─── Database Configuration ──────────────────────────────
DB_TYPE="{db_type}"
DB_NAME="{project_info.get('DB_NAME', 'lila')}"
{db_extra}
# ─── AI Integration (core/ia.py) ─────────────────────────
OPENAI_API_KEY=""
DEEPSEEK_API_KEY=""
GEMINI_API_KEY=""

# ─── Better Auth OAuth Providers ─────────────────────────
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GITHUB_CLIENT_ID=""
GITHUB_CLIENT_SECRET=""
DISCORD_CLIENT_ID=""
DISCORD_CLIENT_SECRET=""
"""
    env_path.write_text(env_content.lstrip(), encoding="utf-8")

def main():
    destination_base_path = Path(os.getcwd())
    project_dir_name = os.path.basename(destination_base_path)

    if list(destination_base_path.glob('*')):
        print(
            "⚠️ Advertencia: El directorio actual no está vacío. Los archivos del proyecto Lila se copiarán aquí. / "
            "Warning: The current directory is not empty. Lila project files will be copied here."
        )
        input("Presiona Enter para continuar o Ctrl+C para cancelar... / Press Enter to continue...")

    try:
        project_info = _collect_project_info(project_dir_name)

        print("\n🛠️  Scaffolding project with Lila Framework v2.0.0...")

        for item_pkg_name, item_dest_name in SCAFFOLD_ITEMS.items():
            copy_item("lila", item_pkg_name, destination_base_path, item_dest_name)

        env_path = destination_base_path / ".env"
        _write_env_file(env_path, project_info)
        print("  ✨ .env generated successfully.")

        req_path = destination_base_path / "requirements.txt"
        if not req_path.exists():
            req_path.write_text("lila-framework>=2.0.0\n", encoding="utf-8")
            print("  📄 requirements.txt generated.")

        readme_content = f"""# {project_info["TITLE_PROJECT"]}

{project_info["DESCRIPTION_PROJECT"]}

Built with **Lila Framework v2.0.0** — Full-Stack Python SPA, SQLite WAL mode, and Desktop ready.

## Quick Start
```bash
# Run local dev server with auto-reload
lila dev

# Run as native desktop application
lila desktop dev

# Compile desktop executable
lila desktop build
```

## Documentation
https://seip25.github.io/Lila
"""
        with open(destination_base_path / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("  📄 README.md created.")

        print("\n🎉 ¡Proyecto Lila v2.0 inicializado con éxito! / Lila v2.0 project scaffolded successfully!")
        print("➡️  Ejecuta 'lila dev' para arrancar el servidor con hot-reload.")

    except Exception as e:
        print(f"\n❌ Error during project creation: {e}")

if __name__ == "__main__":
    main()
