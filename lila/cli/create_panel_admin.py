import sys
import os
import secrets
import subprocess
from typing import Optional, List, Dict, Any
import typer
from sqlalchemy import text

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.core.auth import PasswordHasher

app = typer.Typer(help="Setup Admin 2.0 and create administrator credentials.")

def get_connection():
    try:
        from app.connections import connection
        return connection
    except Exception:
        return None

def check_and_create_admins_table(conn) -> bool:
    is_sqlite = "sqlite" in conn.config.get("type", "sqlite")
    is_postgres = "postgres" in conn.config.get("type", "")

    if is_sqlite:
        check_q = "SELECT name FROM sqlite_master WHERE type='table' AND name='admins'"
    else:
        check_q = "SELECT table_name FROM information_schema.tables WHERE table_name = 'admins'"

    try:
        row = conn.query(query=check_q, return_row=True)
        if not row:
            if is_sqlite:
                pk_def = "id INTEGER PRIMARY KEY AUTOINCREMENT"
            elif is_postgres:
                pk_def = "id SERIAL PRIMARY KEY"
            else:
                pk_def = "id INTEGER PRIMARY KEY AUTO_INCREMENT"

            create_q = f"""
            CREATE TABLE admins (
                {pk_def},
                username VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            conn.query(query=create_q)
        return True
    except Exception as e:
        typer.echo(f"  ⚠️ Table check notice: {e}")
        return False

def create_admin_user(conn, username: str, password: str) -> bool:
    hashed_password = PasswordHasher.hash(password)
    query = "INSERT INTO admins (username, password, active) VALUES (:username, :password, 1)"
    params = {"username": username, "password": hashed_password}
    try:
        conn.query(query=query, params=params)
        return True
    except Exception as e:
        typer.secho(f"  ❌ Error creating admin user: {e}", fg=typer.colors.RED)
        return False

def copy_admin_files():
    import shutil
    dest_routes = os.path.join(os.getcwd(), "app", "routes", "admin")
    if not os.path.exists(dest_routes):
        os.makedirs(dest_routes, exist_ok=True)
        src_routes = os.path.join(os.path.dirname(__file__), "..", "app", "routes", "admin")
        if os.path.exists(src_routes):
            shutil.copytree(src_routes, dest_routes, dirs_exist_ok=True)
            typer.echo("  📁 Admin routes copied to app/routes/admin/")

    dest_templates = os.path.join(os.getcwd(), "resources", "html", "admin")
    if not os.path.exists(dest_templates):
        os.makedirs(dest_templates, exist_ok=True)
        src_templates = os.path.join(os.path.dirname(__file__), "..", "resources", "html", "admin")
        if os.path.exists(src_templates):
            shutil.copytree(src_templates, dest_templates, dirs_exist_ok=True)
            typer.echo("  📄 Admin templates copied to resources/html/admin/")


def update_main_routes():
    import re
    main_file = "main.py"
    marker = "admin_marker"
    if not os.path.exists(main_file):
        return

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    import_line = "from app.routes.admin.index import router as admin_router"
    include_line = "app.include_router(admin_router)"

    if import_line in content:
        return

    if f"# {marker}" in content:
        content = content.replace(f"# {marker}", f"# {marker}\n{import_line}")
    else:
        content = f"{import_line}\n" + content

    if include_line not in content and "admin_router" not in content.split("App(")[-1].split(")")[0]:
        app_match = re.search(r"(app\s*=\s*App\s*\([^)]*\))", content, re.DOTALL)
        if app_match:
            end_pos = app_match.end()
            content = content[:end_pos] + f"\n{include_line}\n" + content[end_pos:]
        else:
            content += f"\n{include_line}\n"

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(content)
    typer.echo("  ✨ Admin routes linked in main.py.")


@app.callback(invoke_without_command=True)
def default_admin(
    ctx: typer.Context,
    username: str = typer.Option("admin", "--user", "-u", help="Admin username"),
    password: str = typer.Option(None, "--password", "-p", help="Admin password (generated if omitted)"),
):
    """Setup Admin Panel 2.0 tables and create a superuser."""
    if ctx.invoked_subcommand is None:
        create(username=username, password=password)


@app.command("create")
@app.command("setup")
def create(
    username: str = typer.Option("admin", "--user", "-u", help="Admin username"),
    password: str = typer.Option(None, "--password", "-p", help="Admin password (generated if omitted)"),
):
    """
    Setup Admin Panel 2.0 tables and create a superuser.
    """
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.secho("❌ Error: Must run inside a Lila project root directory.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    conn = get_connection()
    if conn is None:
        typer.secho("❌ Could not connect to database via app.connections.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo("🛠️  Setting up Admin 2.0 tables...")
    check_and_create_admins_table(conn)

    copy_admin_files()

    admin_pw = password or secrets.token_urlsafe(10)
    if create_admin_user(conn, username, admin_pw):
        typer.secho(f"✅ Administrator '{username}' created successfully!", fg=typer.colors.GREEN)
        typer.echo(f"   🔑 Password: {admin_pw}")
        typer.echo("   🌐 Login at: http://127.0.0.1:8000/admin")
        update_main_routes()
    else:
        typer.secho(f"❌ Failed to create admin user '{username}'.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()

