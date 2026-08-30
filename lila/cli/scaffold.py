import sys
import os
import socket
import shutil
from importlib import resources
from pathlib import Path

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

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


def copy_item(source_package_name, item_name_in_package, destination_base_path, item_name_in_dest):
    def _do_copy(src_path: Path):
        dest_path = Path(destination_base_path) / item_name_in_dest
        
        if src_path.resolve() == dest_path.resolve():
            print(f"  ℹ️ Skipping '{item_name_in_package}' (source and destination are identical).")
            return

        if src_path.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            print(f"  📂 Directory '{item_name_in_package}' copied to '{dest_path}'.")
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            print(f"  📄 File '{item_name_in_package}' copied to '{dest_path}'.")

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
        print(f"  ❌ Error copying '{item_name_in_package}': {e}.")


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Test if a port is bound on the host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _prompt(label: str, default: str) -> str:
    """Prompts the user for input with a default fallback."""
    value = input(f"  {label} [{default}]: ").strip()
    return value if value else default


def _to_docker_name(name: str) -> str:
    """Sanitizes a project name for Docker container/network naming."""
    import re
    name = name.strip().lower()
    name = re.sub(r'[\s\-]+', '_', name)
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name or "lila_project"


def _collect_project_info(project_dir_name: str) -> dict:
    """Interactively collects project metadata and database configuration."""
    default_title = project_dir_name.replace("_", " ").replace("-", " ").title()
    default_docker_name = _to_docker_name(project_dir_name)

    print("\n📝 Project Configuration")
    print("   (Press Enter to accept default values)\n")

    project_name_raw = _prompt("Project name (used for Docker containers)", project_dir_name)
    docker_name = _to_docker_name(project_name_raw)

    suggested_port = "8000"
    if _is_port_in_use(8000):
        print("  ⚠️ Port 8000 is currently in use on the host.")
        for p in range(8001, 8020):
            if not _is_port_in_use(p):
                suggested_port = str(p)
                break

    app_port = _prompt("HTTP port for Docker/VPS", suggested_port)

    info = {
        "LILA_PROJECT_NAME": docker_name,
        "PORT": app_port,
        "TITLE_PROJECT": _prompt("Project title", default_title),
        "DESCRIPTION_PROJECT": _prompt("Description", ""),
        "AUTHOR_DEFAULT": _prompt("Author", ""),
        "LANG_DEFAULT": _prompt("Default language (en/es/...)", "en"),
        "DESCRIPTION_DEFAULT": _prompt("SEO meta description", "A high-performance Python web framework"),
        "KEYWORDS_DEFAULT": _prompt("SEO keywords", "Python, web, framework, asgi, api"),
        "DB_TYPE": "sqlite",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "3306",
        "DB_NAME": docker_name,
        "DB_USER": "root",
        "DB_PASSWORD": "root",
        "REDIS_PORT_HOST": "6379",
    }

    print("\n🗄️ Database Setup")
    setup_mysql = input("  Configure MySQL now? [y/N]: ").strip().lower()
    if setup_mysql in ("y", "yes"):
        suggested_db_port = "3306"
        if _is_port_in_use(3306):
            print("  ⚠️ MySQL port 3306 is in use.")
            for p in range(3307, 3320):
                if not _is_port_in_use(p):
                    suggested_db_port = str(p)
                    break

        info["DB_TYPE"] = "mysql"
        info["DB_HOST"] = _prompt("MySQL host", "127.0.0.1")
        info["DB_PORT"] = _prompt("MySQL port (host)", suggested_db_port)
        info["DB_NAME"] = _prompt("Database name", docker_name)
        info["DB_USER"] = _prompt("MySQL user", "root")
        info["DB_PASSWORD"] = _prompt("MySQL password", "root")
        print("  ✅ MySQL configured with low-memory VPS profile (~70MB RAM).")
    else:
        print("  ℹ️ Using SQLite by default (app/connections.py).")

    return info


def _write_env_file(env_path: Path, project_info: dict) -> None:
    """Writes the .env file with project metadata and Docker variables."""
    import secrets
    secret_key = secrets.token_hex(32)
    env_content = f"""# ─── Server ────────────────────────────────────────────────
SECRET_KEY='{secret_key}'
DEBUG=True
PORT={project_info.get("PORT", "8000")}
HOST="127.0.0.1"
JIT=False
WORKERS=2

# ─── Redis ─────────────────────────────────────────────────
REDIS_HOST="127.0.0.1"
REDIS_PORT=6379
REDIS_PORT_HOST={project_info.get("REDIS_PORT_HOST", "6379")}

# ─── Application URL ─────────────────────────────────────────
APP_URL=""

# ─── Project Metadata ─────────────────────────────────────────
TITLE_PROJECT='{project_info["TITLE_PROJECT"]}'
VERSION_PROJECT='1.0.0'
DESCRIPTION_PROJECT='{project_info["DESCRIPTION_PROJECT"]}'
LANG_DEFAULT='{project_info["LANG_DEFAULT"]}'

# ─── SEO Defaults ───────────────────────────────────────────────
DESCRIPTION_DEFAULT="{project_info["DESCRIPTION_DEFAULT"]}"
KEYWORDS_DEFAULT="{project_info["KEYWORDS_DEFAULT"]}"
AUTHOR_DEFAULT="{project_info["AUTHOR_DEFAULT"]}"

# ─── Docker / VPS Multi-Project Configuration ─────────────────
LILA_PROJECT_NAME={project_info["LILA_PROJECT_NAME"]}
DB_NAME={project_info["DB_NAME"]}
DB_USER={project_info["DB_USER"]}
DB_PASSWORD={project_info["DB_PASSWORD"]}
DB_PORT={project_info["DB_PORT"]}
"""
    env_path.write_text(env_content.lstrip(), encoding="utf-8")


def _write_connections_file(connections_path: Path, project_info: dict) -> None:
    """Writes app/connections.py with the database configuration."""
    if project_info["DB_TYPE"] == "mysql":
        connections_content = f"""from lila.core.database import Database
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()

# MySQL async connection (tuned for low-memory VPS)
config = {{
    "type": "mysql",
    "host": os.getenv("DB_HOST", "{project_info['DB_HOST']}"),
    "port": int(os.getenv("DB_PORT", "{project_info['DB_PORT']}")),
    "user": os.getenv("DB_USER", "{project_info['DB_USER']}"),
    "password": os.getenv("DB_PASSWORD", "{project_info['DB_PASSWORD']}"),
    "database": os.getenv("DB_NAME", "{project_info['DB_NAME']}"),
    "is_async": True,
    "auto_commit": False,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_recycle": 1800,
    "pool_timeout": 30,
}}
connection = Database(config=config)
connection.connect()
"""
    else:
        connections_content = """from lila.core.database import Database
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

load_dotenv()

# SQLite connection (default for local development)
config = {"type": "sqlite", "database": "lila", "is_async": True}
connection = Database(config=config)
connection.connect()
"""
    connections_path.write_text(connections_content.lstrip(), encoding="utf-8")


def main():
    destination_base_path = Path(os.getcwd())
    project_dir_name = os.path.basename(destination_base_path)

    if list(destination_base_path.glob('*')):
        print("⚠️ Warning: The current directory is not empty. Lila project files will be copied here.")
        input("Press Enter to continue or Ctrl+C to cancel...")

    try:
        project_info = _collect_project_info(project_dir_name)

        print(f"\n🛠️ Scaffolding project in the current directory using Lila Framework...")

        for item_pkg_name, item_dest_name in SCAFFOLD_ITEMS.items():
            copy_item("lila", item_pkg_name, destination_base_path, item_dest_name)

        env_path = destination_base_path / ".env"
        _write_env_file(env_path, project_info)
        print("  ✨ .env generated with project configuration.")

        connections_path = destination_base_path / "app" / "connections.py"
        if connections_path.exists():
            _write_connections_file(connections_path, project_info)
            print("  🔗 app/connections.py updated with database configuration.")

        req_path = destination_base_path / "requirements.txt"
        if not req_path.exists():
            req_path.write_text("lila-framework\n", encoding="utf-8")
            print("  📄 requirements.txt generated.")

        readme_content = f"""# {project_info["TITLE_PROJECT"]}

{project_info["DESCRIPTION_PROJECT"]}

## Documentation
https://seip25.github.io/Lila
"""
        with open(destination_base_path / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("  📄 README.md created.")

        print("\n🎉 Lila project initialized successfully!")
        print("➡️ Review the generated files and start your application with: python main.py or lila-docker start prod")

    except Exception as e:
        print(f"\n❌ Error during project creation: {e}")


if __name__ == "__main__":
    main()
