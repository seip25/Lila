import os
import sys
import subprocess
import typer
from lila.core.config import ENV_CONFIG

app = typer.Typer(help="Start Lila local development server with hot-reload.")

@app.command()
def start(
    host: str = typer.Option(None, "--host", "-h", help="Host address to bind"),
    port: int = typer.Option(None, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable auto-reload on code change"),
):
    """
    Start the Lila development server with hot-reload.
    """
    if not os.path.exists("main.py"):
        typer.secho("❌ Error: main.py not found in the current directory.", fg=typer.colors.RED)
        typer.echo("Make sure you are in the root directory of your Lila project.")
        raise typer.Exit(code=1)

    bind_host = host or ENV_CONFIG.get("HOST", "127.0.0.1")
    bind_port = port or int(ENV_CONFIG.get("PORT", 8000))

    typer.secho(f"🚀 Starting Lila v2.0 development server at http://{bind_host}:{bind_port} ...", fg=typer.colors.CYAN)
    
    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", str(bind_host),
        "--port", str(bind_port)
    ]
    if reload:
        cmd.extend([
            "--reload",
            "--reload-dir", ".",
            "--reload-include", "*.jinja",
            "--reload-include", "*.html",
            "--reload-include", "*.json",
        ])

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        typer.echo("\n🛑 Lila server stopped.")
    except Exception as e:
        typer.secho(f"❌ Error starting server: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

def main():
    app()

if __name__ == "__main__":
    main()
