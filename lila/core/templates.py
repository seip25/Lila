from app.config import (
    VERSION_PROJECT,
    TITLE_PROJECT,
    DEBUG,
    DESCRIPTION_DEFAULT,
    KEYWORDS_DEFAULT,
    AUTHOR_DEFAULT,
    LANG_DEFAULT,
    APP_URL,
    HOST,
    PORT,
    PATH_TEMPLATES_HTML,
    PATH_TEMPLATES_MARKDOWN,
)
from lila.core.translate import Translate
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse
from lila.core.csrf import CSRF
from lila.core.logger import Logger
from lila.core.cache import Cache
from typing import Any, Optional, List, Dict
import os
import json
import traceback
import sys

PROJECT_ROOT = os.getcwd()

_JINJA_ENV = None
_PUBLIC_CACHE: Dict[tuple, str] = {}
_ASSET_CACHE: Dict[tuple, str] = {}
_VITE_MANIFEST: Dict = {}
_vite_manifest_loaded: bool = False
ASSETS_MANIFEST: Dict = {}
_assets_manifest_loaded: bool = False


def _load_vite_manifest():
    """Loads the Vite build assets manifest dynamically from public/.vite/manifest.json."""
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
    """Loads the static assets manifest via Python cache module or JSON file fallback."""
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


def public(path: str, force_static: bool = False) -> str:
    """Resolves the public URL for a given static asset with RAM caching."""
    cache_key = (path, force_static)
    if cache_key in _PUBLIC_CACHE:
        return _PUBLIC_CACHE[cache_key]

    clean_path = path.lstrip("/")
    resolved_path = f"/{clean_path}"

    _load_assets_manifest()
    if ASSETS_MANIFEST and clean_path in ASSETS_MANIFEST:
        path_val = ASSETS_MANIFEST[clean_path]
        resolved_path = path_val if path_val.startswith("/") else f"/{path_val}"

    if not DEBUG and APP_URL and not force_static:
        res = f"{APP_URL.rstrip('/')}{resolved_path}"
    else:
        res = resolved_path

    _PUBLIC_CACHE[cache_key] = res
    return res


def asset(path: str, force_static: bool = False) -> str:
    """Generates the HTML tag for a CSS or JS asset, or a URL for other assets."""
    cache_key = (path, force_static)
    if cache_key in _ASSET_CACHE:
        return _ASSET_CACHE[cache_key]

    clean_path = path.lstrip("/")
    resolved = public(clean_path, force_static=force_static)
    if clean_path.endswith(".css"):
        tag = f'<link rel="stylesheet" href="{resolved}" />'
    elif clean_path.endswith(".js"):
        tag = f'<script src="{resolved}"></script>'
    else:
        tag = resolved

    _ASSET_CACHE[cache_key] = tag
    return tag


def get_flashes(request: Request) -> List[dict]:
    """Retrieves queued flash messages and clears them from request state."""
    flashes = []
    if hasattr(request, "state"):
        if hasattr(request.state, "_flash_messages"):
            flashes.extend(request.state._flash_messages)
            request.state._flash_messages = []
        if hasattr(request.state, "_new_flashes"):
            flashes.extend(request.state._new_flashes)
            request.state._new_flashes = []
    return flashes


def get_jinja_env():
    """Lazy-loads and configures Jinja2 environment on first access."""
    global _JINJA_ENV
    if _JINJA_ENV is not None:
        return _JINJA_ENV

    try:
        from jinja2 import Environment, FileSystemLoader, BytecodeCache
    except ImportError:
        raise ImportError(
            "Jinja2 is required for template rendering. Install it via: pip install 'lila-framework[ssr]'"
        )

    class LilaBytecodeCache(BytecodeCache):
        _MEM_CACHE: Dict[str, Any] = {}

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

    bccache = LilaBytecodeCache() if not DEBUG else None
    loader = FileSystemLoader(PATH_TEMPLATES_HTML)

    _JINJA_ENV = Environment(
        loader=loader,
        auto_reload=DEBUG,
        autoescape=True,
        cache_size=-1 if not DEBUG else 400,
        bytecode_cache=bccache,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    _JINJA_ENV.globals["public"] = public
    _JINJA_ENV.globals["asset"] = asset
    _JINJA_ENV.globals["get_flashes"] = get_flashes
    _JINJA_ENV.globals["hot_reload"] = lambda: ""
    return _JINJA_ENV


def get_base_context(request: Request, files_translate: List[str] = None, lang_default: str = None) -> dict:
    """Constructs standard template context dictionary."""
    if files_translate is None:
        files_translate = []

    current_lang = lang_default if lang_default else Translate.lang(request)
    seo_data = getattr(request.state, "seo", {}) if hasattr(request, "state") else {}

    return {
        "title": seo_data.get("title", TITLE_PROJECT),
        "description": seo_data.get("description", DESCRIPTION_DEFAULT),
        "keywords": seo_data.get("keywords", KEYWORDS_DEFAULT),
        "seo": seo_data,
        "version": VERSION_PROJECT,
        "lang": current_lang,
        "author": seo_data.get("author", AUTHOR_DEFAULT),
        "app_url": APP_URL or f"http://{HOST}:{PORT}",
        "debug": DEBUG,
        "get_flashes": lambda: get_flashes(request),
    }


def render(
    request: Request,
    template: str,
    context: dict = None,
    files_translate: List[str] = None,
    lang_default: str = None,
    extension: str = "jinja",
    csrf: bool = False,
):
    """Renders an HTML template using Jinja2 with context and error handling."""
    if context is None:
        context = {}
    if files_translate is None:
        files_translate = []

    try:
        env = get_jinja_env()
        full_context = get_base_context(request, files_translate, lang_default)
        full_context.update(context)

        csrf_token = None
        if csrf:
            csrf_token = CSRF.generate(request)
            full_context["csrf_input"] = f"<input type='hidden' name='csrf' id='csrf' value='{csrf_token}' />"
            full_context["csrf_token"] = csrf_token

        template_obj = env.get_template(f"{template}.{extension}")
        body = template_obj.render(full_context)
        response = HTMLResponse(content=body)

        if csrf and csrf_token:
            CSRF.set_cookie(response, csrf_token)

        return response
    except Exception as e:
        return handle_render_error(template, e)


def handle_render_error(template: str, e: Exception):
    """Logs and formats template rendering errors."""
    exc_type, _, _ = sys.exc_info()
    tb_str = traceback.format_exc()
    error_name = exc_type.__name__ if exc_type else "Error"

    Logger.error(f"Render error in {template}: {str(e)}")
    print(f"\n{'='*20} TEMPLATE ERROR: {template} {'='*20}\n{tb_str}")

    if DEBUG:
        return HTMLResponse(content=f"<h1>{error_name}</h1><pre>{tb_str}</pre>", status_code=500)
    return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)


def renderMarkdown(
    request: Request,
    file: str,
    css_files: List[str] = None,
    js_files: List[str] = None,
    lang_default: str = None,
):
    """Converts a markdown file to HTML and renders layout."""
    try:
        import markdown
    except ImportError:
        raise ImportError("Markdown rendering requires markdown package. Install with: pip install markdown")

    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = markdown.markdown(md_content)
    context = get_base_context(request, lang_default=lang_default)
    context.update({
        "request": request,
        "content": html_content,
        "css_files": css_files or [],
        "js_files": js_files or [],
    })

    env = get_jinja_env()
    template_obj = env.get_template("layout.jinja")
    body = template_obj.render(context)
    return HTMLResponse(content=body)