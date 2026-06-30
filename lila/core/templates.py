from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT, MINIFY_HTML, APP_URL, HOST, PORT
from lila.core.translate import Translate
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from lila.core.logger import Logger
import markdown
import os
import traceback
import sys
import json

PROJECT_ROOT = os.getcwd()

if MINIFY_HTML:
    loader = minify_loader(
        FileSystemLoader(PATH_TEMPLATES_HTML),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    )
else:
    loader = FileSystemLoader(PATH_TEMPLATES_HTML)

jinja_env = Environment(
    loader=loader,
    auto_reload=DEBUG,
    autoescape=True,
)

MANIFEST_BUILD: dict[str, str] = {}

_VITE_PROJECT_EXISTS: bool = None
STYLES_DEFAULT_TAILWIND: str = None

def hot_reload() -> str:
    """
    Returns Vite hot reload scripts if DEBUG is True.
    """
    global _VITE_PROJECT_EXISTS
    if DEBUG:
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
            
        if _VITE_PROJECT_EXISTS:
            return """
        <script type="module" src="http://localhost:5173/public/@vite/client"></script>
        """
    return ""


jinja_env.globals['hot_reload'] = hot_reload

_VITE_MANIFEST: dict = {}
_vite_manifest_loaded: bool = False
ASSETS_MANIFEST: dict = {}
_assets_manifest_loaded: bool = False

def _load_vite_manifest():
    """
    English: Loads the Vite build assets manifest dynamically from public/.vite/manifest.json.
    Español: Carga dinámicamente el manifiesto de recursos de construcción de Vite desde public/.vite/manifest.json.
    """
    global _VITE_MANIFEST, _vite_manifest_loaded
    if not _vite_manifest_loaded:
        manifest_path = os.path.join(PROJECT_ROOT, "public", ".vite", "manifest.json")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(PROJECT_ROOT, "public", "manifest.json")
            
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    _VITE_MANIFEST = json.load(f)
            except Exception as e:
                Logger.warning(f"Error loading Vite manifest: {e}")
        _vite_manifest_loaded = True

def _load_assets_manifest():
    """
    English: Loads the classic static assets manifest.
    Español: Carga el manifiesto clásico de recursos estáticos.
    """
    global ASSETS_MANIFEST, _assets_manifest_loaded
    if not _assets_manifest_loaded:
        manifest_path = os.path.join(PROJECT_ROOT, "app", "assets_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    ASSETS_MANIFEST = json.load(f)
            except Exception as e:
                Logger.warning(f"Error loading assets_manifest.json: {e}")
        _assets_manifest_loaded = True

def public(path: str, force_static: bool = False) -> str:
    """
    English: Resolves the public URL for a given static asset, automatically supporting Vite development and production modes.
    Español: Resuelve la URL pública para un recurso estático dado, soportando automáticamente los modos de desarrollo y producción de Vite.
    """
    clean_path = path.lstrip('/')
    
    if DEBUG and not force_static:
        global _VITE_PROJECT_EXISTS
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
        if _VITE_PROJECT_EXISTS and (clean_path.endswith(".css") or clean_path.endswith(".js")):
            if clean_path == 'css/tailwind.css':
                return "http://localhost:5173/public/resources/css/tailwind.css"
            elif clean_path == 'js/utils.js':
                return "http://localhost:5173/public/resources/js/utils.js"
            return f"http://localhost:5173/public/{clean_path}"
            
    if not DEBUG or force_static:
        _load_assets_manifest()
        resolved_path = f"/{clean_path}"
        if ASSETS_MANIFEST and clean_path in ASSETS_MANIFEST:
            path_val = ASSETS_MANIFEST[clean_path]
            resolved_path = path_val if path_val.startswith('/') else f"/{path_val}"
        
        if not DEBUG and APP_URL:
            return f"{APP_URL.rstrip('/')}{resolved_path}"
        return resolved_path
            
    return f"/{clean_path}"

jinja_env.globals['public'] = public

def asset(path: str, force_static: bool = False) -> str:
    """
    English: Returns the complete HTML tag for a CSS or JS asset (supporting Vite dev/prod), or a simple URL string for other assets.
    If in DEBUG mode and Vite package-lock.json does not exist, it automatically falls back to Tailwind Play CDN to prevent styling breakage.
    
    Español: Retorna la etiqueta HTML completa para un recurso CSS o JS (soportando Vite dev/prod), o una cadena de URL simple para otros recursos.
    Si está en modo DEBUG y no existe el archivo package-lock.json de Vite, recurre automáticamente a Tailwind Play CDN para evitar la rotura del diseño.
    """
    clean_path = path.lstrip('/')
    resolved = public(clean_path, force_static=force_static)
    
    if DEBUG and not force_static and clean_path == 'css/tailwind.css':
        global _VITE_PROJECT_EXISTS, STYLES_DEFAULT_TAILWIND
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
        if not _VITE_PROJECT_EXISTS:
            if STYLES_DEFAULT_TAILWIND is None:
                css_path = os.path.join(PROJECT_ROOT, "resources", "css", "tailwind.css")
                if os.path.exists(css_path):
                    try:
                        with open(css_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        if lines and "@import" in lines[0] and "tailwindcss" in lines[0]:
                            lines = lines[1:]
                        STYLES_DEFAULT_TAILWIND = "".join(lines)
                    except Exception as e:
                        STYLES_DEFAULT_TAILWIND = f"/* Error reading tailwind.css: {e} */"
                else:
                    STYLES_DEFAULT_TAILWIND = "/* resources/css/tailwind.css not found */"
            
            return f"""<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
            <style type="text/tailwindcss">
{STYLES_DEFAULT_TAILWIND}
            </style>
            """
            
    if clean_path.endswith('.css'):
        if DEBUG and resolved.startswith('http://localhost:5173'):
            return f'<script type="module" src="{resolved}"></script>'
        return f'<link rel="stylesheet" href="{resolved}" />'
        
    if clean_path.endswith('.js'):
        if DEBUG and resolved.startswith('http://localhost:5173'):
            return f'<script type="module" src="{resolved}"></script>'
        return f'<script src="{resolved}"></script>'
        
    return resolved

jinja_env.globals['asset'] = asset

templates = Jinja2Templates(env=jinja_env)
markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)
def get_base_context(request: Request, files_translate: list[str] = None, lang_default: str = None) -> dict:
    """
    Constructs the standard context dictionary for all template renders.
    """
    if files_translate is None:
        files_translate = []

    current_lang = lang_default if lang_default else Translate.lang(request)
    translations = Translate.get_translations("translations", request, lang_default=lang_default)

    for file_name in files_translate:
        translations.update(Translate.get_translations(file_name, request, lang_default=lang_default))

    seo_data = getattr(request.state, "seo", {})

    return {
        "title": seo_data.get("title", TITLE_PROJECT),
        "description": seo_data.get("description", DESCRIPTION_DEFAULT),
        "keywords": seo_data.get("keywords", KEYWORDS_DEFAULT),
        "seo": seo_data,
        "version": VERSION_PROJECT,
        "lang": current_lang,
        "translate": translations,
        "author": AUTHOR_DEFAULT,
        "app_url": APP_URL or f"http://{HOST}:{PORT}",
        "debug": DEBUG,
    }


def render(request: Request, template: str, context: dict = None, files_translate: list[str] = None, lang_default: str = None,extension:str="html"):
    """
    Renders an HTML template with unified context and error handling.
    """
    if context is None:
        context = {}
    if files_translate is None:
        files_translate = []
    try:
        full_context = get_base_context(request, files_translate, lang_default)
        full_context.update(context)
        template_obj = jinja_env.get_template(f"{template}.{extension}")
        body = template_obj.render(full_context)
        return HTMLResponse(content=body)
    except Exception as e:
        return handle_render_error(template, e)

def handle_render_error(template: str, e: Exception):
    """
    Logs and formats template rendering errors based on the debug environment.
    """
    exc_type, _, exc_tb = sys.exc_info()
    tb_str = traceback.format_exc()
    error_name = exc_type.__name__ if exc_type else "Error"
    
    Logger.error(f"Render error in {template}: {str(e)}")
    print(f"\n{'='*20} TEMPLATE ERROR: {template} {'='*20}\n{tb_str}")

    if DEBUG:
        return HTMLResponse(content=f"<h1>{error_name}</h1><pre>{tb_str}</pre>", status_code=500)
    return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

def renderMarkdown(request: Request, file: str, css_files: list = None, js_files: list = None, lang_default: str = None, translate_files: list[str] = None):
    """
    Converts a markdown file to HTML and wraps it in a layout template.
    """
    if css_files is None:
        css_files = []
    if js_files is None:
        js_files = []
    if translate_files is None:
        translate_files = []
    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    context = get_base_context(request, translate_files, lang_default)
     
    import re
    def replace_translate(match):
        key = match.group(1)
        return str(context["translate"].get(key, match.group(0)))
    
    md_content = re.sub(r'\{\{\s*translate\["([^"]+)"\]\s*\}\}', replace_translate, md_content)

    html_content = markdown.markdown(md_content)
    context.update({
        "request": request,
        "content": html_content,
        "css_files": css_files,
        "js_files": js_files,
    })

    return markdown_templates.TemplateResponse(request, "layout.html", context)
