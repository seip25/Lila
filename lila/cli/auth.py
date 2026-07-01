import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer
from pathlib import Path
import os
import subprocess
try:
    from app.connections import connection
except ImportError:
    connection = None

app = typer.Typer()

package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
user_project_root = os.getcwd()

def read_file(path):
    path = os.path.join(package_root, path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ── HTML templates ────────────────────────────────────────────────────────────
login_template_content           = read_file("cli/auth/templates/login.jinja")
register_template_content        = read_file("cli/auth/templates/register.jinja")
forgot_password_template_content = read_file("cli/auth/templates/forgot-password.jinja")
change_password_template_content = read_file("cli/auth/templates/change-password.jinja")
invalid_token_template_content   = read_file("cli/auth/templates/invalid-token.jinja")
authenticated_template_content   = read_file("cli/auth/templates/dashboard.jinja")
profile_template_content         = read_file("cli/auth/templates/profile.jinja")

# ── Route file templates (auth/) ──────────────────────────────────────────────
login_route_content           = read_file("cli/auth/routes/login.py")
register_route_content        = read_file("cli/auth/routes/register.py")
logout_route_content          = read_file("cli/auth/routes/logout.py")
forgot_password_route_content = read_file("cli/auth/routes/forgot_password.py")
change_password_route_content = read_file("cli/auth/routes/change_password.py")
auth_init_content             = read_file("cli/auth/routes/auth_init.py")

# ── Route file templates (authenticated/) ────────────────────────────────────
dashboard_route_content         = read_file("cli/auth/routes/dashboard.py")
profile_route_content           = read_file("cli/auth/routes/profile.py")
authenticated_init_content      = read_file("cli/auth/routes/authenticated_init.py")

# ── Model templates ───────────────────────────────────────────────────────────
user_model_content = read_file("cli/auth/models/user.py")
auth_model_content = read_file("cli/auth/models/auth.py")


def _create_templates():
    templates_dir = Path("resources/html/auth")
    templates_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "login.jinja":           login_template_content,
        "register.jinja":        register_template_content,
        "forgot-password.jinja": forgot_password_template_content,
        "change-password.jinja": change_password_template_content,
        "invalid-token.jinja":   invalid_token_template_content,
    }

    for filename, content in templates.items():
        file_path = templates_dir / filename
        file_path.write_text(content, encoding="utf-8")
        print(f" Template created: {file_path}")

    print("\n Auth templates generated successfully")

    template_dashboard_dir = Path("resources/html/authenticated")
    template_dashboard_dir.mkdir(parents=True, exist_ok=True)
    templates_dashboard = {
        "dashboard.jinja": authenticated_template_content,
        "profile.jinja":   profile_template_content,
    }
    for filename, content in templates_dashboard.items():
        file_path = template_dashboard_dir / filename
        file_path.write_text(content, encoding="utf-8")
        print(f" Template created: {file_path}")
    print("\n Dashboards templates generated successfully")


def _create_routes():
    main_file = os.path.join(user_project_root, "main.py")
    marker = "auth_marker"

    if not os.path.exists(main_file):
        typer.echo("main.py not found.")
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if "from app.routes.web.auth import routes as auth_routes" in content:
        typer.echo("Auth routes already added.")
        return

    replace_text = f'''# {marker}
from app.routes.web.auth import routes as auth_routes
from app.routes.web.authenticated import routes as authenticated_routes
all_routes = list(itertools.chain(routes, api_routes, auth_routes, authenticated_routes))'''

    new_content = content.replace(f"# {marker}", replace_text)

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("Auth routes added to main.py.")


def _create_auth_files():
    """Write the 5 auth route files + __init__.py into app/routes/web/auth/"""
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/auth"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":        auth_init_content,
        "login.py":           login_route_content,
        "register.py":        register_route_content,
        "logout.py":          logout_route_content,
        "forgot_password.py": forgot_password_route_content,
        "change_password.py": change_password_route_content,
    }
    for filename, content in files.items():
        (auth_dir / filename).write_text(content, encoding="utf-8")

    typer.echo("Auth route files created in app/routes/web/auth/")


def _create_authenticated_files():
    """Write the 2 authenticated route files + __init__.py into app/routes/web/authenticated/"""
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/authenticated"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":  authenticated_init_content,
        "dashboard.py": dashboard_route_content,
        "profile.py":   profile_route_content,
    }
    for filename, content in files.items():
        (auth_dir / filename).write_text(content, encoding="utf-8")

    typer.echo("Authenticated route files created in app/routes/web/authenticated/")


def _overwrite_user_model():
    user_model_path = os.path.join(user_project_root, "app/models/user.py")
    with open(user_model_path, "w", encoding="utf-8") as file:
        file.write(user_model_content)
    typer.echo("User model overwritten successfully.")


def _create_auth_model():
    model_path = os.path.join(user_project_root, "app/models/auth.py")
    with open(model_path, "w", encoding="utf-8") as file:
        file.write(auth_model_content)

    result = subprocess.run([sys.executable, "-m", "lila.cli.migrations", "--refresh"], cwd=user_project_root)
    if result.returncode != 0:
        typer.echo("Failed to run migrations. Please check the error messages above.")
        return

    typer.echo("LoginAttempt model created successfully.")


@app.command()
def main(template: str = "True", route: str = "True"):
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.echo("❌ Error: This command must be run inside a Lila project root directory.")
        raise typer.Exit(code=1)

    if connection is None:
        subprocess.run([sys.executable, "-m", "lila.cli.migrations"], cwd=user_project_root)
        typer.echo("Database connection established and migrations run.")

    if template.lower() == "true":
        _create_templates()

    if route.lower() == "true":
        _create_routes()
        _create_auth_files()
        _create_authenticated_files()
        _overwrite_user_model()
        _create_auth_model()

if __name__ == "__main__":
    app()