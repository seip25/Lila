import sys
import os
import re
import secrets
from pathlib import Path
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Generate and rotate application SECRET_KEY in .env.")

@app.command()
def create():
    """Generate a cryptographic SECRET_KEY and update .env"""
    new_key = secrets.token_hex(32)
    env_file = Path(".env")
    if not env_file.exists():
        typer.secho("❌ .env file not found in current directory.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    content = env_file.read_text(encoding="utf-8")
    content, count = re.subn(r"(SECRET_KEY\s*=\s*['\"])(.*?)(['\"])", rf"\g<1>{new_key}\g<3>", content)
    if count == 0:
        content, count = re.subn(r"(SECRET_KEY\s*=\s*)([^\s'\"#]+)", rf"\g<1>'{new_key}'", content)
    if count == 0:
        content = f"SECRET_KEY='{new_key}'\n" + content

    env_file.write_text(content, encoding="utf-8")
    typer.secho(f"🔑 Generated new SECRET_KEY='{new_key}'", fg=typer.colors.GREEN)

def main():
    app()

if __name__ == "__main__":
    main()
