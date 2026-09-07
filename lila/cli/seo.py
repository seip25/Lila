import sys
import os
from pathlib import Path
import typer
from datetime import datetime

# English: Ensure the current directory is in sys.path to import app modules.
# Español: Asegurar que el directorio actual esté en sys.path para importar módulos de la app.
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

app = typer.Typer()

def _get_base_url(domain: str = None) -> str:
    """
    English: Resolves the base URL for SEO files. Priority: CLI --domain flag > APP_URL from .env > fallback HOST:PORT.
    Español: Resuelve la URL base para archivos SEO. Prioridad: flag --domain del CLI > APP_URL de .env > fallback HOST:PORT.
    """
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
        return "http://localhost:8000"

@app.command()
def sitemap(domain: str = None):
    """
    English: Generates a sitemap.xml based on the application routes.
             Uses APP_URL from .env by default, or --domain to override.
    Español: Genera un sitemap.xml basado en las rutas de la aplicación.
             Usa APP_URL de .env por defecto, o --domain para sobreescribir.
    """
    base_url = _get_base_url(domain)
    
    try:
        # English: Attempt to discover routes from common locations.
        # Español: Intentar descubrir rutas desde ubicaciones comunes.
        from app.routes.routes import routes as web_routes
    except ImportError:
        web_routes = []

    try:
        from app.routes.api import routes as api_routes
    except ImportError:
        api_routes = []

    all_routes = web_routes + api_routes
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    processed_paths = set()
    
    for route in all_routes:
        if not hasattr(route, "path"):
            continue
            
        path = route.path
        
        # English: Exclude dynamic routes with parameters, private areas, and system routes.
        # Español: Excluir rutas dinámicas con parámetros, áreas privadas y rutas del sistema.
        if "{" in path or path.startswith("/admin") or path.startswith("/api") or path in ["/docs", "/openapi.json"]:
            continue
            
        if path in processed_paths:
            continue
            
        processed_paths.add(path)
        
        full_url = f"{base_url}{path}"
        xml_content += f"  <url>\n    <loc>{full_url}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.8</priority>\n  </url>\n"
    
    xml_content += "</urlset>"
    
    output_path = Path("public/sitemap.xml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_content, encoding="utf-8")
    
    typer.echo(f"✅ Sitemap generated at {output_path} (base URL: {base_url})")

@app.command()
def robots(domain: str = None):
    """
    English: Generates a robots.txt file.
             Uses APP_URL from .env by default, or --domain to override.
    Español: Genera un archivo robots.txt.
             Usa APP_URL de .env por defecto, o --domain para sobreescribir.
    """
    base_url = _get_base_url(domain)
    
    content = f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api\n\nSitemap: {base_url}/sitemap.xml"
    
    output_path = Path("public/robots.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    
    typer.echo(f"✅ Robots.txt generated at {output_path} (base URL: {base_url})")

if __name__ == "__main__":
    app()
