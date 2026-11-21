import sys
import os
import shutil
import socket
from pathlib import Path
from importlib import resources

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
    def _safe_copy_tree(src_path: Path, dest_path: Path, ignore=None):
        for source in src_path.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(src_path)
            if "__pycache__" in relative.parts or source.suffix in (".pyc", ".pyo"):
                continue
            if ignore and any(part in ("admin", "lila") for part in relative.parts):
                continue
            target = dest_path / relative
            if target.exists():
                continue  # never destroy user files on re-init
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _do_copy(src_path: Path):
        dest_path = Path(destination_base_path) / item_name_in_dest

        if src_path.resolve() == dest_path.resolve():
            return

        if src_path.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
            ignore = item_name_in_package == "resources"
            _safe_copy_tree(src_path, dest_path, ignore=ignore)
            print(f"  📂 Directory '{item_name_in_package}' -> '{dest_path}' (existing files preserved).")
        else:
            if dest_path.exists():
                print(f"  ℹ️ File '{item_name_in_dest}' already exists; preserved.")
                return
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

_ASSUME_DEFAULTS = False


def _prompt(label_en: str, label_es: str, default: str) -> str:
    if _ASSUME_DEFAULTS:
        return default
    value = input(f"  {label_es} / {label_en} [{default}]: ").strip()
    return value if value else default


# `lila init --template X`: the scaffold plus these existing generators.
TEMPLATES = {
    "web": "Jinja pages + lila-client SPA (default)",
    "react": "web + React/Vite (TypeScript) with the UI kit",
    "auth": "web + Jinja auth (login, register, dashboard, profile)",
    "react-auth": "react + React auth pages",
    "full": "react + React auth + React admin panel",
    "desktop": "react + desktop app notes (DESKTOP_EXCLUDE, installers)",
}


def apply_template(template: str, install: bool = False) -> None:
    """Runs the generators a template needs inside the new project."""
    template = (template or "web").lower()
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template '{template}'. Use one of: {', '.join(TEMPLATES)}")
    if template == "web":
        return
    if template in ("react", "react-auth", "full", "desktop"):
        from lila.cli.react import init as react_init

        react_init(install=install, force=False, routes=True, js=False)
    if template == "auth":
        from lila.cli.auth import generate as auth_generate

        auth_generate(template=True, routes=True, react=False)
    if template in ("react-auth", "full"):
        from lila.cli.auth import generate as auth_generate

        auth_generate(template=None, routes=True, react=True)
    if template == "full":
        import secrets as _secrets
        from lila.cli.create_panel_admin import create as admin_create

        admin_create(username="admin", password=_secrets.token_urlsafe(12), react=True)
    if template == "desktop":
        env_path = Path(".env")
        if env_path.exists() and "DESKTOP_EXCLUDE" not in env_path.read_text(encoding="utf-8"):
            with open(env_path, "a", encoding="utf-8") as fh:
                fh.write(
                    "\n# ─── Desktop (lila desktop dev/build) ───────────────────\n"
                    "# Web-only routes left out of the desktop app (paths, globs, name:route)\n"
                    'DESKTOP_EXCLUDE=""\n'
                )
        print("  🖥️  Desktop: pip install \"lila-framework[desktop]\" · lila desktop dev · "
              "lila desktop build --installer auto")

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
    try:
        port_value = int(app_port)
        if not (1 <= port_value <= 65535):
            raise ValueError
        app_port = str(port_value)
    except ValueError:
        print(f"  ⚠️ Invalid port '{app_port}', using {suggested_port}.")
        app_port = suggested_port

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
    setup_db = "" if _ASSUME_DEFAULTS else input("   ¿Deseas usar MySQL o PostgreSQL en vez de SQLite? [s/N]: ").strip().lower()
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

def _env_value(value) -> str:
    """Quotes a value for .env (double quotes, escaped backslashes/quotes/newlines)."""
    text = str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n")
    return f'"{text}"'


def _write_env_file(env_path: Path, project_info: dict) -> None:
    import secrets
    secret_key = secrets.token_hex(32)
    db_type = project_info.get("DB_TYPE", "sqlite")

    db_extra = ""
    if db_type != "sqlite":
        db_extra = f"""DB_HOST={_env_value(project_info.get('DB_HOST', '127.0.0.1'))}
DB_PORT={project_info.get('DB_PORT', 3306)}
DB_USER={_env_value(project_info.get('DB_USER', 'root'))}
DB_PASSWORD={_env_value(project_info.get('DB_PASSWORD', ''))}
"""

    env_content = f"""# ─── Server Configuration ────────────────────────────────
SECRET_KEY={_env_value(secret_key)}
DEBUG=True
PORT={project_info.get("PORT", "8000")}
HOST="127.0.0.1"
WORKERS="1"

# ─── Application URL ────────────────────────────────────
APP_URL=""

# ─── Project Metadata ───────────────────────────────────
TITLE_PROJECT={_env_value(project_info["TITLE_PROJECT"])}
VERSION_PROJECT="2.0.0"
DESCRIPTION_PROJECT={_env_value(project_info["DESCRIPTION_PROJECT"])}
LANG_DEFAULT={_env_value(project_info["LANG_DEFAULT"])}

# ─── SEO Defaults ───────────────────────────────────────
DESCRIPTION_DEFAULT={_env_value(project_info["DESCRIPTION_DEFAULT"])}
KEYWORDS_DEFAULT={_env_value(project_info["KEYWORDS_DEFAULT"])}
AUTHOR_DEFAULT={_env_value(project_info["AUTHOR_DEFAULT"])}

# ─── Cache Driver (memory | redis | file) ───────────────
# memory = default for 1-2 workers; redis = shared/multi-worker; file = fallback
CACHE_DRIVER="memory"
CACHE_DIR="app/cache/data"
REDIS_HOST="127.0.0.1"
REDIS_PORT=6379
REDIS_PASSWORD=""
REDIS_URL=""

# ─── Database Configuration ──────────────────────────────
DB_TYPE={_env_value(db_type)}
DB_NAME={_env_value(project_info.get('DB_NAME', 'lila'))}
{db_extra}
# ─── AI Integration (core/ia.py) ─────────────────────────
OPENAI_API_KEY=""
DEEPSEEK_API_KEY=""
GEMINI_API_KEY=""

# ─── Mailer (password reset, optional) ───────────────────
SMTP_HOST=""
SMTP_PORT=587
SMTP_USER=""
SMTP_PASSWORD=""
SMTP_FROM=""
SMTP_TLS=True
SMTP_SSL=False

# ─── OAuth 2.0 Providers ─────────────────────────
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GITHUB_CLIENT_ID=""
GITHUB_CLIENT_SECRET=""
DISCORD_CLIENT_ID=""
DISCORD_CLIENT_SECRET=""
"""
    env_path.write_text(env_content.lstrip(), encoding="utf-8")

def main(template: str = "web", yes: bool = False, install: bool = False):
    global _ASSUME_DEFAULTS
    _ASSUME_DEFAULTS = bool(yes)
    destination_base_path = Path(os.getcwd())
    project_dir_name = os.path.basename(destination_base_path)
    template = (template or "web").lower()
    if template not in TEMPLATES:
        print(f"❌ Unknown template '{template}'. Available: " + ", ".join(f"{k} ({v})" for k, v in TEMPLATES.items()))
        return

    if list(destination_base_path.glob('*')):
        print(
            "⚠️ Advertencia: El directorio actual no está vacío. Los archivos del proyecto Lila se copiarán aquí. / "
            "Warning: The current directory is not empty. Lila project files will be copied here."
        )
        if not yes:
            input("Presiona Enter para continuar o Ctrl+C para cancelar... / Press Enter to continue...")

    try:
        project_info = _collect_project_info(project_dir_name)

        print("\n🛠️  Scaffolding project with Lila Framework v2.0...")

        for item_pkg_name, item_dest_name in SCAFFOLD_ITEMS.items():
            copy_item("lila", item_pkg_name, destination_base_path, item_dest_name)

        env_path = destination_base_path / ".env"
        if env_path.exists():
            print("  ℹ️ .env already exists; preserved (delete it to regenerate).")
        else:
            _write_env_file(env_path, project_info)
            print("  ✨ .env generated successfully.")

        req_path = destination_base_path / "requirements.txt"
        if not req_path.exists():
            req_path.write_text("lila-framework>=2.0.0\n", encoding="utf-8")
            print("  📄 requirements.txt generated.")

        readme_content = f"""# {project_info["TITLE_PROJECT"]}

{project_info["DESCRIPTION_PROJECT"]}

Built with **Lila Framework v2.0** — Full-Stack Python SPA, SQLite WAL mode, and Desktop ready.

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
        readme_path = destination_base_path / "README.md"
        if not readme_path.exists():
            readme_path.write_text(readme_content, encoding="utf-8")
            print("  📄 README.md created.")
        else:
            print("  ℹ️ README.md already exists; preserved.")

        if template != "web":
            print(f"\n🧩 Template '{template}': {TEMPLATES[template]}")
            apply_template(template, install=install)

        print("\n🎉 ¡Proyecto Lila v2.0 inicializado con éxito! / Lila v2.0 project scaffolded successfully!")
        if template in ("react", "react-auth", "full", "desktop"):
            print("➡️  Ejecuta 'lila react dev' (Vite + Lila con HMR) / Run 'lila react dev'.")
        else:
            print("➡️  Ejecuta 'lila dev' para arrancar el servidor con hot-reload.")

    except Exception as e:
        print(f"\n❌ Error during project creation: {e}")

if __name__ == "__main__":
    main()

