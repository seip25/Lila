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

app.add_typer(desktop_app, name="desktop", help="Desktop mode: run locally in native window or build .exe bundle.")
app.add_typer(auth_app, name="auth", help="Generate Auth 2.0 (OAuth Better Auth, login, register, dashboard).")
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

if __name__ == "__main__":
    app()
