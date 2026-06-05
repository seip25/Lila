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
    "uploads": "uploads",
    ".gitignore": ".gitignore",
    ".env": ".env",
    "AGENTS.md": "AGENTS.md",
    "vite.config.js": "vite.config.js",
    "package.json": "package.json",
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


def _collect_project_info(project_dir_name: str) -> dict:
    """
    English: Interactively collects project metadata from the user via terminal prompts.
    Español: Recolecta interactivamente los metadatos del proyecto del usuario via prompts de terminal.
    """
    default_title = project_dir_name.replace("_", " ").replace("-", " ").title()

    print("\n📝 Configuración del proyecto / Project configuration")
    print("   (Presiona Enter para usar el valor por defecto / Press Enter to use defaults)\n")

    return {
        "TITLE_PROJECT": _prompt("Project title", "Título del proyecto", default_title),
        "DESCRIPTION_PROJECT": _prompt("Description", "Descripción", ""),
        "AUTHOR_DEFAULT": _prompt("Author", "Autor", ""),
        "LANG_DEFAULT": _prompt("Default language (en/es/...)", "Idioma por defecto (en/es/...)", "en"),
        "DESCRIPTION_DEFAULT": _prompt("SEO meta description", "SEO meta descripción", "A Python web framework"),
        "KEYWORDS_DEFAULT": _prompt("SEO keywords", "SEO palabras clave", "Python, web, framework"),
    }


def _write_env_file(env_path: Path, project_info: dict) -> None:
    """
    English: Writes the .env file with the collected project metadata and framework defaults.
    Español: Escribe el archivo .env con los metadatos del proyecto recolectados y los defaults del framework.
    """
    import secrets
    secret_key = secrets.token_hex(32)
    env_content = f"""# ─── Server ────────────────────────────────────────────
SECRET_KEY='{secret_key}'
DEBUG=True
PORT=8000
HOST="127.0.0.1"
JIT=False
WORKERS="1"

# ─── Application URL ──────────────────────────────────
# English: Production URL for sitemaps, robots.txt, and canonical links.
#          Leave empty in development — the framework uses http://HOST:PORT automatically.
# Español: URL de producción para sitemaps, robots.txt y links canónicos.
#          Dejar vacío en desarrollo — el framework usa http://HOST:PORT automáticamente.
#          Example: APP_URL="https://my-lila-app.com"
APP_URL=""

# ─── Project Metadata ─────────────────────────────────
TITLE_PROJECT='{project_info["TITLE_PROJECT"]}'
VERSION_PROJECT='1'
DESCRIPTION_PROJECT='{project_info["DESCRIPTION_PROJECT"]}'
LANG_DEFAULT='{project_info["LANG_DEFAULT"]}'

# ─── SEO Defaults ─────────────────────────────────────
DESCRIPTION_DEFAULT="{project_info["DESCRIPTION_DEFAULT"]}"
KEYWORDS_DEFAULT="{project_info["KEYWORDS_DEFAULT"]}"
AUTHOR_DEFAULT="{project_info["AUTHOR_DEFAULT"]}"
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
