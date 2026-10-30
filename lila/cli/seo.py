import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Set
from xml.sax.saxutils import escape

import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from lila.core.config import ConfigLoader, ENV_CONFIG

app = typer.Typer(help="Generate SEO sitemap.xml and robots.txt.")


def _get_base_url(domain: Optional[str] = None) -> str:
    if domain:
        return domain.rstrip("/")
    ConfigLoader.load()
    app_url = str(ENV_CONFIG.get("APP_URL", "") or "").strip()
    if app_url:
        return app_url.rstrip("/")
    host = ENV_CONFIG.get("HOST", "127.0.0.1")
    port = ENV_CONFIG.get("PORT", 8000)
    return f"http://{host}:{port}"


def _discover_paths() -> Set[str]:
    """Best-effort discovery of public GET routes from main:app."""
    paths: Set[str] = {"/"}
    excluded_prefixes = (
        "/api", "/admin", "/docs", "/openapi", "/swagger", "/_lila",
        "/public", "/uploads", "/favicon", "/debug", "/health",
        "/auth/", "/change-password", "/forgot-password", "/delete-account",
    )
    excluded_exact = {"/login", "/register", "/logout", "/dashboard", "/profile"}
    try:
        import importlib

        main_module = importlib.import_module("main")
        app_obj = getattr(main_module, "app", None)
        for route in getattr(app_obj, "routes", []):
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            if "GET" not in methods:
                continue
            if not path or "{" in path or path.endswith((".xml", ".txt", ".ico")):
                continue
            if path in excluded_exact or path.startswith(excluded_prefixes):
                continue
            paths.add(path)
    except Exception:
        pass
    return paths


@app.callback(invoke_without_command=True)
def default_seo(
    ctx: typer.Context,
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Base production domain"),
):
    """Generate both sitemap.xml and robots.txt."""
    if ctx.invoked_subcommand is None:
        sitemap(domain=domain, extra_paths=None)
        robots(domain=domain)


@app.command()
def sitemap(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Base production domain"),
    extra_paths: Optional[str] = typer.Option(None, "--paths", help="Comma-separated extra paths"),
):
    """Generate public/sitemap.xml for web search engines."""
    base_url = _get_base_url(domain)
    paths = _discover_paths()
    if extra_paths and isinstance(extra_paths, str):
        paths.update(p.strip() for p in extra_paths.split(",") if p.strip())

    today = datetime.now().strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in sorted(paths):
        loc = f"{base_url}{path}"
        lines.append(
            f"  <url><loc>{escape(loc)}</loc><lastmod>{today}</lastmod>"
            f"<priority>{'1.0' if path == '/' else '0.8'}</priority></url>"
        )
    lines.append("</urlset>")

    out_file = Path("public/sitemap.xml")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.secho(f"✅ Sitemap generated at {out_file} ({len(paths)} URLs, base: {base_url})", fg=typer.colors.GREEN)


@app.command()
def robots(domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Base production domain")):
    """Generate public/robots.txt."""
    base_url = _get_base_url(domain)
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api\n"
        "Disallow: /debug\n"
        "Disallow: /uploads\n\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    out_file = Path("public/robots.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8")
    typer.secho(f"✅ Robots.txt generated at {out_file}", fg=typer.colors.GREEN)


def main():
    app()


if __name__ == "__main__":
    main()
