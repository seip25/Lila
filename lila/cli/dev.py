import os
import sys
import subprocess
import typer
from lila.core.config import ConfigLoader, ENV_CONFIG

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

    ConfigLoader.load()
    bind_host = host or ENV_CONFIG.get("HOST", "127.0.0.1")
    try:
        bind_port = int(port or ENV_CONFIG.get("PORT", 8000) or 8000)
    except (TypeError, ValueError):
        bind_port = 8000

    typer.secho(f"🚀 Starting Lila v2.0 development server at http://{bind_host}:{bind_port} ...", fg=typer.colors.CYAN)
    
    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", str(bind_host),
        "--port", str(bind_port)
    ]
    child_env = os.environ.copy()
    # ``lila dev`` is a development command even if the project .env says
    # DEBUG=False. This enables Jinja auto_reload + the dev SSE watcher.
    child_env["DEBUG"] = "True"
    child_env["LILA_DEV"] = "1"
    child_env["LILA_DEV_RELOAD"] = "1" if reload else "0"
    if reload:
        # Python files are watched by uvicorn. Jinja/HTML/static edits are
        # detected by the Lila SSE watcher, which works without watchfiles.
        cmd.extend([
            "--reload",
            "--reload-dir", ".",
        ])

    try:
        subprocess.run(cmd, env=child_env)
    except KeyboardInterrupt:
        typer.echo("\n🛑 Lila server stopped.")
    except Exception as e:
        typer.secho(f"❌ Error starting server: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

def main():
    app()

if __name__ == "__main__":
    main()
