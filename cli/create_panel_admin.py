import typer
import os
import subprocess
from app.connections import connection
from argon2 import PasswordHasher
from app.helpers.helpers import generate_token_value

app = typer.Typer()
ph = PasswordHasher()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def ensure_connection_or_migrate():
    try:
        connection.engine.connect()
        result = subprocess.run(["python", "-m", "cli.migrations"])
        return True
    except Exception:
        typer.echo("Database connection failed. Running migrations...")
        result = subprocess.run(["python", "-m", "cli.migrations"])
        return result.returncode == 0

def check_and_create_table():
    db_type = connection.engine.url.drivername
    if db_type == "sqlite":
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='admins'"
    elif db_type in {"postgresql", "mysql", "mysql+mysqlconnector"}:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'admins'
        ) AS table_exists
        """
    else:
        typer.echo("Unsupported database type.")
        raise typer.Exit(code=1)

    table_exists = connection.query(query=query, return_row=True)
    if db_type == "sqlite":
        table_exists = bool(table_exists)
    else:
        table_exists = table_exists.get("table_exists", False)

    if not table_exists:
        if db_type == "sqlite":
            column_definition = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        elif db_type.startswith("mysql"):
            column_definition = "id INTEGER PRIMARY KEY AUTO_INCREMENT"
        elif db_type == "postgresql":
            column_definition = "id SERIAL PRIMARY KEY"
        else:
            typer.echo("Unsupported database type.")
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
from app.routes.admin import Admin
from app.models.user import User
admin_routes = Admin(models=[User])
all_routes = list(itertools.chain(routes, api_routes, admin_routes))
    """

    if not os.path.exists(main_file):
        typer.echo("main.py not found.")
        raise typer.Exit(code=1)

    with open(main_file, "r", encoding="utf-8") as file:
        content = file.read()

    if marker not in content:
        typer.echo(f"Marker '{marker}' not found in main.py.")
        raise typer.Exit(code=1)

    if replace_text.strip() in content:
        typer.echo("Admin routes already added.")
        return

    new_content = content.replace(marker, f"{marker}\n{replace_text}")

    with open(main_file, "w", encoding="utf-8") as file:
        file.write(new_content)

    typer.echo("Admin routes added to main.py.")

@app.command(name="create_panel_admin")
def create_admin(username: str = "admin", password: str = None):
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
