from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT, MINIFY_HTML
from core.translate import Translate
from core.request import Request
from core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
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

def is_frontend_request(request: Request) -> bool:
    """
    Check if the current request is a frontend SPA request.
    """
    return request.query_params.get('source') == 'frontend' or request.headers.get('x-lila-spa') == 'true'

def render_json_response(body: str, context: dict) -> JSONResponse:
    """
    Render a JSON response for SPA navigation.
    """
    seo_data = context.get("seo", {})
    response_data = {
        "meta": {
            "title": seo_data.get("title", context.get("title", TITLE_PROJECT)),
            "description": seo_data.get("description", context.get("description", DESCRIPTION_DEFAULT)),
            "keywords": seo_data.get("keywords", context.get("keywords", KEYWORDS_DEFAULT)),
            "author": context.get("author", AUTHOR_DEFAULT)
        },
        "lang": context.get("lang", LANG_DEFAULT),
        "scripts": context.get("scripts_array", []),
        "css": context.get("styles_array", []),
        "fonts": [],
        "body": body,
        "props": context.get("props_array", {}),
        "translations": context.get("translate", {})
    }
    return JSONResponse(response_data)

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
            elif clean_path == 'js/spa.js':
                return "http://localhost:5173/public/resources/js/spa.js"
            return f"http://localhost:5173/public/{clean_path}"
            
    if not DEBUG or force_static:
        _load_assets_manifest()
        if ASSETS_MANIFEST and clean_path in ASSETS_MANIFEST:
            path_val = ASSETS_MANIFEST[clean_path]
            if path_val.startswith('/'):
                return path_val
            return f"/{path_val}"
            
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
        global _VITE_PROJECT_EXISTS
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
        if not _VITE_PROJECT_EXISTS:
            return """<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
            <style type="text/tailwindcss">

@variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme {
  --color-primary: var(--primary, #1a73e8);
  --color-primary-dark: var(--primary-dark, #1557b0);
  --color-secondary: var(--secondary, #e91e63);
  --color-secondary-dark: var(--secondary-dark, #c2185b);
  --color-accent: var(--accent, #ffc107);
  --color-surface: var(--surface, #ffffff);
  --color-surface-dark: var(--surface-dark, #1e293b);
  --color-bg-body: var(--bg-body, #f8fafc);
  --color-bg-body-dark: var(--bg-body-dark, #0f172a);
  
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  
  --shadow-material: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --shadow-material-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

:root {
  --primary: #1a73e8;
  --primary-dark: #1557b0;
  --secondary: #e91e63;
  --secondary-dark: #c2185b;
  --accent: #ffc107;
  --surface: #ffffff;
  --surface-dark: #1e293b;
  --bg-body: #f8fafc;
  --bg-body-dark: #0f172a;
}


@layer components {
  .btn-primary {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-primary hover:bg-primary-dark text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-secondary {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-secondary hover:bg-secondary-dark text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-error {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-red-500 dark:bg-red-400 hover:bg-red-600 dark:hover:bg-red-500 text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-warning {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-yellow-500 dark:bg-yellow-400 hover:bg-yellow-600 dark:hover:bg-yellow-500 text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-success {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-green-500 dark:bg-green-400 hover:bg-green-600 dark:hover:bg-green-500 text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-info {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-blue-500 dark:bg-blue-400 hover:bg-blue-600 dark:hover:bg-blue-500 text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-white dark:bg-surface border border-gray-300 dark:border-gray-800 hover:bg-primary text-gray-600 dark:text-primary-dark hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline-primary {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-transparent border border-primary hover:bg-primary text-primary hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline-error {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-transparent border border-red-500 dark:border-red-400 hover:bg-red-600 dark:hover:bg-red-500 text-red-500 dark:text-red-400 hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline-warning {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-transparent border border-yellow-500 dark:border-yellow-400 hover:bg-yellow-600 dark:hover:bg-yellow-500 text-yellow-500 dark:text-yellow-400 hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline-success {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-transparent border border-green-500 dark:border-green-400 hover:bg-green-600 dark:hover:bg-green-500 text-green-500 dark:text-green-400 hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .btn-outline-info {
    @apply relative overflow-hidden px-6 py-3 rounded-full bg-transparent border border-blue-500 dark:border-blue-400 hover:bg-blue-600 dark:hover:bg-blue-500 text-blue-500 dark:text-blue-400 hover:text-white font-bold shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-2;
  }

  .card {
    @apply bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-material hover:shadow-material-lg transition-all duration-300;
  }

  .text-lila {
    @apply text-4xl md:text-6xl font-black tracking-tight bg-gradient-to-r from-primary via-purple-600 to-secondary bg-clip-text text-transparent mb-4;
  }

  .input-lila {
    @apply w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500;
  }

  .link-lila {
    @apply text-primary hover:text-primary-dark dark:text-blue-400 dark:hover:text-blue-300 font-semibold transition-colors duration-200 underline decoration-2 decoration-transparent hover:decoration-current;
  }

}

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

        if is_frontend_request(request):
            full_context["layout"] = "lila/empty.html"
            full_context["request"] = request
            template_obj = jinja_env.get_template(f"{template}.{extension}")
            body = template_obj.render(full_context)

            return render_json_response(body, full_context)

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
