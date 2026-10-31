import os
import sys
import typer
from lila.cli.scaffold import main as scaffold_main
from lila.cli.dev import start as dev_start
from lila.cli.desktop import app as desktop_app
from lila.cli.auth import app as auth_app
from lila.cli.create_panel_admin import app as admin_app
from lila.cli.migrations import app as migrations_app
from lila.cli.model import app as model_app
from lila.cli.scaffold_crud import app as crud_app
from lila.cli.optimize import main as optimize_main
from lila.cli.secret_key import app as secret_key_app
from lila.cli.seo import app as seo_app
from lila.cli.worker import app as worker_app
from lila.cli.deploy import app as deploy_app
from lila.cli.backup import app as backup_app

app = typer.Typer(
    name="lila",
    help="Lila Framework v2.0.0 CLI — Full-Stack Python with SPA View Transitions, AI Helper, and Desktop apps.",
    add_completion=False
)

# Attach subcommands
@app.command("init")
def init():
    """Scaffold a new Lila project in the current directory."""
    scaffold_main()

@app.command("dev")
def dev(
    host: str = typer.Option(None, "--host", "-h", help="Host address"),
    port: int = typer.Option(None, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Hot-reload"),
):
    """Run local development server with auto-reload."""
    dev_start(host=host, port=port, reload=reload)


@app.command("run")
def run(
    host: str = typer.Option(None, "--host", "-h", help="Bind address"),
    port: int = typer.Option(None, "--port", "-p", help="Port"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
    proxy_headers: bool = typer.Option(True, "--proxy-headers/--no-proxy-headers", help="Enable X-Forwarded-* proxy headers"),
    forwarded_allow_ips: str = typer.Option("127.0.0.1", "--forwarded-allow-ips", help="Allowed IPs for proxy headers (comma-separated or '*')"),
):
    """Run the production server (no reload)."""
    from lila.core.config import ConfigLoader, ENV_CONFIG

    if not os.path.exists("main.py"):
        typer.secho("❌ main.py not found. Run this command inside your project root.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    ConfigLoader.load()
    bind_host = host or ENV_CONFIG.get("HOST", "127.0.0.1")
    bind_port = int(port or ENV_CONFIG.get("PORT", 8000) or 8000)
    if workers > 1 and str(ENV_CONFIG.get("CACHE_DRIVER", "memory")) != "redis":
        typer.secho(
            "⚠️ Multiple workers with the memory cache: rate limits/sessions are per worker. "
            "Use CACHE_DRIVER=redis for shared state.",
            fg=typer.colors.YELLOW,
        )
    import uvicorn

    typer.secho(f"🚀 Lila v2.0.0 on http://{bind_host}:{bind_port} ({workers} worker(s))", fg=typer.colors.CYAN)
    uvicorn.run(
        "main:app",
        host=bind_host,
        port=bind_port,
        reload=False,
        workers=workers,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
    )


@app.command("routes")
def routes():
    """List the registered routes of main:app."""
    if not os.path.exists("main.py"):
        typer.secho("❌ main.py not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    try:
        import importlib

        main_module = importlib.import_module("main")
        app_obj = main_module.app
    except Exception as exc:
        typer.secho(f"❌ Could not import main:app: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    rows = []
    for route in getattr(app_obj, "routes", []):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not path:
            continue
        rows.append((path, ",".join(sorted(methods)) if methods else "WS/MOUNT"))
    for path, methods in sorted(rows):
        typer.echo(f"  {methods:<20} {path}")
    typer.echo(f"\n{len(rows)} routes.")


@app.command("doctor")
def doctor():
    """Check the project configuration, secret, database and templates."""
    import asyncio
    from lila.core.config import ConfigLoader, ENV_CONFIG, get_secret_key

    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.secho("❌ Not a Lila project root (main.py/app missing).", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    ok = True
    typer.echo("🩺 Lila doctor\n")

    if sys.version_info < (3, 10):
        typer.secho("  ❌ Python >=3.10 is required.", fg=typer.colors.RED)
        ok = False
    else:
        typer.secho(f"  ✅ Python {sys.version.split()[0]}", fg=typer.colors.GREEN)

    if os.path.exists(".env"):
        typer.secho("  ✅ .env found", fg=typer.colors.GREEN)
    else:
        typer.secho("  ⚠️ .env not found; defaults will be used.", fg=typer.colors.YELLOW)

    ConfigLoader.load()
    secret = get_secret_key()
    if len(secret) >= 32:
        typer.secho("  ✅ SECRET_KEY is set (>=32 chars)", fg=typer.colors.GREEN)
    else:
        typer.secho("  ⚠️ SECRET_KEY is short; rotate it with 'lila secret-key'.", fg=typer.colors.YELLOW)

    try:
        from app.connections import connection

        async def _check_db():
            return await connection.query_async("SELECT 1 AS ok", return_row=True)

        row = asyncio.run(_check_db())
        typer.secho(f"  ✅ Database reachable ({connection.type})", fg=typer.colors.GREEN)
        if row is None:
            ok = False
    except Exception as exc:
        typer.secho(f"  ❌ Database check failed: {exc}", fg=typer.colors.RED)
        ok = False

    project_templates = os.path.isdir(os.path.join("resources", "html"))
    package_templates = os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "resources", "html"))
    if project_templates or package_templates:
        typer.secho("  ✅ Templates available", fg=typer.colors.GREEN)
    else:
        typer.secho("  ❌ No templates found.", fg=typer.colors.RED)
        ok = False

    if os.path.isdir("public"):
        typer.secho("  ✅ public/ found", fg=typer.colors.GREEN)
    else:
        typer.secho("  ⚠️ public/ not found; bundled assets will be used.", fg=typer.colors.YELLOW)

    if ENV_CONFIG.get_bool("DEBUG", False):
        typer.secho("  ⚠️ DEBUG=True. Disable it in production.", fg=typer.colors.YELLOW)

    if not ok:
        raise typer.Exit(code=1)
    typer.secho("\n✅ Project looks healthy.", fg=typer.colors.GREEN)


app.add_typer(desktop_app, name="desktop", help="Desktop mode: run locally in native window or build .exe bundle.")
app.add_typer(auth_app, name="auth", help="Generate Auth 2.0 (OAuth 2.0, login, register, dashboard).")
app.add_typer(admin_app, name="admin", help="Setup Admin Panel 2.0 and superuser credentials.")
app.add_typer(migrations_app, name="migrate", help="Run database migrations.")
app.add_typer(migrations_app, name="migrations", help="Run database migrations (alias).")
app.add_typer(model_app, name="model", help="Generate and inspect ActiveRecord models.")
app.add_typer(crud_app, name="crud", help="Generate full CRUD routes, schemas, and DataTable view.")

@app.command("optimize")
def optimize():
    """Minify JS/CSS assets and convert PNG/JPG images to WebP."""
    optimize_main()

app.add_typer(secret_key_app, name="secret-key", help="Generate and rotate SECRET_KEY in .env.")
app.add_typer(seo_app, name="seo", help="Generate sitemap.xml and robots.txt.")
app.add_typer(worker_app, name="worker", help="Run background task worker process.")
app.add_typer(deploy_app, name="deploy", help="Generate production deployment configurations (systemd, Nginx, Windows).")
app.add_typer(backup_app, name="backup", help="Hot atomic SQLite database backup using sqlite3.backup().")

if __name__ == "__main__":
    app()
