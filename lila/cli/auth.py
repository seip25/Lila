import sys
import os
from pathlib import Path
import subprocess
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Generate complete Auth 2.0 system (login, register, forgot-password, dashboard, OAuth).")

package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
user_project_root = os.getcwd()

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
        file_path.write_text(content, encoding="utf-8")
        typer.echo(f"  📄 Template created: {file_path}")

    template_dashboard_dir = Path("resources/html/authenticated")
    template_dashboard_dir.mkdir(parents=True, exist_ok=True)
    templates_dashboard = {
        "dashboard.jinja": read_file("cli/auth/templates/dashboard.jinja"),
        "profile.jinja":   read_file("cli/auth/templates/profile.jinja"),
    }
    for filename, content in templates_dashboard.items():
        file_path = template_dashboard_dir / filename
        file_path.write_text(content, encoding="utf-8")
        typer.echo(f"  📄 Template created: {file_path}")

def _create_routes():
    main_file = os.path.join(user_project_root, "main.py")
    marker = "auth_marker"

    if not os.path.exists(main_file):
        typer.secho("❌ main.py not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if "from app.routes.web.auth import routes as auth_routes" in content:
        typer.echo("ℹ️ Auth routes already present in main.py.")
        return

    replace_text = f'''# {marker}
from app.routes.web.auth import routes as auth_routes
from app.routes.web.authenticated import routes as authenticated_routes
app.include_router(auth_routes)
app.include_router(authenticated_routes)'''

    if f"# {marker}" in content:
        new_content = content.replace(f"# {marker}", replace_text)
    else:
        new_content = content + f"\n\n{replace_text}\n"

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("  ✨ Auth routes linked in main.py.")

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
        (auth_dir / filename).write_text(content, encoding="utf-8")

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
        (auth_dir / filename).write_text(content, encoding="utf-8")

    typer.echo("  📁 Route files created in app/routes/web/authenticated/")

def _overwrite_user_model():
    user_model_path = os.path.join(user_project_root, "app/models/user.py")
    content = read_file("cli/auth/models/user.py")
    with open(user_model_path, "w", encoding="utf-8") as file:
        file.write(content)
    typer.echo("  👤 User model updated with OAuth and Argon2/PasswordHasher.")

def _create_auth_model():
    model_path = os.path.join(user_project_root, "app/models/auth.py")
    content = read_file("cli/auth/models/auth.py")
    with open(model_path, "w", encoding="utf-8") as file:
        file.write(content)

    subprocess.run([sys.executable, "-m", "lila.cli.migrations", "--refresh"], cwd=user_project_root)
    typer.echo("  🔐 LoginAttempt & PasswordResetToken models registered.")

@app.command()
def generate(
    template: bool = typer.Option(True, "--templates/--no-templates", help="Generate Jinja2 auth templates"),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Generate auth and dashboard routes"),
):
    """
    Scaffold authentication system with Better Auth OAuth, Argon2, and dashboard.
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
