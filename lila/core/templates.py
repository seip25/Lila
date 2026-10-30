"""Lila Framework v2.0.x Template Engine.

Jinja2 environment with:
- Dual template resolution (project resources first, bundled framework templates second)
- SPA partial rendering (the client swaps the ``[data-lila-outlet]`` content)
- Global CSRF token/meta cookie on every HTML render
- Asset helpers with optional ``lila optimize`` manifest + cache busting
"""

import os
import re
import json
import html
import traceback
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader, ChoiceLoader

from lila.core.config import ENV_CONFIG, get_base_path, get_data_path, is_debug
from lila.core.request import Request
from lila.core.responses import HTMLResponse
from lila.core.translate import Translate
from lila.core.csrf import CSRF, CSRF_COOKIE_NAME, CSRF_MAX_AGE
from lila.core.logger import Logger
from lila.core.oauth import OAuth


def _get_template_loaders() -> ChoiceLoader:
    loaders = []
    project_html = get_base_path("resources", "html")
    if os.path.exists(project_html):
        loaders.append(FileSystemLoader(project_html))

    pkg_html = os.path.join(os.path.dirname(__file__), "..", "resources", "html")
    if os.path.exists(pkg_html):
        loaders.append(FileSystemLoader(os.path.abspath(pkg_html)))

    if not loaders:
        loaders.append(FileSystemLoader(os.getcwd()))

    return ChoiceLoader(loaders)


jinja_env = Environment(
    loader=_get_template_loaders(),
    auto_reload=is_debug(),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Asset helpers (supports the ``lila optimize`` manifest)
# ──────────────────────────────────────────────────────────────────────────────
_PUBLIC_CACHE: Dict[str, str] = {}
_MANIFEST_CACHE: Dict[str, str] = {}
_MANIFEST_LOADED = False


def _load_asset_manifest() -> Dict[str, str]:
    global _MANIFEST_LOADED, _MANIFEST_CACHE
    if _MANIFEST_LOADED:
        return _MANIFEST_CACHE
    _MANIFEST_LOADED = True
    candidates = [
        get_data_path("app", "cache", "assets_manifest.json"),
        get_data_path("app", "cache", "manifest_cache.py"),
    ]
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            if candidate.endswith(".json"):
                with open(candidate, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            else:
                import importlib.util

                spec = importlib.util.spec_from_file_location("lila_asset_manifest", candidate)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                data = getattr(module, "ASSET_MANIFEST", {})
            if isinstance(data, dict):
                _MANIFEST_CACHE = {str(k): str(v) for k, v in data.items()}
                break
        except Exception:
            continue
    return _MANIFEST_CACHE


def _asset_version(path: str) -> str:
    try:
        return str(int(os.path.getmtime(path)))
    except Exception:
        return ""


def public(asset_path: str) -> str:
    """Resolves a public static asset URL with manifest mapping and instant cache."""
    clean = asset_path.lstrip("/\\")
    if clean in _PUBLIC_CACHE:
        return _PUBLIC_CACHE[clean]

    manifest = _load_asset_manifest()
    mapped = manifest.get(clean)
    if mapped and os.path.exists(get_base_path("public", mapped)):
        clean = mapped

    app_url = str(ENV_CONFIG.get("APP_URL", "") or "").rstrip("/")
    resolved = f"/{clean}"
    if app_url and not is_debug():
        resolved = f"{app_url}{resolved}"

    # Cache-busting: use the file mtime. In production this is stable per deploy.
    versioned = get_base_path("public", clean)
    version = _asset_version(versioned)
    if version:
        resolved = f"{resolved}?v={version}"

    _PUBLIC_CACHE[clean] = resolved
    return resolved


def asset(asset_path: str) -> str:
    """Returns a <link> or <script> tag for an asset."""
    clean = asset_path.lstrip("/\\")
    url = public(clean)
    lower = clean.lower()
    if lower.endswith(".css"):
        return f'<link rel="stylesheet" href="{url}" />'
    if lower.endswith(".js"):
        return f'<script src="{url}"></script>'
    return url


DEFAULT_LAYOUT: str = "lila/base.jinja"


def set_default_layout(layout_name: str) -> None:
    global DEFAULT_LAYOUT
    DEFAULT_LAYOUT = layout_name


jinja_env.globals["public"] = public
jinja_env.globals["asset"] = asset
jinja_env.globals["oauth_buttons"] = OAuth.render_buttons
jinja_env.globals["lang"] = lambda: str(ENV_CONFIG.get("LANG_DEFAULT", "en"))
jinja_env.globals["translate"] = Translate.get_dict()
jinja_env.globals["t"] = Translate.t


def get_base_context(
    request: Request,
    lang_default: Optional[str] = None,
    files_translate: Optional[list] = None,
) -> Dict[str, Any]:
    """Generates the standard template context."""
    app_url = str(ENV_CONFIG.get("APP_URL", "") or "").rstrip("/")
    if not app_url:
        app_url = str(request.base_url).rstrip("/") if hasattr(request, "base_url") else "http://127.0.0.1:8000"

    current_lang = (lang_default or Translate.lang(request))[:2].lower()
    trans_dict = Translate.get_dict(current_lang)

    return {
        "request": request,
        "title": ENV_CONFIG.get("TITLE_PROJECT", "Lila Application"),
        "description": ENV_CONFIG.get("DESCRIPTION_PROJECT", ENV_CONFIG.get("DESCRIPTION_DEFAULT", "")),
        "keywords": ENV_CONFIG.get("KEYWORDS_DEFAULT", ""),
        "author": ENV_CONFIG.get("AUTHOR_DEFAULT", ""),
        "version": ENV_CONFIG.get("VERSION_PROJECT", "2.0"),
        "lang": current_lang,
        "translate": trans_dict,
        "t": lambda key, default=None: Translate.t(key, lang=current_lang, default=default),
        "app_url": app_url,
        "debug": is_debug(),
        "debug_html": is_debug(),
        "layout": DEFAULT_LAYOUT,
        "csrf_token": "",
    }


def _resolve_template_name(target: str, extension: str) -> List[str]:
    """Returns candidate names, accepting legacy ``.html``/``.jinja`` spellings."""
    names = []
    if target.endswith(f".{extension}"):
        names.append(target)
    elif target.endswith(".html"):
        names.append(target)
        names.append(f"{target[:-5]}.{extension}")
    elif target.endswith(".jinja"):
        names.append(target)
    else:
        names.append(f"{target}.{extension}")
    # De-duplicate while preserving order.
    return list(dict.fromkeys(names))


def render(
    request: Request,
    template_name: Optional[str] = None,
    context: Optional[dict] = None,
    extension: str = "jinja",
    csrf: bool = False,
    status_code: int = 200,
    template: Optional[str] = None,
    layout: Optional[str] = None,
    headers: Optional[dict] = None,
    lang_default: Optional[str] = None,
    files_translate: Optional[list] = None,
) -> HTMLResponse:
    """Renders an HTML template with unified context, CSRF and SPA partial support."""
    target_template = template_name or template or "index"
    ctx = get_base_context(request, lang_default=lang_default, files_translate=files_translate)
    if layout:
        ctx["layout"] = layout
    if context:
        ctx.update(context)

    seo_meta = ctx.get("seo") or getattr(request.state, "seo", None)
    if seo_meta:
        ctx["seo"] = seo_meta
        for key in ("title", "description", "keywords", "author"):
            if seo_meta.get(key):
                ctx[key] = seo_meta[key]
    else:
        ctx.setdefault("seo", {})

    # CSRF token is available on every page so SPA navigations keep working.
    csrf_token = CSRF.generate(request)
    ctx["csrf_token"] = csrf_token
    ctx["csrf_input"] = (
        f'<input type="hidden" name="_csrf" id="csrf" value="{html.escape(csrf_token)}" />'
    )

    try:
        tmpl = None
        last_error = None
        for candidate in _resolve_template_name(target_template, extension):
            try:
                tmpl = jinja_env.get_template(candidate)
                break
            except Exception as exc:
                last_error = exc
        if tmpl is None:
            raise last_error or RuntimeError(f"Template not found: {target_template}")

        body = tmpl.render(ctx)

        response_headers = dict(headers or {})
        if request.headers.get("x-lila-partial") == "1":
            response_headers["X-Lila-Partial"] = "1"

        response = HTMLResponse(content=body, status_code=status_code, headers=response_headers)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=CSRF.sign(csrf_token),
            max_age=CSRF_MAX_AGE,
            httponly=True,
            secure=str(ENV_CONFIG.get("APP_URL", "") or "").lower().startswith("https://"),
            samesite="lax",
            path="/",
        )
        return response

    except Exception as e:
        Logger.error(f"Template render error in '{target_template}': {e}", exception=e)
        if is_debug():
            tb = traceback.format_exc()
            return HTMLResponse(
                f'<div style="padding: 2rem; font-family: sans-serif; background: #fff1f2; color: #9f1239;">'
                f'<h2 style="margin-top: 0;">Template Render Error: {html.escape(str(target_template))}</h2>'
                f'<pre style="background: #ffffff; padding: 1rem; border-radius: 8px; overflow-x: auto;">{html.escape(tb)}</pre>'
                f"</div>",
                status_code=500,
            )
        return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)


def render_markdown(
    request: Request,
    markdown_path: str,
    context: Optional[dict] = None,
    css_files: Optional[List[str]] = None,
    js_files: Optional[List[str]] = None,
) -> HTMLResponse:
    """Renders a markdown document wrapped in the markdown layout."""
    base_dir = os.path.realpath(get_base_path("resources", "markdown"))
    requested = markdown_path if str(markdown_path).endswith(".md") else f"{markdown_path}.md"
    full_path = os.path.realpath(os.path.join(base_dir, requested))

    # Prevent path traversal / absolute path reads.
    if not (full_path == base_dir or full_path.startswith(base_dir + os.sep)):
        return HTMLResponse("<h1>Invalid document path</h1>", status_code=400)
    if not os.path.isfile(full_path):
        return HTMLResponse("<h1>Document Not Found</h1>", status_code=404)

    with open(full_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    try:
        import markdown  # optional extra: pip install "lila-framework[markdown]"

        html_content = markdown.markdown(md_text, extensions=["extra", "codehilite"])
    except ImportError:
        html_content = (
            '<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">'
            "Markdown support requires <code>pip install \"lila-framework[markdown]\"</code>."
            "</div><pre>" + html.escape(md_text) + "</pre>"
        )

    ctx = get_base_context(request)
    if context:
        ctx.update(context)
    ctx["content"] = html_content
    ctx["css_files"] = css_files or []
    ctx["js_files"] = js_files or []

    try:
        tmpl = jinja_env.get_template("markdown/layout.jinja")
        return HTMLResponse(tmpl.render(ctx))
    except Exception:
        return HTMLResponse(html_content)


# v1-compatible alias (documented in older guides).
renderMarkdown = render_markdown
