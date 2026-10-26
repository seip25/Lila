import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import typer

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer(help="Generate SEO sitemap.xml and robots.txt.")

def _get_base_url(domain: str = None) -> str:
    if domain:
        return domain.rstrip("/")
    try:
        from lila.core.config import ENV_CONFIG
        app_url = ENV_CONFIG.get("APP_URL")
        if app_url:
            return app_url.rstrip("/")
        host = ENV_CONFIG.get("HOST", "127.0.0.1")
        port = ENV_CONFIG.get("PORT", "8000")
        return f"http://{host}:{port}"
    except Exception:
        return "http://127.0.0.1:8000"

@app.callback(invoke_without_command=True)
def default_seo(
    ctx: typer.Context,
    domain: str = typer.Option(None, "--domain", "-d", help="Base production domain"),
):
    """Generate both sitemap.xml and robots.txt."""
    if ctx.invoked_subcommand is None:
        sitemap(domain=domain)
        robots(domain=domain)


@app.command()
def sitemap(domain: str = typer.Option(None, "--domain", "-d", help="Base production domain")):
    """
    Generate public/sitemap.xml for web search engines.
    """
    base_url = _get_base_url(domain)
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    today = datetime.now().strftime("%Y-%m-%d")

    # Always include homepage
    xml_content += f"  <url>\n    <loc>{base_url}/</loc>\n    <lastmod>{today}</lastmod>\n    <priority>1.0</priority>\n  </url>\n"
    xml_content += f"  <url>\n    <loc>{base_url}/docs</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.8</priority>\n  </url>\n"
    xml_content += "</urlset>"

    out_file = Path("public/sitemap.xml")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(xml_content, encoding="utf-8")
    typer.secho(f"✅ Sitemap generated at {out_file} (base: {base_url})", fg=typer.colors.GREEN)

@app.command()
def robots(domain: str = typer.Option(None, "--domain", "-d", help="Base production domain")):
    """
    Generate public/robots.txt file.
    """
    base_url = _get_base_url(domain)
    content = f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api\nDisallow: /debug\n\nSitemap: {base_url}/sitemap.xml\n"
    out_file = Path("public/robots.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8")
    typer.secho(f"✅ Robots.txt generated at {out_file}", fg=typer.colors.GREEN)

def main():
    app()

if __name__ == "__main__":
    main()
