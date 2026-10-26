import sys
import os
import secrets
import subprocess
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

def update_main_routes():
    main_file = "main.py"
    marker = "admin_marker"
    if not os.path.exists(main_file):
        return

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if "from app.routes.admin.index import router as admin_router" in content or "from app.routes.admin.index import Admin" in content:
        return

    replace_text = f'''# {marker}
from app.routes.admin.index import router as admin_router
app.include_router(admin_router)'''

    if f"# {marker}" in content:
        new_content = content.replace(f"# {marker}", replace_text)
        with open(main_file, "w", encoding="utf-8") as file:
            file.write(new_content)
        typer.echo("  ✨ Admin routes linked in main.py.")

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
