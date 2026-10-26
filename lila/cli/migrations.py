import sys
import os
from pathlib import Path
import asyncio
import importlib
import typer
from dotenv import load_dotenv

load_dotenv()

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

try:
    from app.connections import connection
except ImportError:
    connection = None

app = typer.Typer(help="Manage database migrations (SQLAlchemy metadata sync).")

def load_models():
    models_dir = Path("app/models")
    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            if file.name != "__init__.py":
                module_name = f"app.models.{file.stem}"
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    typer.echo(f"  ⚠️ Warning loading {module_name}: {e}")

async def migrate_async(conn, refresh: bool = False) -> bool:
    try:
        load_models()
        if refresh:
            typer.echo("🔄 Dropping existing tables...")
            if hasattr(conn, "drop_all_async") and getattr(conn, "is_async", False):
                await conn.drop_all_async(use_base=True)
            elif hasattr(conn, "drop_all"):
                conn.drop_all(use_base=True)

        typer.echo("🚀 Running migrations...")
        if hasattr(conn, "migrate_async") and getattr(conn, "is_async", False):
            await conn.migrate_async(use_base=True)
        else:
            conn.migrate(use_base=True)

        typer.secho("✅ Migrations completed successfully!", fg=typer.colors.GREEN)
        return True
    except Exception as e:
        typer.secho(f"❌ Migration error: {e}", fg=typer.colors.RED)
        return False
    finally:
        if conn and getattr(conn, "is_async", False) and conn.engine:
            await conn.engine.dispose()

@app.command()
def migrate(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Drop all tables before running migrations"),
):
    """
    Run database migrations to synchronize models with the database.
    """
    if connection is None:
        typer.secho("❌ Error: 'app.connections' not found. Make sure you are in the root directory of your Lila project.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    success = asyncio.run(migrate_async(connection, refresh))
    if not success:
        raise typer.Exit(code=1)

def main():
    app()

if __name__ == "__main__":
    main()
