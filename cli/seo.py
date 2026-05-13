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

@app.command()
def sitemap(domain: str = "http://localhost:8000"):
    """
    English: Generates a sitemap.xml based on the application routes.
    Español: Genera un sitemap.xml basado en las rutas de la aplicación.
    """
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
        
        full_url = f"{domain.rstrip('/')}{path}"
        xml_content += f"  <url>\n    <loc>{full_url}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.8</priority>\n  </url>\n"
    
    xml_content += "</urlset>"
    
    output_path = Path("public/sitemap.xml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_content, encoding="utf-8")
    
    typer.echo(f"✅ Sitemap generated at {output_path}")

@app.command()
def robots(domain: str = "http://localhost:8000"):
    """
    English: Generates a robots.txt file.
    Español: Genera un archivo robots.txt.
    """
    content = f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api\n\nSitemap: {domain.rstrip('/')}/sitemap.xml"
    
    output_path = Path("public/robots.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    
    typer.echo(f"✅ Robots.txt generated at {output_path}")

if __name__ == "__main__":
    app()
