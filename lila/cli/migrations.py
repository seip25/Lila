import sys
import os
import asyncio
import importlib
from pathlib import Path
from typing import Optional

import typer

load_errors = []
connection = None

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Manage database migrations (SQLAlchemy metadata sync).")


def _load_connection():
    """Loads .env and app.connections lazily (CLI --help stays fast)."""
    global connection
    if connection is not None:
        return connection
    from lila.core.config import ConfigLoader

    ConfigLoader.load()
    try:
        from app.connections import connection as project_connection

        connection = project_connection
    except ImportError:
        connection = None
    return connection


def load_models():
    """Imports app models (and the admin model) so Base.metadata is complete."""
    try:
        import lila.core.admin  # noqa: F401  (registers the admins table)
    except Exception as exc:
        load_errors.append(f"lila.core.admin: {exc}")

    models_dir = Path("app/models")
    if not models_dir.exists():
        return
    for file in models_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue
        module_name = f"app.models.{file.stem}"
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            load_errors.append(f"{module_name}: {exc}")
            typer.echo(f"  ⚠️ Could not load {module_name}: {exc}")


async def migrate_async(conn, refresh: bool = False) -> bool:
    try:
        load_models()
        if refresh:
            typer.echo("🔄 Dropping existing tables...")
            if getattr(conn, "is_async", False):
                await conn.drop_all_async(use_base=True)
            else:
                conn.drop_all(use_base=True)

        typer.echo("🚀 Running migrations...")
        if getattr(conn, "is_async", False):
            report = await conn.migrate_async(use_base=True)
        else:
            conn.migrate(use_base=True)
            report = {}

        added = (report or {}).get("added_columns", [])
        if added:
            typer.secho(f"  ➕ Added columns: {', '.join(added)}", fg=typer.colors.CYAN)
        if load_errors:
            typer.secho(
                f"❌ {len(load_errors)} model(s) failed to import; their tables may be missing.",
                fg=typer.colors.RED,
            )
            for error in load_errors:
                typer.echo(f"   - {error}")
            return False
        typer.secho("✅ Migrations completed successfully!", fg=typer.colors.GREEN)
        return True
    except Exception as exc:
        typer.secho(f"❌ Migration error: {exc}", fg=typer.colors.RED)
        return False
    finally:
        if conn and getattr(conn, "engine", None):
            try:
                if getattr(conn, "is_async", False):
                    await conn.engine.dispose()
                else:
                    conn.engine.dispose()
            except Exception:
                pass


@app.callback(invoke_without_command=True)
def default_migrate(
    ctx: typer.Context,
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Drop all tables before migrating"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before --refresh"),
):
    """Run database migrations to synchronize models with the database."""
    if ctx.invoked_subcommand is None:
        migrate(refresh=refresh, yes=yes)


@app.command()
def migrate(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Drop all tables before migrating"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before --refresh"),
):
    """Run database migrations and add missing columns."""
    project_connection = _load_connection()
    if project_connection is None:
        typer.secho(
            "❌ Error: 'app.connections' not found. Run inside the root directory of your Lila project.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if refresh and not yes:
        confirmed = typer.confirm("⚠️ --refresh deletes ALL tables and data. Continue?")
        if not confirmed:
            typer.echo("Cancelled.")
            raise typer.Exit(code=1)

    success = asyncio.run(migrate_async(project_connection, refresh))
    if not success:
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()
