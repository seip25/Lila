import typer
import os
import subprocess
from app.connections import connection
from argon2 import PasswordHasher
from app.helpers.helpers import generate_token_value

app = typer.Typer()
ph = PasswordHasher()


def create_admin_user(username: str, password: str) -> bool:
    hashed_password = ph.hash(password)
    query = "INSERT INTO admins (username, password, active) VALUES (:username, :password, 1)"
    params = {"username": username, "password": hashed_password}
    return connection.query(query=query, params=params)


@app.command(name="create_panel_admin")
def create_admin(username: str = "admin", password: str = None):
    
    if not password:
        password = generate_token_value(2)

    if create_admin_user(username, password):
        typer.echo(f"Admin user '{username}' created with password '{password}'.")
        typer.echo("Create admin command executed successfully.")
    else:
        typer.echo(f"Failed to create admin user '{username}'.")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
