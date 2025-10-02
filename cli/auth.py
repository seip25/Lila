import typer
from pathlib import Path
import os
import subprocess
from app.connections import connection

app = typer.Typer()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

login_template_content = read_file("cli/auth/templates/login.html")
register_template_content = read_file("cli/auth/templates/register.html")
forgot_password_template_content = read_file("cli/auth/templates/forgot-password.html")
change_password_template_content = read_file("cli/auth/templates/change-password.html")
invalid_token_template_content = read_file("cli/auth/templates/invalid-token.html")
authenticated_template_content = read_file("cli/auth/templates/dashboard.html")
profile_template_content = read_file("cli/auth/templates/profile.html")

auth_file_content = read_file("cli/auth/routes/auth.py")
dashboard_file_content = read_file("cli/auth/routes/dashboard.py")

user_model_content = read_file("cli/auth/models/user.py")
auth_model_content = read_file("cli/auth/models/auth.py")

def _create_templates():
    templates_dir = Path("templates/html/auth")
    templates_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "login.html": login_template_content,
        "register.html": register_template_content,
        "forgot-password.html": forgot_password_template_content,
        "change-password.html": change_password_template_content,
        "invalid-token.html": invalid_token_template_content
    }

    for filename, content in templates.items():
        file_path = templates_dir / filename
        file_path.write_text(content, encoding="utf-8")
        print(f" Template created: {file_path}")

    print("\n Auth templates generated successfully")

    template_dashboard_dir = Path("templates/html/dashboard")
    template_dashboard_dir.mkdir(parents=True, exist_ok=True)
    templates_dashboard = {
        "dashboard.html": authenticated_template_content,
        "profile.html": profile_template_content
    }
    for filename, content in templates_dashboard.items():
        file_path = template_dashboard_dir / filename
        file_path.write_text(content, encoding="utf-8")
        print(f" Template created: {file_path}")
    print("\n Dashboards templates generated successfully")

def _create_routes():
    main_file = os.path.join(project_root, "main.py")
    marker = "auth_marker"

    if not os.path.exists(main_file):
        typer.echo("main.py not found.")
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if "from app.routes.auth import auth_routes" in content:
        typer.echo("Auth routes already added.")

    typer.echo("Auth routes already addedd")

    replace_text = f'''# {marker}
from app.routes.auth import auth_routes
from app.routes.authenticated import authenticated_routes
import itertools
all_routes = list(itertools.chain(routes, api_routes, auth_routes,authenticated_routes))'''

    new_content = content.replace(f"# {marker}", replace_text)

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("Auth routes added to main.py.")

def _create_dashboard_file():
    auth_file_path = os.path.join(project_root, "app/routes/dashboard.py")
    with open(auth_file_path, "w", encoding="utf-8") as file:
        file.write(dashboard_file_content)
    typer.echo("Dashboard file created/updated successfully.")

def _create_auth_file():
    auth_file_path = os.path.join(project_root, "app/routes/auth.py")
    with open(auth_file_path, "w", encoding="utf-8") as file:
        file.write(auth_file_content)
    typer.echo("Auth file created/updated successfully.")

def _overwrite_user_model():
    user_model_path = os.path.join(project_root, "app/models/user.py")
    with open(user_model_path, "w", encoding="utf-8") as file:
        file.write(user_model_content)
    typer.echo("User model overwritten successfully.")

def _create_auth_model():
    model_path = os.path.join(project_root, "app/models/auth.py")
    with open(model_path, "w", encoding="utf-8") as file:
        file.write(auth_model_content)
    marker = "# auth_marker"
    main_file = os.path.join(project_root, "cli/migrations.py")
    code_import = """from app.models.auth import LoginAttempt ,LoginAttemptHistory,LoginSuccessHistory"""
    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()
    if code_import not in content:
        content = content.replace(marker, f"{code_import}\n{marker}")
        with open(main_file, "w", encoding="utf-8") as file:
            file.write(content)
    if marker not in content:
        typer.echo(f"Marker '{marker}' not found in migrations.py. Please add it to enable automatic migrations for LoginAttempt model.")
        return
    result = subprocess.run(["python", "-m", "cli.migrations", "--refresh"], cwd=project_root)
    if result.returncode != 0:
        typer.echo("Failed to run migrations. Please check the error messages above.")
        return

    typer.echo("LoginAttempt model created successfully.")

@app.command()
def main(template: str = "True", route: str = "True"):
    if connection is None:
        subprocess.run(["python", "-m", "cli.migrations"], cwd=project_root)
        typer.echo("Database connection established and migrations run.")

    if template.lower() == "true":
        _create_templates()

    if route.lower() == "true":
        _create_routes()
        _create_auth_file()
        _create_dashboard_file()
        _overwrite_user_model()
        _create_auth_model()

if __name__ == "__main__":
    app()