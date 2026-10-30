import sys
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.cli._patch import patch_main

app = typer.Typer(help="Generate complete Auth 2.0 system (login, register, forgot-password, dashboard, OAuth).")

package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
user_project_root = os.getcwd()


def _write_with_backup(path: Path, content: str) -> None:
    """Writes a generated file, backing up a differing existing file."""
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != content:
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        typer.secho(f"  ⚠️ Could not write {path}: {exc}", fg=typer.colors.YELLOW)

def read_file(rel_path: str) -> str:
    path = os.path.join(package_root, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _create_templates():
    templates_dir = Path("resources/html/auth")
    templates_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "login.jinja":           read_file("cli/auth/templates/login.jinja"),
        "register.jinja":        read_file("cli/auth/templates/register.jinja"),
        "forgot-password.jinja": read_file("cli/auth/templates/forgot-password.jinja"),
        "change-password.jinja": read_file("cli/auth/templates/change-password.jinja"),
        "invalid-token.jinja":   read_file("cli/auth/templates/invalid-token.jinja"),
    }

    for filename, content in templates.items():
        file_path = templates_dir / filename
        _write_with_backup(file_path, content)
        typer.echo(f"  📄 Template created: {file_path}")

    template_dashboard_dir = Path("resources/html/authenticated")
    template_dashboard_dir.mkdir(parents=True, exist_ok=True)
    templates_dashboard = {
        "dashboard.jinja": read_file("cli/auth/templates/dashboard.jinja"),
        "profile.jinja":   read_file("cli/auth/templates/profile.jinja"),
    }
    for filename, content in templates_dashboard.items():
        file_path = template_dashboard_dir / filename
        _write_with_backup(file_path, content)
        typer.echo(f"  📄 Template created: {file_path}")


def _create_routes():
    main_file = os.path.join(user_project_root, "main.py")

    if not os.path.exists(main_file):
        typer.secho("❌ main.py not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    import_stmt = (
        "from app.routes.web.auth import routes as auth_routes\n"
        "from app.routes.web.authenticated import routes as authenticated_routes"
    )
    include_stmt = "app.include_router(auth_routes)\napp.include_router(authenticated_routes)"

    if patch_main(main_file, import_stmt, include_stmt):
        typer.echo("  ✨ Auth routes linked in main.py.")
    else:
        typer.echo("ℹ️ Auth routes already present (or main.py could not be patched safely).")


def _create_auth_files():
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/auth"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":        read_file("cli/auth/routes/auth_init.py"),
        "login.py":           read_file("cli/auth/routes/login.py"),
        "register.py":        read_file("cli/auth/routes/register.py"),
        "logout.py":          read_file("cli/auth/routes/logout.py"),
        "forgot_password.py": read_file("cli/auth/routes/forgot_password.py"),
        "change_password.py": read_file("cli/auth/routes/change_password.py"),
    }
    for filename, content in files.items():
        _write_with_backup(auth_dir / filename, content)

    typer.echo("  📁 Route files created in app/routes/web/auth/")


def _create_authenticated_files():
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/authenticated"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":  read_file("cli/auth/routes/authenticated_init.py"),
        "dashboard.py": read_file("cli/auth/routes/dashboard.py"),
        "profile.py":   read_file("cli/auth/routes/profile.py"),
    }
    for filename, content in files.items():
        _write_with_backup(auth_dir / filename, content)

    typer.echo("  📁 Route files created in app/routes/web/authenticated/")


def _overwrite_user_model():
    user_model_path = Path(user_project_root) / "app/models/user.py"
    content = read_file("cli/auth/models/user.py")
    if user_model_path.exists() and user_model_path.read_text(encoding="utf-8") == content:
        typer.echo("  👤 User model already up to date.")
        return
    _write_with_backup(user_model_path, content)
    typer.echo("  👤 User model updated with OAuth and Argon2/PasswordHasher (previous file backed up).")


def _create_auth_model():
    model_path = Path(user_project_root) / "app/models/auth.py"
    content = read_file("cli/auth/models/auth.py")
    _write_with_backup(model_path, content)

    # Plain migrations: never --refresh (that would drop existing users).
    import subprocess

    result = subprocess.run([sys.executable, "-m", "lila.cli.migrations"], cwd=user_project_root)
    if result.returncode != 0:
        typer.secho(
            "  ⚠️ Migrations did not finish successfully; run 'lila migrate' manually.",
            fg=typer.colors.YELLOW,
        )
    typer.echo("  🔐 LoginAttempt & PasswordResetToken models registered.")

@app.callback(invoke_without_command=True)
def default_auth(
    ctx: typer.Context,
    template: bool = typer.Option(True, "--templates/--no-templates", help="Generate Jinja2 auth templates"),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Generate auth and dashboard routes"),
):
    """Scaffold authentication system with OAuth 2.0, Argon2, and dashboard."""
    if ctx.invoked_subcommand is None:
        generate(template=template, routes=routes)


@app.command()
def generate(
    template: bool = typer.Option(True, "--templates/--no-templates", help="Generate Jinja2 auth templates"),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Generate auth and dashboard routes"),
):
    """
    Scaffold authentication system with OAuth 2.0, Argon2, and dashboard.
    """
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.secho("❌ Error: Must run inside a Lila project root directory.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("🔐 Generating Lila Auth 2.0...", fg=typer.colors.CYAN)

    if template:
        _create_templates()

    if routes:
        _create_auth_files()
        _create_authenticated_files()
        _overwrite_user_model()
        _create_auth_model()
        _create_routes()

    typer.secho("✅ Auth 2.0 generated successfully! OAuth ready with Google, GitHub, and Discord.", fg=typer.colors.GREEN)

def main():
    app()

if __name__ == "__main__":
    app()

