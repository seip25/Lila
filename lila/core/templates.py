"""Lila Framework v2.0.0 Template Engine.
Jinja2 environment with:
- Dual template resolution (app resources & built-in framework templates)
- Full support for SPA Partial requests (X-Lila-Partial)
- Helpers for OAuth buttons, CSRF, Tailwind assets, and translations
"""

import os
import sys
import json
import traceback
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from starlette.templating import Jinja2Templates

from lila.core.config import ENV_CONFIG, get_base_path
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse
from lila.core.translate import Translate
from lila.core.csrf import CSRF, CSRF_COOKIE_NAME
from lila.core.logger import Logger
from lila.core.oauth import OAuth


def _get_template_loaders() -> ChoiceLoader:
    loaders = []
    # 1. Project app resources
    project_html = get_base_path("resources", "html")
    if os.path.exists(project_html):
        loaders.append(FileSystemLoader(project_html))

    # 2. Package builtin resources
    pkg_html = os.path.join(os.path.dirname(__file__), "..", "resources", "html")
    if os.path.exists(pkg_html):
        loaders.append(FileSystemLoader(os.path.abspath(pkg_html)))

    # Fallback to current working directory
    if not loaders:
        loaders.append(FileSystemLoader(os.getcwd()))

    return ChoiceLoader(loaders)


jinja_env = Environment(
    loader=_get_template_loaders(),
    auto_reload=bool(ENV_CONFIG.get("DEBUG", True)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Global Jinja Template Helpers
# ──────────────────────────────────────────────────────────────────────────────
_PUBLIC_CACHE: Dict[str, str] = {}


def public(asset_path: str) -> str:
    """Resolves public static asset URL with instant memory cache."""
    clean = asset_path.lstrip("/\\")
    if clean in _PUBLIC_CACHE:
        return _PUBLIC_CACHE[clean]

    app_url = str(ENV_CONFIG.get("APP_URL", "")).rstrip("/")
    resolved = f"/{clean}"
    if app_url and not ENV_CONFIG.get("DEBUG", True):
        res = f"{app_url}{resolved}"
    else:
        res = resolved

    _PUBLIC_CACHE[clean] = res
    return res


def asset(asset_path: str) -> str:
    """Returns <link> or <script> HTML tag for asset."""
    clean = asset_path.lstrip("/\\")
    url = public(clean)
    if clean.endswith(".css"):
        return f'<link rel="stylesheet" href="{url}" />'
    elif clean.endswith(".js"):
        return f'<script src="{url}"></script>'
    return url


jinja_env.globals["public"] = public
jinja_env.globals["asset"] = asset
jinja_env.globals["oauth_buttons"] = OAuth.render_buttons
jinja_env.globals["lang"] = lambda: str(ENV_CONFIG.get("LANG_DEFAULT", "es"))


def get_base_context(request: Request) -> Dict[str, Any]:
    """Generates standard template context."""
    app_url = str(ENV_CONFIG.get("APP_URL", "")).rstrip("/")
    if not app_url:
        app_url = str(request.base_url).rstrip("/") if hasattr(request, "base_url") else "http://127.0.0.1:8000"

    current_lang = Translate.lang(request)

    return {
        "request": request,
        "title": ENV_CONFIG.get("TITLE_PROJECT", "Lila Application"),
        "description": ENV_CONFIG.get("DESCRIPTION_DEFAULT", ""),
        "keywords": ENV_CONFIG.get("KEYWORDS_DEFAULT", ""),
        "version": ENV_CONFIG.get("VERSION_PROJECT", "2.0.0"),
        "lang": current_lang,
        "app_url": app_url,
        "debug": bool(ENV_CONFIG.get("DEBUG", True)),
    }


def render(
    request: Request,
    template_name: Optional[str] = None,
    context: Optional[dict] = None,
    extension: str = "jinja",
    csrf: bool = False,
    status_code: int = 200,
    template: Optional[str] = None,
) -> HTMLResponse:
    """Renders HTML template with unified context, CSRF handling, and SPA partial support."""
    target_template = template_name or template or "index"
    ctx = get_base_context(request)
    if context:
        ctx.update(context)

    csrf_token = None
    if csrf:
        csrf_token = CSRF.generate(request)
        ctx["csrf_token"] = csrf_token
        ctx["csrf_input"] = f'<input type="hidden" name="_csrf" id="csrf" value="{csrf_token}" />'

    # Normalize template name
    if not target_template.endswith(f".{extension}"):
        full_name = f"{target_template}.{extension}"
    else:
        full_name = target_template

    try:
        tmpl = jinja_env.get_template(full_name)
        body = tmpl.render(ctx)

        # Check for SPA Partial request
        headers = {}
        if request.headers.get("x-lila-partial") == "1":
            headers["X-Lila-Partial"] = "1"

        response = HTMLResponse(content=body, status_code=status_code, headers=headers)
        if csrf and csrf_token:
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=CSRF.sign(csrf_token),
                httponly=True,
                samesite="lax",
            )
        return response

    except Exception as e:
        Logger.error(f"Template render error in '{target_template}': {e}", exception=e)
        if bool(ENV_CONFIG.get("DEBUG", True)):
            tb = traceback.format_exc()
            return HTMLResponse(
                f'<div style="padding: 2rem; font-family: sans-serif; background: #fff1f2; color: #9f1239;">'
                f'<h2 style="margin-top: 0;">Template Render Error: {target_template}</h2>'
                f'<pre style="background: #ffffff; padding: 1rem; border-radius: 8px; overflow-x: auto;">{tb}</pre>'
                f'</div>',
                status_code=500,
            )
        return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)


def render_markdown(
    request: Request,
    markdown_path: str,
    context: Optional[dict] = None,
) -> HTMLResponse:
    """Renders a markdown document wrapped in layout template."""
    import markdown
    full_path = get_base_path("resources", "markdown", f"{markdown_path}.md")
    if not os.path.exists(full_path):
        return HTMLResponse("<h1>Document Not Found</h1>", status_code=404)

    with open(full_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_content = markdown.markdown(md_text, extensions=["extra", "codehilite"])
    ctx = get_base_context(request)
    if context:
        ctx.update(context)
    ctx["content"] = html_content

    try:
        tmpl = jinja_env.get_template("markdown/layout.jinja")
        return HTMLResponse(tmpl.render(ctx))
    except Exception:
        return HTMLResponse(html_content)
