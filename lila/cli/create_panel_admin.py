import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer
import os
import subprocess
try:
    from app.connections import connection
except ImportError:
    connection = None
from argon2 import PasswordHasher
from lila.core.auth import generate_token_value

app = typer.Typer()
ph = PasswordHasher()

project_root = os.getcwd()

def ensure_connection_or_migrate():
    try:
        if hasattr(connection, "check_connection"):
            connected = connection.check_connection()
        else:
            connected = False
            try:
                with connection.engine.connect() as conn:
                    connected = True
            except Exception:
                pass
        
        if not connected:
            raise Exception("Connection failed")

        result = subprocess.run([sys.executable, "-m", "lila.cli.migrations"])
        return True
    except Exception:
        typer.echo("Database connection failed. Running migrations...")
        result = subprocess.run([sys.executable, "-m", "lila.cli.migrations"])
        return result.returncode == 0

def check_and_create_table():
    db_type = connection.engine.url.drivername
    is_sqlite = "sqlite" in db_type
    is_mysql = "mysql" in db_type
    is_postgres = "postgresql" in db_type or "postgres" in db_type or "asyncpg" in db_type

    if is_sqlite:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='admins'"
    elif is_mysql or is_postgres:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'admins'
        ) AS table_exists
        """
    else:
        typer.echo(f"Unsupported database type: {db_type}")
        raise typer.Exit(code=1)

    table_exists = connection.query(query=query, return_row=True)
    if is_sqlite:
        table_exists = bool(table_exists)
    else:
        table_exists = table_exists.get("table_exists", False) if table_exists else False

    if not table_exists:
        if is_sqlite:
            column_definition = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        elif is_mysql:
            column_definition = "id INTEGER PRIMARY KEY AUTO_INCREMENT"
        elif is_postgres:
            column_definition = "id SERIAL PRIMARY KEY"
        else:
            typer.echo(f"Unsupported database type: {db_type}")
            raise typer.Exit(code=1)

        create_table_query = f"""
        CREATE TABLE admins (
            {column_definition},
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(150) NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        return connection.query(query=create_table_query)
    return True

def create_admin_user(username: str, password: str) -> bool:
    hashed_password = ph.hash(password)
    query = "INSERT INTO admins (username, password, active) VALUES (:username, :password, 1)"
    params = {"username": username, "password": hashed_password}
    return connection.query(query=query, params=params)

def update_main_routes():
    main_file = os.path.join(project_root, "main.py")
    marker = "admin_marker"
    replace_text = """
from app.routes.admin.index import Admin
from app.models.user import User
admin_routes = Admin(models=[User])
all_routes = list(itertools.chain(all_routes, admin_routes))
"""

    if not os.path.exists(main_file):
        typer.echo("main.py not found.")
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if marker not in content:
        typer.echo(f"Marker '{marker}' not found in main.py.")
        raise typer.Exit(code=1)

    if "admin_routes = Admin" in content:
        typer.echo("Admin routes already added.")
        return

    new_content = content.replace(marker, f"{marker}{replace_text}")

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("Admin routes added to main.py.")

@app.command(name="create_panel_admin")
def create_admin(username: str = "admin", password: str = None):
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.echo("❌ Error: This command must be run inside a Lila project root directory.")
        raise typer.Exit(code=1)

    if not ensure_connection_or_migrate():
        typer.echo("Failed to initialize the database.")
        raise typer.Exit(code=1)

    if not check_and_create_table():
        typer.echo("Failed to verify or create 'admins' table.")
        raise typer.Exit(code=1)

    if not password:
        password = generate_token_value(2)

    if create_admin_user(username, password):
        typer.echo(f"Admin user '{username}' created with password '{password}'.")
        update_main_routes()
        typer.echo("Create admin command executed successfully.")
    else:
        typer.echo(f"Failed to create admin user '{username}'.")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
