import typer
from core.helpers import generate_token_value
from database.connections import connection
from argon2 import PasswordHasher

ph = PasswordHasher()

app = typer.Typer()

@app.command(name="create_admin")
def create_admin(user: str = "admin", password: str = None):
    """
    Create user command.
    """
    success = check_and_create_table()
    if not password:
        password = generate_token_value(2)

    success = create_admin(user, password)
    if not success:
        typer.echo(f"Failed to create admin user '{user}'.")
        raise typer.Exit(code=1)
    typer.echo(f"Admin user '{user}' created with password '{password}'.")
    typer.echo("Admin command executed.")


def create_admin(username: str, password: str) -> bool:
    """Create a new admin user.

    Args:
        username (str): The username of the admin.
        password (str): The password of the admin.

    Returns:
        bool: True if the admin was created successfully, False otherwise.
    """
    hashed_password = ph.hash(password)
    query = "INSERT INTO admins (username, password, active) VALUES (:username, :password, 1)"
    params = {"username": username, "password": hashed_password}
    result = connection.query(query=query, params=params)
    return result


def check_and_create_table():
    """Check if the 'admins' table exists and create it if it doesn't."""
    db_type = connection.engine.url.drivername

    if db_type == "sqlite":
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='admins'"
    elif db_type in {"postgresql", "mysql", "mysql+mysqlconnector"}:
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'admins'
            )
            """
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    table_exists = connection.query(query=query, return_row=True)
    if db_type == "sqlite":
        table_exists = bool(table_exists)
    elif db_type in {"postgresql", "mysql", "mysql+mysqlconnector"}:
        table_exists = table_exists.get("table_exists", 0) == 1

    if not table_exists:
        if db_type == "sqlite":
            column_definition = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        elif db_type == "mysql" or "mysql+mysqlconnector":
            column_definition = "id INTEGER PRIMARY KEY AUTO_INCREMENT"
        elif db_type == "postgresql":
            column_definition = "id SERIAL PRIMARY KEY"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
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


if __name__ == "__main__":
    app()
