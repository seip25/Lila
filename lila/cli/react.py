"""``lila react`` — React + Vite integration.

    lila react init      # package.json, vite.config.js, resources/react/*, example routes
    lila react dev       # Vite (HMR / Fast Refresh) + Lila dev server together
    lila react build     # vite build -> public/build (+ manifest) for production/desktop
    lila react status    # which mode pages use right now (dev / build / missing)

Node.js is only needed to develop and build; production servers and desktop
builds only serve the files in ``public/build``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional

import typer

app = typer.Typer(help="React + Vite: init, dev (HMR) and production build.")

SCAFFOLD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "react_scaffold")
IMPORT_STMT = "from app.routes.web.react_pages import router as react_router"
INCLUDE_STMT = "app.include_router(react_router)"
GITIGNORE_LINES = ("node_modules/", "public/build/hot")


def _npm() -> Optional[str]:
    return shutil.which("npm") or shutil.which("npm.cmd")


def _require_npm() -> str:
    npm = _npm()
    if not npm:
        typer.secho("❌ Node.js/npm not found. Install Node.js 20+ (https://nodejs.org) to develop or build React.", fg=typer.colors.RED)
        typer.echo("   Production servers do not need Node: deploy the files in public/build.")
        raise typer.Exit(code=1)
    return npm


def is_react_project(root: str = ".") -> bool:
    """True when the project has a Vite config and a package.json."""
    has_config = any(os.path.isfile(os.path.join(root, name)) for name in ("vite.config.js", "vite.config.mjs", "vite.config.ts"))
    return has_config and os.path.isfile(os.path.join(root, "package.json"))


def _ensure_install(npm: str, install: bool) -> None:
    if os.path.isdir("node_modules"):
        return
    if not install:
        typer.secho("❌ node_modules/ is missing: run `npm install` first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("📦 Installing JavaScript dependencies (npm install)...", fg=typer.colors.CYAN)
    result = subprocess.run([npm, "install"])
    if result.returncode != 0:
        typer.secho("❌ npm install failed.", fg=typer.colors.RED)
        raise typer.Exit(code=result.returncode)


def _copy_scaffold(force: bool) -> List[str]:
    written = []
    for dirpath, _dirs, files in os.walk(SCAFFOLD_DIR):
        for filename in files:
            if filename.endswith((".pyc",)) or "__pycache__" in dirpath:
                continue
            src = os.path.join(dirpath, filename)
            rel = os.path.relpath(src, SCAFFOLD_DIR)
            if os.path.exists(rel) and not force:
                typer.echo(f"   · kept {rel} (exists)")
                continue
            os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
            if os.path.exists(rel):
                shutil.copy2(rel, rel + ".bak")
            shutil.copy2(src, rel)
            written.append(rel)
            typer.echo(f"   + {rel}")
    return written


def _update_gitignore() -> None:
    path = ".gitignore"
    try:
        current = open(path, "r", encoding="utf-8").read() if os.path.exists(path) else ""
    except OSError:
        return
    missing = [line for line in GITIGNORE_LINES if line not in current.splitlines()]
    if not missing:
        return
    with open(path, "a", encoding="utf-8") as fh:
        if current and not current.endswith("\n"):
            fh.write("\n")
        fh.write("\n# React / Vite\n" + "\n".join(missing) + "\n")


@app.command("init")
def init(
    install: bool = typer.Option(False, "--install", help="Run npm install afterwards."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files (a .bak copy is kept)."),
    routes: bool = typer.Option(True, "--routes/--no-routes", help="Register the example routes in main.py."),
):
    """Add React + Vite to the current Lila project (never overwrites without --force)."""
    if not os.path.exists("main.py"):
        typer.secho("❌ main.py not found. Run this inside a Lila project (lila init).", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("⚛️  Adding React + Vite to this project...", fg=typer.colors.CYAN)
    _copy_scaffold(force)
    _update_gitignore()
    if routes:
        from lila.cli._patch import patch_main

        if patch_main("main.py", IMPORT_STMT, INCLUDE_STMT):
            typer.echo("   ~ main.py: react_router included")
    if install:
        _ensure_install(_require_npm(), True)
    typer.secho("\n✅ React is ready.", fg=typer.colors.GREEN)
    typer.echo("   lila react dev     → http://127.0.0.1:8000/react (pages) and /app (SPA), with HMR")
    typer.echo("   lila react build   → public/build for production and `lila desktop build`")


@app.command("dev")
def dev(
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Lila host"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Lila port"),
    vite_port: int = typer.Option(5173, "--vite-port", help="Vite dev-server port"),
    install: bool = typer.Option(True, "--install/--no-install", help="npm install when node_modules/ is missing."),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Reload Python on changes"),
):
    """Run Vite (HMR, React Fast Refresh) and the Lila dev server together."""
    if not is_react_project():
        typer.secho("❌ No vite.config.js/package.json here. Run `lila react init` first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    npm = _require_npm()
    _ensure_install(npm, install)

    env = os.environ.copy()
    env["VITE_PORT"] = str(vite_port)
    typer.secho(f"⚡ Vite dev server on http://127.0.0.1:{vite_port}", fg=typer.colors.CYAN)
    vite_proc = subprocess.Popen([npm, "run", "dev", "--", "--port", str(vite_port), "--strictPort"], env=env)
    try:
        # Wait briefly for the hot file so the first page already uses Vite.
        hot = os.path.join("public", "build", "hot")
        for _ in range(50):
            if os.path.exists(hot) or vite_proc.poll() is not None:
                break
            time.sleep(0.1)
        if vite_proc.poll() is not None:
            typer.secho("❌ Vite exited. Check the output above.", fg=typer.colors.RED)
            raise typer.Exit(code=vite_proc.returncode or 1)
        from lila.cli.dev import start as dev_start

        dev_start(host=host, port=port, reload=reload)
    finally:
        if vite_proc.poll() is None:
            vite_proc.terminate()
            try:
                vite_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite_proc.kill()
        hot = os.path.join("public", "build", "hot")
        if os.path.exists(hot):
            try:
                os.remove(hot)
            except OSError:
                pass


def run_build(install: bool = True, quiet: bool = False) -> bool:
    """Runs ``vite build``; returns True when a manifest was produced."""
    npm = _require_npm()
    _ensure_install(npm, install)
    hot = os.path.join("public", "build", "hot")
    if os.path.exists(hot):
        os.remove(hot)
    if not quiet:
        typer.secho("📦 Building React assets (vite build)...", fg=typer.colors.CYAN)
    env = os.environ.copy()
    env.setdefault("NODE_ENV", "production")
    result = subprocess.run([npm, "run", "build"], env=env)
    if result.returncode != 0:
        typer.secho("❌ vite build failed.", fg=typer.colors.RED)
        return False
    from lila.core.vite import manifest_path

    path = manifest_path()
    if not os.path.isfile(path):
        typer.secho("❌ Build finished without a manifest. Keep `build.manifest: true` in vite.config.js.", fg=typer.colors.RED)
        return False
    return True


@app.command("build")
def build(
    install: bool = typer.Option(True, "--install/--no-install", help="npm install when node_modules/ is missing."),
):
    """Build production assets into public/build (hashed files + manifest)."""
    if not is_react_project():
        typer.secho("❌ No vite.config.js/package.json here. Run `lila react init` first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not run_build(install=install):
        raise typer.Exit(code=1)
    from lila.core.vite import manifest_path

    with open(manifest_path(), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    entries = [key for key, chunk in manifest.items() if chunk.get("isEntry")]
    total = 0
    for chunk in manifest.values():
        target = os.path.join("public", "build", chunk.get("file", ""))
        if os.path.isfile(target):
            total += os.path.getsize(target)
    typer.secho(f"✅ {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} built ({total / 1024:.1f} KB of JS/CSS):", fg=typer.colors.GREEN)
    for entry in entries:
        typer.echo(f"   {entry} → public/build/{manifest[entry]['file']}")
    typer.echo("   Deploy public/build with the app; Node is not needed on the server.")


@app.command("status")
def status():
    """Show whether pages load assets from Vite (dev), the build, or nothing."""
    from lila.core.config import ConfigLoader

    ConfigLoader.load()
    from lila.core.vite import status as vite_status

    mode, detail = vite_status()
    color = {"dev": typer.colors.CYAN, "build": typer.colors.GREEN}.get(mode, typer.colors.YELLOW)
    typer.secho(f"  {mode}: {detail}", fg=color)
    if mode == "missing":
        raise typer.Exit(code=1)


def main():  # pragma: no cover - console script
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
