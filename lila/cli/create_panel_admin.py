import os
import sys
import asyncio
import secrets
from pathlib import Path

import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.core.auth import PasswordHasher
from lila.core.config import ConfigLoader, ENV_CONFIG
from lila.cli._patch import patch_main

app = typer.Typer(help="Setup Admin 2.0 and create administrator credentials.")


def get_connection():
    try:
        from app.connections import connection
        return connection
    except Exception as exc:
        typer.secho(f"  ❌ Could not load app.connections: {exc}", fg=typer.colors.RED)
        return None


def copy_admin_files():
    import shutil

    dest_routes = os.path.join(os.getcwd(), "app", "routes", "admin")
    if not os.path.exists(dest_routes):
        src_routes = os.path.join(os.path.dirname(__file__), "..", "app", "routes", "admin")
        if os.path.exists(src_routes):
            shutil.copytree(src_routes, dest_routes, dirs_exist_ok=True)
            typer.echo("  📁 Admin routes copied to app/routes/admin/")

    # Admin templates are framework UI: upgrade them (with backups) so an old
    # v1.x dashboard does not crash against the new context.
    src_templates = os.path.join(os.path.dirname(__file__), "..", "resources", "html", "admin")
    dest_templates = os.path.join(os.getcwd(), "resources", "html", "admin")
    if os.path.exists(src_templates):
        os.makedirs(dest_templates, exist_ok=True)
        updated = 0
        for name in os.listdir(src_templates):
            source = os.path.join(src_templates, name)
            if not os.path.isfile(source):
                continue
            target = os.path.join(dest_templates, name)
            try:
                content = open(source, "r", encoding="utf-8").read()
                if os.path.exists(target) and open(target, "r", encoding="utf-8").read() == content:
                    continue
                if os.path.exists(target):
                    shutil.copy2(target, target + ".bak")
                shutil.copy2(source, target)
                updated += 1
            except Exception:
                pass
        if updated:
            typer.echo(f"  📄 Admin templates updated ({updated} files, old versions backed up).")


def update_main_routes() -> bool:
    main_file = os.path.join(os.getcwd(), "main.py")
    if not os.path.exists(main_file):
        return False
    import_stmt = "from app.routes.admin.index import router as admin_router"
    include_stmt = "app.include_router(admin_router)"
    if patch_main(main_file, import_stmt, include_stmt):
        typer.echo("  ✨ Admin routes linked in main.py.")
        return True
    return False


async def _create_async(connection, username: str, password: str) -> bool:
    from lila.core.admin import Admin, ensure_admin_table_async

    await ensure_admin_table_async(connection)
    row = await connection.query_async(
        "SELECT id FROM admins WHERE lower(username) = lower(:u) LIMIT 1",
        {"u": username},
        return_row=True,
    )
    hashed = await PasswordHasher.hash_async(password)
    if row:
        await Admin.update_async(row["id"], password=hashed, active=1)
        typer.echo(f"  🔁 Administrator '{username}' password updated.")
    else:
        await Admin.insert_async(username=username, password=hashed, active=1)
        typer.echo(f"  ✅ Administrator '{username}' created.")
    return True


def _create_sync(connection, username: str, password: str) -> bool:
    from lila.core.admin import Admin

    connection.migrate(use_base=True)
    row = connection.query(
        "SELECT id FROM admins WHERE lower(username) = lower(:u) LIMIT 1",
        {"u": username},
        return_row=True,
    )
    hashed = PasswordHasher.hash(password)
    if row:
        Admin.update(row["id"], password=hashed, active=1)
        typer.echo(f"  🔁 Administrator '{username}' password updated.")
    else:
        Admin.insert(username=username, password=hashed, active=1)
        typer.echo(f"  ✅ Administrator '{username}' created.")
    return True


@app.callback(invoke_without_command=True)
def default_admin(
    ctx: typer.Context,
    username: str = typer.Option("admin", "--user", "-u", "--username", help="Admin username"),
    password: str = typer.Option(None, "--password", "-p", help="Admin password (generated if omitted)"),
):
    """Setup Admin 2.0 tables and create/update a superuser."""
    if ctx.invoked_subcommand is None:
        create(username=username, password=password)


@app.command("create")
@app.command("setup")
def create(
    username: str = typer.Option("admin", "--user", "-u", "--username", help="Admin username"),
    password: str = typer.Option(None, "--password", "-p", help="Admin password (generated if omitted)"),
):
    """Setup Admin 2.0 tables and create/update a superuser."""
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.secho("❌ Error: Must run inside a Lila project root directory.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    ConfigLoader.load()
    connection = get_connection()
    if connection is None:
        typer.secho("❌ Could not connect to the project database via app.connections.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo("🛠️  Setting up Admin 2.0 tables...")
    copy_admin_files()

    admin_pw = password or secrets.token_urlsafe(12)
    try:
        if getattr(connection, "is_async", True):
            asyncio.run(_create_async(connection, username, admin_pw))
        else:
            _create_sync(connection, username, admin_pw)
    except Exception as exc:
        typer.secho(f"❌ Failed to create administrator: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    update_main_routes()
    typer.secho(f"✅ Administrator '{username}' ready!", fg=typer.colors.GREEN)
    typer.echo(f"   🔑 Password: {admin_pw}")
    host = ENV_CONFIG.get("HOST", "127.0.0.1")
    port = ENV_CONFIG.get("PORT", 8000)
    typer.echo(f"   🌐 Login at: http://{host}:{port}/admin")


def main():
    app()


if __name__ == "__main__":
    main()
