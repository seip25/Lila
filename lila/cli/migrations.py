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


_ICONS = {
    "create_table": "🆕", "add_column": "➕", "rename_column": "✏️", "create_index": "⚡",
    "drop_column": "🗑️", "alter_type": "⚠️", "alter_nullable": "⚠️", "add_column_manual": "⚠️",
}


def print_plan(ops) -> None:
    if not ops:
        typer.secho("✅ Database schema matches the models.", fg=typer.colors.GREEN)
        return
    typer.secho(f"📋 {len(ops)} difference(s):", fg=typer.colors.CYAN, bold=True)
    for op in ops:
        tag = "safe" if op["safe"] else ("needs --drop-columns" if op["kind"] == "drop_column" else "manual")
        color = typer.colors.GREEN if op["safe"] else typer.colors.YELLOW
        typer.secho(f"  {_ICONS.get(op['kind'], '•')} {op['kind']:<18} {op['target']:<32} {op['detail']}  [{tag}]", fg=color)


async def migrate_async(conn, refresh: bool = False, plan_only: bool = False, drop_columns: bool = False) -> bool:
    from lila.core import migrations as mig

    try:
        load_models()
        if load_errors:
            typer.secho(
                f"❌ {len(load_errors)} model(s) failed to import; fix them before migrating.",
                fg=typer.colors.RED,
            )
            for error in load_errors:
                typer.echo(f"   - {error}")
            return False
        if refresh and not plan_only:
            typer.echo("🔄 Dropping existing tables...")
            if getattr(conn, "is_async", False):
                await conn.drop_all_async(use_base=True)
            else:
                conn.drop_all(use_base=True)

        if not getattr(conn, "is_async", False):
            typer.echo("🚀 Running migrations (sync engine: tables + columns)...")
            conn.migrate(use_base=True)
            typer.secho("✅ Migrations completed successfully!", fg=typer.colors.GREEN)
            return True

        ops = await mig.plan_async(conn)
        print_plan(ops)
        if plan_only:
            return True
        to_apply = [op for op in ops if op["safe"] or (drop_columns and op["kind"] == "drop_column")]
        if to_apply:
            applied = await mig.apply_async(conn, to_apply, drop_columns=drop_columns)
            typer.secho(f"✅ Applied {len(applied)} operation(s) (recorded in app/data/lila_system.db).",
                        fg=typer.colors.GREEN)
        pending = [op for op in ops if op not in to_apply]
        if pending:
            typer.secho(f"ℹ️  {len(pending)} operation(s) need a manual decision (see above).", fg=typer.colors.YELLOW)
        elif not to_apply:
            typer.secho("✅ Nothing to do.", fg=typer.colors.GREEN)
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
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before --refresh/--drop-columns"),
    plan: bool = typer.Option(False, "--plan", "-p", help="Only show the differences, change nothing"),
    drop_columns: bool = typer.Option(False, "--drop-columns", help="Also drop columns removed from the models"),
):
    """Run database migrations to synchronize models with the database."""
    if ctx.invoked_subcommand is None:
        migrate(refresh=refresh, yes=yes, plan=plan, drop_columns=drop_columns)


@app.command()
def migrate(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Drop all tables before migrating"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before --refresh/--drop-columns"),
    plan: bool = typer.Option(False, "--plan", "-p", help="Only show the differences, change nothing"),
    drop_columns: bool = typer.Option(False, "--drop-columns", help="Also drop columns removed from the models"),
):
    """Create tables, add/rename columns and indexes; report risky changes."""
    project_connection = _load_connection()
    if project_connection is None:
        typer.secho(
            "❌ Error: 'app.connections' not found. Run inside the root directory of your Lila project.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if refresh and not yes and not plan:
        confirmed = typer.confirm("⚠️ --refresh deletes ALL tables and data. Continue?")
        if not confirmed:
            typer.echo("Cancelled.")
            raise typer.Exit(code=1)
    if drop_columns and not yes and not plan:
        if not typer.confirm("⚠️ --drop-columns deletes the data of removed columns. Continue?"):
            typer.echo("Cancelled.")
            raise typer.Exit(code=1)

    success = asyncio.run(migrate_async(project_connection, refresh, plan_only=plan, drop_columns=drop_columns))
    if not success:
        raise typer.Exit(code=1)


@app.command("history")
def history_cmd(limit: int = typer.Option(30, "--limit", "-n")):
    """Show the operations applied by `lila migrate`."""
    from lila.core.config import ConfigLoader
    from lila.core.migrations import history

    ConfigLoader.load()
    rows = history(limit)
    if not rows:
        typer.echo("No migrations recorded yet.")
        return
    for row in rows:
        typer.echo(f"  {row['applied_at']}  {row['kind']:<15} {row['target']:<32} {row['detail'] or ''}")


def main():
    app()


if __name__ == "__main__":
    main()
