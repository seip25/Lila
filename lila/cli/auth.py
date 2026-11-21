import sys
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.cli._patch import patch_main

app = typer.Typer(help="Generate complete Auth 2.0 system (login, register, forgot-password, dashboard, OAuth).")

package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
user_project_root = os.getcwd()


def _write_with_backup(path: Path, content: str) -> None:
    """Writes a generated file, backing up a differing existing file."""
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != content:
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as exc:
        typer.secho(f"  ⚠️ Could not write {path}: {exc}", fg=typer.colors.YELLOW)

def read_file(rel_path: str) -> str:
    path = os.path.join(package_root, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _create_templates():
    templates_dir = Path("resources/html/auth")
    templates_dir.mkdir(parents=True, exist_ok=True)

    templates = {
        "login.jinja":           read_file("cli/auth/templates/login.jinja"),
        "register.jinja":        read_file("cli/auth/templates/register.jinja"),
        "forgot-password.jinja": read_file("cli/auth/templates/forgot-password.jinja"),
        "change-password.jinja": read_file("cli/auth/templates/change-password.jinja"),
        "invalid-token.jinja":   read_file("cli/auth/templates/invalid-token.jinja"),
    }

    for filename, content in templates.items():
        file_path = templates_dir / filename
        _write_with_backup(file_path, content)
        typer.echo(f"  📄 Template created: {file_path}")

    template_dashboard_dir = Path("resources/html/authenticated")
    template_dashboard_dir.mkdir(parents=True, exist_ok=True)
    templates_dashboard = {
        "dashboard.jinja": read_file("cli/auth/templates/dashboard.jinja"),
        "profile.jinja":   read_file("cli/auth/templates/profile.jinja"),
    }
    for filename, content in templates_dashboard.items():
        file_path = template_dashboard_dir / filename
        _write_with_backup(file_path, content)
        typer.echo(f"  📄 Template created: {file_path}")


def _create_routes():
    main_file = os.path.join(user_project_root, "main.py")

    if not os.path.exists(main_file):
        typer.secho("❌ main.py not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    import_stmt = (
        "from app.routes.web.auth import routes as auth_routes\n"
        "from app.routes.web.authenticated import routes as authenticated_routes"
    )
    include_stmt = "app.include_router(auth_routes)\napp.include_router(authenticated_routes)"

    if patch_main(main_file, import_stmt, include_stmt):
        typer.echo("  ✨ Auth routes linked in main.py.")
    else:
        typer.echo("ℹ️ Auth routes already present (or main.py could not be patched safely).")


# `lila auth --react`: page handlers render React pages instead of Jinja. The
# JSON endpoints (POST /login, /register, ...) are shared by both versions.
_REACT_IMPORT = "from lila.core.react import react_render"
_RT = "robots=\"noindex\", translations=True"
REACT_PAGE_REPLACEMENTS = {
    "login.py": [
        (
            'return render(request=request, template="auth/login", csrf=True, title="sign_in")',
            f'return react_render(request, "Auth/Login", {{"providers": OAuth.configured_providers()}}, title="sign_in", {_RT})',
        ),
    ],
    "register.py": [
        (
            'return render(request=request, template="auth/register", csrf=True, title="register")',
            f'return react_render(request, "Auth/Register", {{"providers": OAuth.configured_providers()}}, title="register", {_RT})',
        ),
    ],
    "forgot_password.py": [
        (
            'return render(request=request, template="auth/forgot-password", csrf=True, title="recover_password")',
            f'return react_render(request, "Auth/ForgotPassword", {{}}, title="recover_password", {_RT})',
        ),
    ],
    "change_password.py": [
        (
            'return render(request=request, template="auth/invalid-token", status_code=400, title="invalid or expired token", robots="noindex")',
            f'return react_render(request, "Auth/InvalidToken", {{}}, status_code=400, title="invalid or expired token", {_RT})',
        ),
        (
            """return render(
        request=request,
        template="auth/change-password",
        context={"token": token},
        csrf=True,
        title="reset_password",
        robots="noindex",
    )""",
            f'return react_render(request, "Auth/ChangePassword", {{"token": token}}, title="reset_password", {_RT})',
        ),
    ],
    "dashboard.py": [
        (
            'return render(request=request, template="authenticated/dashboard", context=context, title="dashboard", robots="noindex")',
            f'return react_render(request, "Account/Dashboard", context, title="dashboard", {_RT})',
        ),
    ],
    "profile.py": [
        (
            'return render(request=request, template="authenticated/profile", context=context, csrf=True, title="profile", robots="noindex")',
            f'return react_render(request, "Account/Profile", context, title="profile", {_RT})',
        ),
    ],
}


def reactify_route(filename: str, content: str) -> str:
    """Returns the React version of a generated route file (exact, checked replacements)."""
    replacements = REACT_PAGE_REPLACEMENTS.get(filename)
    if not replacements:
        return content
    for old, new in replacements:
        if old not in content:
            raise RuntimeError(f"lila auth --react: page handler not found in {filename}")
        content = content.replace(old, new)
    content = content.replace(
        "from lila.core.templates import render\n",
        f"{_REACT_IMPORT}\n",
        1,
    )
    if "OAuth.configured_providers" in content and "from lila.core.oauth import OAuth" not in content:
        content = content.replace(f"{_REACT_IMPORT}\n", f"{_REACT_IMPORT}\nfrom lila.core.oauth import OAuth\n", 1)
    return content


def _create_react_pages():
    """Copies the React auth pages; sets up React (TypeScript) when missing."""
    from lila.cli.react import copy_ui, init as react_init, is_react_project

    if not is_react_project():
        typer.secho("  ⚛️  React is not set up yet: running `lila react init --no-routes`...", fg=typer.colors.CYAN)
        react_init(install=False, force=False, routes=False, js=False)
    else:
        copy_ui(quiet=True)  # the pages use components/ui and @lila (missing files only)
    base = Path(package_root) / "cli" / "auth" / "react"
    for src in sorted(base.rglob("*.tsx")):
        rel = src.relative_to(base)
        target = Path("resources/react") / rel
        _write_with_backup(target, src.read_text(encoding="utf-8"))
        typer.echo(f"  ⚛️  {target}")
    main_jsx = Path("resources/react/main.jsx")
    if main_jsx.exists() and ".tsx" not in main_jsx.read_text(encoding="utf-8"):
        typer.secho(
            '  ⚠️ resources/react/main.jsx only globs .jsx: use import.meta.glob("./pages/**/*.{jsx,tsx}")',
            fg=typer.colors.YELLOW,
        )


def _create_auth_files(react: bool = False):
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/auth"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":        read_file("cli/auth/routes/auth_init.py"),
        "login.py":           read_file("cli/auth/routes/login.py"),
        "register.py":        read_file("cli/auth/routes/register.py"),
        "logout.py":          read_file("cli/auth/routes/logout.py"),
        "forgot_password.py": read_file("cli/auth/routes/forgot_password.py"),
        "change_password.py": read_file("cli/auth/routes/change_password.py"),
        "me.py":              read_file("cli/auth/routes/me.py"),
    }
    for filename, content in files.items():
        if react:
            content = reactify_route(filename, content)
        _write_with_backup(auth_dir / filename, content)

    typer.echo("  📁 Route files created in app/routes/web/auth/")


def _create_authenticated_files(react: bool = False):
    auth_dir = Path(os.path.join(user_project_root, "app/routes/web/authenticated"))
    auth_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "__init__.py":  read_file("cli/auth/routes/authenticated_init.py"),
        "dashboard.py": read_file("cli/auth/routes/dashboard.py"),
        "profile.py":   read_file("cli/auth/routes/profile.py"),
    }
    for filename, content in files.items():
        if react:
            content = reactify_route(filename, content)
        _write_with_backup(auth_dir / filename, content)

    typer.echo("  📁 Route files created in app/routes/web/authenticated/")


def _overwrite_user_model():
    user_model_path = Path(user_project_root) / "app/models/user.py"
    content = read_file("cli/auth/models/user.py")
    if user_model_path.exists() and user_model_path.read_text(encoding="utf-8") == content:
        typer.echo("  👤 User model already up to date.")
        return
    _write_with_backup(user_model_path, content)
    typer.echo("  👤 User model updated with OAuth and Argon2/PasswordHasher (previous file backed up).")


def _create_auth_model():
    model_path = Path(user_project_root) / "app/models/auth.py"
    content = read_file("cli/auth/models/auth.py")
    _write_with_backup(model_path, content)

    # Plain migrations: never --refresh (that would drop existing users).
    import subprocess

    result = subprocess.run([sys.executable, "-m", "lila.cli.migrations"], cwd=user_project_root)
    if result.returncode != 0:
        typer.secho(
            "  ⚠️ Migrations did not finish successfully; run 'lila migrate' manually.",
            fg=typer.colors.YELLOW,
        )
    typer.echo("  🔐 LoginAttempt & PasswordResetToken models registered.")

_TEMPLATES_HELP = "Generate Jinja2 auth templates (default: yes, no with --react)"
_REACT_HELP = "React (TypeScript) pages for login, register, forgot/reset password, dashboard and profile"


@app.callback(invoke_without_command=True)
def default_auth(
    ctx: typer.Context,
    template: Optional[bool] = typer.Option(None, "--templates/--no-templates", help=_TEMPLATES_HELP),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Generate auth and dashboard routes"),
    react: bool = typer.Option(False, "--react", help=_REACT_HELP),
):
    """Scaffold authentication system with OAuth 2.0, Argon2, and dashboard."""
    if ctx.invoked_subcommand is None:
        generate(template=template, routes=routes, react=react)


@app.command()
def generate(
    template: Optional[bool] = typer.Option(None, "--templates/--no-templates", help=_TEMPLATES_HELP),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Generate auth and dashboard routes"),
    react: bool = typer.Option(False, "--react", help=_REACT_HELP),
):
    """
    Scaffold authentication system with OAuth 2.0, Argon2, and dashboard.
    """
    if template is None:
        template = not react
    if not os.path.exists("main.py") or not os.path.exists("app"):
        typer.secho("❌ Error: Must run inside a Lila project root directory.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("🔐 Generating Lila Auth 2.0...", fg=typer.colors.CYAN)

    if template:
        _create_templates()

    if react:
        _create_react_pages()

    if routes:
        _create_auth_files(react=react)
        _create_authenticated_files(react=react)
        _overwrite_user_model()
        _create_auth_model()
        _create_routes()

    typer.secho("✅ Auth 2.0 generated successfully! OAuth ready with Google, GitHub, and Discord.", fg=typer.colors.GREEN)
    if react:
        typer.echo("   React pages: resources/react/pages/Auth/* and Account/* — run `lila react dev`.")

def main():
    app()

if __name__ == "__main__":
    app()

