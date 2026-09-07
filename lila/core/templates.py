from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, BytecodeCache
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT, MINIFY_HTML, APP_URL, HOST, PORT
from lila.core.translate import Translate
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from lila.core.csrf import CSRF
from lila.core.logger import Logger
from lila.core.cache import Cache
from typing import Any
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

class LilaBytecodeCache(BytecodeCache):
    """
    High-performance Dual-Tier Jinja Bytecode Cache (`Performance First`).
    1. L1 Memory Cache (`_MEM_CACHE`): Keeps compiled Python AST code objects directly in RAM (`0 ms` overhead, zero deserialization).
    2. L2 Distributed Cache (`Cache.set/get`): Stores marshaled bytecode in Redis or memory fallback across worker restarts.
    """
    _MEM_CACHE: dict[str, Any] = {}

    def load_bytecode(self, bucket) -> None:
        code = self._MEM_CACHE.get(bucket.key)
        if code is not None:
            bucket.code = code
            return

        cached_bytes = Cache.get(f"jinja_bc:{bucket.key}")
        if cached_bytes is not None and isinstance(cached_bytes, bytes):
            try:
                bucket.bytecode_from_string(cached_bytes)
                if bucket.code is not None:
                    self._MEM_CACHE[bucket.key] = bucket.code
            except Exception:
                pass

    def dump_bytecode(self, bucket) -> None:
        if bucket.code is not None: 
            self._MEM_CACHE[bucket.key] = bucket.code 
            try:
                data = bucket.bytecode_to_string()
                Cache.set(f"jinja_bc:{bucket.key}", data, ttl=86400)
            except Exception:
                pass

if not DEBUG:
    bccache = LilaBytecodeCache()
else:
    bccache = None

jinja_env = Environment(
    loader=loader,
    auto_reload=DEBUG,
    autoescape=True,
    cache_size=-1 if not DEBUG else 400,
    bytecode_cache=bccache,
    trim_blocks=True,
    lstrip_blocks=True,
)



MANIFEST_BUILD: dict[str, str] = {}

_VITE_PROJECT_EXISTS: bool = None 

def hot_reload() -> str:
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
    English: Loads the static assets manifest via fast Python import or JSON fallback.
    Español: Carga el manifiesto de recursos estáticos via import de Python o fallback a JSON.
    """
    global ASSETS_MANIFEST, _assets_manifest_loaded
    if not _assets_manifest_loaded:
        try:
            from app.cache.manifest_cache import ASSET_MANIFEST as cache_manifest
            ASSETS_MANIFEST = cache_manifest
        except ImportError:
            manifest_path = os.path.join(PROJECT_ROOT, "app", "assets_manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        ASSETS_MANIFEST = json.load(f)
                except Exception as e:
                    Logger.warning(f"Error loading assets_manifest.json: {e}")
        _assets_manifest_loaded = True

_PUBLIC_CACHE: dict[tuple[str, bool], str] = {}

def public(path: str, force_static: bool = False) -> str:
    """
    Resolves the public URL for a given static asset.
    Cached in RAM for O(1) instant resolution.
    """
    cache_key = (path, force_static)
    if cache_key in _PUBLIC_CACHE:
        return _PUBLIC_CACHE[cache_key]

    clean_path = path.lstrip('/')
    resolved_path = f"/{clean_path}"
    
    _load_assets_manifest()
    if ASSETS_MANIFEST and clean_path in ASSETS_MANIFEST:
        path_val = ASSETS_MANIFEST[clean_path]
        resolved_path = path_val if path_val.startswith('/') else f"/{path_val}"
    
    if not DEBUG and APP_URL and not force_static:
        res = f"{APP_URL.rstrip('/')}{resolved_path}"
    else:
        res = resolved_path

    _PUBLIC_CACHE[cache_key] = res
    return res

jinja_env.globals['public'] = public

_ASSET_CACHE: dict[tuple[str, bool], str] = {}

def asset(path: str, force_static: bool = False) -> str:
    """
    Returns the complete HTML tag for a CSS or JS asset, or a simple URL string for other assets.
    Cached in memory for O(1) instant lookup.
    """
    cache_key = (path, force_static)
    if cache_key in _ASSET_CACHE:
        return _ASSET_CACHE[cache_key]

    clean_path = path.lstrip('/')
    
    resolved = public(clean_path, force_static=force_static)
    if clean_path.endswith('.css'):
        tag = f'<link rel="stylesheet" href="{resolved}" />'
    elif clean_path.endswith('.js'):
        tag = f'<script src="{resolved}"></script>'
    else:
        tag = resolved

    _ASSET_CACHE[cache_key] = tag
    return tag

jinja_env.globals['asset'] = asset

def get_flashes(request: Request) -> list[dict]:
    """
    English: Returns queued flash messages and clears them so they aren't shown again.
    Español: Retorna los mensajes flash en cola y los limpia para que no se muestren de nuevo.
    """
    flashes = []
    if hasattr(request.state, "_flash_messages"):
        flashes.extend(request.state._flash_messages)
        request.state._flash_messages = []
    if hasattr(request.state, "_new_flashes"):
        flashes.extend(request.state._new_flashes)
        request.state._new_flashes = []
    return flashes


jinja_env.globals['get_flashes'] = get_flashes

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
        "author": seo_data.get("author", AUTHOR_DEFAULT),
        "app_url": APP_URL or f"http://{HOST}:{PORT}",
        "debug": DEBUG,
        "debug_html": getattr(request.app, "debug_html", False),
        "get_flashes": lambda: get_flashes(request),
    }


def render(request: Request, template: str, context: dict = None, files_translate: list[str] = None, lang_default: str = None, extension: str = "jinja", csrf: bool = False):
    """
    English: Renders an HTML template with unified context and error handling.
    When csrf=True, generates a CSRF token and injects it into the template context as 'csrf_token'.
    The signed token is also set as a cookie on the response.

    Español: Renderiza una plantilla HTML con contexto unificado y manejo de errores.
    Cuando csrf=True, genera un token CSRF y lo inyecta en el contexto de la plantilla como 'csrf_token'.
    El token firmado tambien se establece como cookie en la respuesta.
    """
    if context is None:
        context = {}
    if files_translate is None:
        files_translate = []
    try:
        full_context = get_base_context(request, files_translate, lang_default)
        full_context.update(context)
        if csrf:
            csrfToken = CSRF.generate(request)
            full_context["csrf_input"] = f"<input type='hidden' name='csrf' id='csrf' value='{csrfToken}' />"

        template_obj = jinja_env.get_template(f"{template}.{extension}")
        body = template_obj.render(full_context)
        response = HTMLResponse(content=body)
        if csrf and csrfToken:
            CSRF.set_cookie(response, csrfToken)
        return response
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

    return markdown_templates.TemplateResponse(request, "layout.jinja", context)

 