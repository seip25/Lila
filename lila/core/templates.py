"""Lila Framework v2.0.x Template Engine.

Jinja2 environment with:
- Automatic layouts: a page template only contains its HTML. ``render()``
  wraps it in ``layout`` (``lila/base.jinja`` by default) and fills title,
  description, Open Graph, JSON-LD, icon, styles and scripts from keyword
  arguments, ``@seo`` or ``SEO_CONFIG``. Templates using ``{% extends %}``
  keep working unchanged.
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

from jinja2 import Environment, FileSystemLoader, ChoiceLoader, BaseLoader, pass_context
from markupsafe import Markup

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


# ──────────────────────────────────────────────────────────────────────────────
# Auto-layout pages
# ──────────────────────────────────────────────────────────────────────────────
PAGE_PREFIX = "@page:"

# Top-level blocks a page may still declare; they are moved next to the
# generated ``content`` block (line numbers are preserved for error messages).
_PAGE_BLOCK_RE = re.compile(
    r"{%-?\s*block\s+(head|scripts|title|styles)\s*-?%}.*?{%-?\s*endblock(?:\s+\1)?\s*-?%}",
    re.DOTALL,
)
_FULL_TEMPLATE_RE = re.compile(r"{%-?\s*extends\s|<html[\s>]|<!doctype", re.IGNORECASE)


def _wrap_page_source(source: str) -> str:
    """Turns a plain HTML page into ``{% extends layout %}`` + blocks.

    The result is compiled once and cached by Jinja (auto-reloaded in debug).
    """
    if _FULL_TEMPLATE_RE.search(source):
        return source
    extra_blocks: List[str] = []

    def _extract(match: "re.Match[str]") -> str:
        extra_blocks.append(match.group(0))
        return "\n" * match.group(0).count("\n")

    body = _PAGE_BLOCK_RE.sub(_extract, source)
    return (
        "{% extends layout %}{% block content %}"
        + body
        + "{% endblock %}"
        + "".join(extra_blocks)
    )


class LilaPageLoader(BaseLoader):
    """Delegates to the normal loaders; ``@page:<name>`` gets auto-wrapped.

    Only the template passed to ``render()`` is wrapped, never includes,
    macros or layouts, so components keep rendering as plain fragments.
    """

    def __init__(self, inner: BaseLoader):
        self.inner = inner

    def get_source(self, environment, template):
        if template.startswith(PAGE_PREFIX):
            source, filename, uptodate = self.inner.get_source(environment, template[len(PAGE_PREFIX):])
            return _wrap_page_source(source), filename, uptodate
        return self.inner.get_source(environment, template)

    def list_templates(self):
        return self.inner.list_templates()


def _bytecode_cache():
    """Compiled templates on disk (production only): faster cold starts and
    less CPU per new worker. Disabled in debug so edits are picked up."""
    if is_debug() or str(ENV_CONFIG.get("JINJA_BYTECODE_CACHE", "true")).lower() in ("0", "false", "no"):
        return None
    try:
        from jinja2 import FileSystemBytecodeCache

        class _LazyDirCache(FileSystemBytecodeCache):
            # The folder is created on the first write, never at import time.
            def dump_bytecode(self, bucket):
                try:
                    os.makedirs(self.directory, exist_ok=True)
                    super().dump_bytecode(bucket)
                except OSError:
                    pass

        return _LazyDirCache(get_data_path("app", "cache", "jinja"))
    except Exception:
        return None


jinja_env = Environment(
    bytecode_cache=_bytecode_cache(),
    loader=LilaPageLoader(_get_template_loaders()),
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

_DEV_RELOAD_SCRIPT = """<script>
(function () {
  if (window.__lilaDevReload) return;
  window.__lilaDevReload = true;
  if (!window.EventSource) return;
  var host = window.location.hostname;
  if (host !== "localhost" && host !== "127.0.0.1" && host !== "::1") return;
  var initial = null, es = null, timer = null;
  function close() {
    if (es) { try { es.close(); } catch (e) {} es = null; }
    if (timer) { clearTimeout(timer); timer = null; }
  }
  function connect() {
    close();
    try {
      es = new EventSource("/_lila/dev-reload");
      es.onmessage = function (event) {
        try {
          var data = JSON.parse(event.data);
          if (data.type === "template") { close(); location.reload(); return; }
          if (data.type === "connected" && data.bootId) {
            if (initial === null) initial = data.bootId;
            else if (initial !== data.bootId) { close(); location.reload(); }
          }
        } catch (e) {}
      };
      es.onerror = function () { close(); timer = setTimeout(connect, 400); };
    } catch (e) { timer = setTimeout(connect, 600); }
  }
  window.addEventListener("beforeunload", close);
  connect();
})();
</script>"""



def clear_asset_cache() -> None:
    """Drops cached asset URLs/manifests (used by the dev template watcher)."""
    global _MANIFEST_LOADED
    _PUBLIC_CACHE.clear()
    _MANIFEST_CACHE.clear()
    _TAILWIND_CSS.clear()
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


_TAILWIND_CSS: Dict[str, str] = {}


def tailwind_css() -> str:
    """URL of the compiled Tailwind CSS (``lila css build``) or ``""``.

    ``TAILWIND_MODE``: ``auto`` (default: compiled file in production, browser
    runtime in debug so new classes appear instantly), ``build`` (always the
    compiled file when it exists) or ``play`` (always the runtime).
    """
    if "url" in _TAILWIND_CSS:
        return _TAILWIND_CSS["url"]
    mode = str(ENV_CONFIG.get("TAILWIND_MODE", "auto") or "auto").lower()
    url = ""
    if mode != "play" and (mode == "build" or not is_debug()):
        if os.path.isfile(get_base_path("public", "css", "lila.css")):
            url = public("css/lila.css")
    _TAILWIND_CSS["url"] = url
    return url


jinja_env.globals["public"] = public
jinja_env.globals["asset"] = asset
jinja_env.globals["tailwind_css"] = tailwind_css


@pass_context
def _oauth_buttons_ctx(ctx, *args, **kwargs):
    if len(args) < 4 and not kwargs.get("label_prefix"):
        request = ctx.get("request")
        lang = ctx.get("lang") or Translate.lang(request)
        kwargs["label_prefix"] = Translate.t("continue_with", lang=lang, default="Continue with")
    return OAuth.render_buttons(*args, **kwargs)


@pass_context
def _t_ctx(ctx, key, *args, **kwargs):
    if args and "default" not in kwargs:
        kwargs["default"] = args[0]
    kwargs.setdefault("request", ctx.get("request"))
    kwargs.setdefault("lang", ctx.get("lang") or Translate.lang(ctx.get("request")))
    return Translate.t(key, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# UI component helpers: {{ datatable(...) }} / {{ carousel(...) }}
# ──────────────────────────────────────────────────────────────────────────────
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


def _component_id(prefix: str, given: Optional[str]) -> str:
    if given:
        return _SAFE_ID_RE.sub("-", str(given))[:64]
    import secrets

    return f"{prefix}-{secrets.token_hex(4)}"


def _json_for_script(data: Any) -> str:
    """JSON safe to embed inside <script type="application/json">."""
    raw = json.dumps(data, ensure_ascii=False, default=str)
    for char, repl in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        raw = raw.replace(char, repl)
    return raw


def _rows(data: Any) -> List[Any]:
    rows = []
    for row in data or []:
        if hasattr(row, "to_dict"):
            row = row.to_dict()
        elif hasattr(row, "model_dump"):
            row = row.model_dump(mode="json")
        rows.append(row)
    return rows


def datatable(
    data: Any = None,
    columns: Any = None,
    *,
    url: Optional[str] = None,
    data_key: Optional[str] = None,
    id: Optional[str] = None,
    rows_per_page: int = 10,
    search: bool = True,
    pagination: bool = True,
    summary_fields: Optional[List[str]] = None,
    id_key: str = "id",
    breakpoint: int = 768,
    edit: Optional[str] = None,
    delete: Optional[str] = None,
    exclude: Any = ("password", "token", "hash"),
    css_class: str = "",
) -> Markup:
    """Renders a ResponsiveDataTable from Jinja with an automatic unique id.

    ``{{ datatable(users, ["id", "name", ("email", "E-mail")]) }}`` embeds the
    rows; ``{{ datatable(url="/api/users", columns=[...]) }}`` loads them with
    ``Http()``. ``edit``/``delete`` are names of global JS functions
    ``(event, item) => ...``. Sensitive keys in ``exclude`` are never embedded.
    """
    table_id = _component_id("lila-dt", id)
    blocked = set(exclude or ())
    rows = [
        {k: v for k, v in row.items() if k not in blocked} if isinstance(row, dict) else row
        for row in _rows(data)
    ]

    cols: List[Dict[str, str]] = []
    if columns:
        for col in columns:
            if isinstance(col, dict):
                key = str(col.get("key", ""))
                cols.append({"key": key, "title": str(col.get("title", key))})
            elif isinstance(col, (list, tuple)):
                cols.append({"key": str(col[0]), "title": str(col[1] if len(col) > 1 else col[0])})
            else:
                cols.append({"key": str(col), "title": str(col).replace("_", " ").title()})
    elif rows and isinstance(rows[0], dict):
        cols = [{"key": k, "title": k.replace("_", " ").title()} for k in rows[0].keys()]
    cols = [c for c in cols if c["key"] and c["key"] not in blocked]

    config: Dict[str, Any] = {
        "columns": cols,
        "rowsPerPage": int(rows_per_page),
        "search": bool(search),
        "pagination": bool(pagination),
        "idKey": id_key,
        "breakpoint": int(breakpoint),
        "summaryFields": summary_fields or ([cols[0]["key"]] if cols else [id_key]),
    }
    if url:
        config["url"] = url
        if data_key:
            config["dataKey"] = data_key
    else:
        config["data"] = rows
    if edit:
        config["edit"] = str(edit)
    if delete:
        config["delete"] = str(delete)

    return Markup(
        f'<div id="{table_id}" class="{html.escape(css_class)}" data-lila-datatable></div>'
        f'<script type="application/json" id="{table_id}-config">{_json_for_script(config)}</script>'
    )


def carousel(
    slides: Any,
    *,
    id: Optional[str] = None,
    autoplay: int = 0,
    loop: bool = True,
    arrows: bool = True,
    indicators: bool = True,
    item_class: str = "basis-full",
    height: str = "h-64 md:h-96",
    css_class: str = "",
) -> Markup:
    """Renders a Tailwind carousel (auto-initialized by lila-client.js).

    ``slides`` items may be dicts ``{"image", "alt", "title", "text", "href"}``,
    plain strings (escaped text) or ``Markup`` (trusted HTML). Use
    ``item_class="basis-full md:basis-1/3"`` to show several cards per view.
    """
    cid = _component_id("lila-carousel", id)
    esc = html.escape
    parts = []
    for slide in slides or []:
        if isinstance(slide, Markup):
            inner = str(slide)
        elif isinstance(slide, dict):
            image = slide.get("image")
            src = _asset_url(image) if image else ""
            img = (
                f'<img src="{esc(src)}" alt="{esc(str(slide.get("alt") or slide.get("title") or ""))}" '
                f'loading="lazy" class="absolute inset-0 w-full h-full object-cover" />'
                if src else ""
            )
            caption = ""
            if slide.get("title") or slide.get("text"):
                caption = (
                    '<div class="absolute inset-x-0 bottom-0 p-6 pb-10 bg-gradient-to-t from-slate-950/80 to-transparent text-white">'
                    + (f'<h3 class="text-xl font-black">{esc(str(slide["title"]))}</h3>' if slide.get("title") else "")
                    + (f'<p class="text-sm opacity-90 mt-1">{esc(str(slide["text"]))}</p>' if slide.get("text") else "")
                    + "</div>"
                )
            inner = f'<div class="relative w-full h-full bg-slate-200 dark:bg-slate-800">{img}{caption}</div>'
            if slide.get("href"):
                inner = f'<a href="{esc(str(slide["href"]))}" class="block w-full h-full">{inner}</a>'
        else:
            inner = f'<div class="w-full h-full flex items-center justify-center p-6">{esc(str(slide))}</div>'
        parts.append(f'<div class="carousel-item {esc(item_class)} {esc(height)} pr-0 overflow-hidden">{inner}</div>')

    arrow_cls = (
        "absolute top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white/80 dark:bg-slate-900/80 "
        "shadow-md backdrop-blur flex items-center justify-center text-xl font-bold cursor-pointer "
        "hover:bg-white dark:hover:bg-slate-800 disabled:opacity-40 transition"
    )
    controls = ""
    if arrows:
        controls += (
            f'<button type="button" class="carousel-prev {arrow_cls} left-3" aria-label="Previous">&lsaquo;</button>'
            f'<button type="button" class="carousel-next {arrow_cls} right-3" aria-label="Next">&rsaquo;</button>'
        )
    if indicators:
        controls += '<div class="carousel-indicators absolute bottom-3 inset-x-0 z-10 flex justify-center gap-2"></div>'

    return Markup(
        f'<div id="{cid}" class="carousel relative overflow-hidden rounded-2xl {esc(css_class)}" data-lila-carousel '
        f'data-autoplay="{int(autoplay)}" data-loop="{"true" if loop else "false"}">'
        f'<div class="carousel-track">{"".join(parts)}</div>{controls}</div>'
    )


from lila.core.ui import UI, render_form, render_pagination  # noqa: E402


@pass_context
def _form_ctx(ctx, model, *args, **kwargs):
    kwargs.setdefault("csrf_input", ctx.get("csrf_input") or "")
    kwargs.setdefault("trans", ctx.get("translate"))
    return render_form(model, *args, **kwargs)


@pass_context
def _pagination_ctx(ctx, page, **kwargs):
    kwargs.setdefault("request", ctx.get("request"))
    kwargs.setdefault("trans", ctx.get("translate"))
    return render_pagination(page, **kwargs)


@pass_context
def _can_ctx(ctx, permission):
    from lila.core.permissions import jinja_can

    return jinja_can(ctx.get("request"), permission)


@pass_context
def _has_role_ctx(ctx, role):
    from lila.core.permissions import jinja_has_role

    return jinja_has_role(ctx.get("request"), role)


from lila.core.images import responsive_image  # noqa: E402

jinja_env.globals["image"] = responsive_image
jinja_env.globals["can"] = _can_ctx
jinja_env.globals["has_role"] = _has_role_ctx
jinja_env.globals["form"] = _form_ctx
jinja_env.globals["pagination"] = _pagination_ctx
jinja_env.globals["ui"] = UI()  # replaced per render by a translated instance
jinja_env.globals["datatable"] = datatable
jinja_env.globals["carousel"] = carousel
jinja_env.globals["oauth_buttons"] = _oauth_buttons_ctx
jinja_env.globals["lang"] = lambda: str(ENV_CONFIG.get("LANG_DEFAULT", "en"))
jinja_env.globals["translate"] = Translate.get_dict()
jinja_env.globals["t"] = _t_ctx


def _inspect_app_routes(app_obj: Any) -> Dict[str, bool]:
    """Inspects routes recursively for common paths."""
    flags = {
        "has_docs": False,
        "has_admin": False,
        "has_auth": False,
        "debug_html": False,
    }
    if not app_obj:
        return flags

    routes = getattr(app_obj, "routes", None)
    if routes is None and hasattr(app_obj, "raw_routes"):
        routes = getattr(app_obj, "raw_routes", None)
    if not routes:
        return flags

    cached = getattr(app_obj, "_lila_route_flags", None)
    if cached is not None and cached[0] == len(routes):
        return dict(cached[1])

    visited = set()

    def check_routes(route_list, prefix=""):
        if not route_list:
            return
        for r in route_list:
            path = getattr(r, "path", "")
            full_path = f"{prefix.rstrip('/')}/{path.lstrip('/')}".rstrip('/')
            if not full_path:
                full_path = "/"

            key = (id(r), full_path)
            if key in visited:
                continue
            visited.add(key)

            if full_path in ("/docs", "/docs/"):
                flags["has_docs"] = True
            if full_path in ("/admin", "/admin/") or full_path.startswith("/admin/"):
                flags["has_admin"] = True
            if full_path in ("/login", "/login/", "/auth/login", "/auth/login/"):
                flags["has_auth"] = True
            if full_path in ("/debug", "/debug/"):
                flags["debug_html"] = True

            sub = getattr(r, "routes", None)
            if sub is None and hasattr(r, "app"):
                sub = getattr(r.app, "routes", None)
            if sub:
                check_routes(sub, prefix=full_path)

    check_routes(routes)
    try:
        setattr(app_obj, "_lila_route_flags", (len(routes), dict(flags)))
    except Exception:
        pass
    return flags


def get_base_context(
    request: Request,
    csrf: bool = True,
    lang_default: Optional[str] = None,
    files_translate: Optional[list] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generates the standard template context."""
    app_url = str(ENV_CONFIG.get("APP_URL", "") or "").rstrip("/")
    if not app_url:
        app_url = str(request.base_url).rstrip("/") if hasattr(request, "base_url") else "http://127.0.0.1:8000"

    current_lang = (lang_default or Translate.lang(request))[:2].lower()
    trans_dict = Translate.get_dict(current_lang)

    app_obj = getattr(request, "app", None)
    if not app_obj and hasattr(request, "scope") and isinstance(request.scope, dict):
        app_obj = request.scope.get("app")
    route_flags = _inspect_app_routes(app_obj)

    debug_val = bool(getattr(app_obj, "_is_debug", is_debug())) if app_obj else is_debug()
    debug_html_val = route_flags["debug_html"] if app_obj else debug_val

    return {
        "request": request,
        "title": ENV_CONFIG.get("TITLE_PROJECT", "Lila Application"),
        "description": ENV_CONFIG.get("DESCRIPTION_PROJECT", ENV_CONFIG.get("DESCRIPTION_DEFAULT", "")),
        "keywords": ENV_CONFIG.get("KEYWORDS_DEFAULT", ""),
        "author": ENV_CONFIG.get("AUTHOR_DEFAULT", ""),
        "version": ENV_CONFIG.get("VERSION_PROJECT", "2.0.0"),
        "lang": current_lang,
        "translate": trans_dict,
        "ui": UI(trans_dict),
        "t": lambda key, default=None: Translate.t(key, lang=current_lang, default=default),
        "app_url": app_url,
        "debug": debug_val,
        "debug_html": debug_html_val,
        "has_docs": route_flags["has_docs"],
        "has_admin": route_flags["has_admin"],
        "has_auth": route_flags["has_auth"],
        "layout": DEFAULT_LAYOUT,
        "layout_id": "default",
        "csrf_token": "",
        "page_meta": {},
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


_JSONLD_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", " ": "\\u2028", " ": "\\u2029"}


def _jsonld_markup(data: Any) -> Markup:
    """Serializes JSON-LD safely for a ``<script>`` tag (no ``</script>`` breakout)."""
    items = data if isinstance(data, (list, tuple)) else [data]
    tags = []
    for item in items:
        if not item:
            continue
        raw = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, default=str)
        for char, repl in _JSONLD_ESCAPES.items():
            raw = raw.replace(char, repl)
        tags.append(f'<script type="application/ld+json" data-lila-head>{raw}</script>')
    return Markup("".join(tags))


def _as_list(value: Any) -> List[Any]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _asset_url(value: str) -> str:
    text = str(value)
    if text.startswith(("http://", "https://", "//", "data:")):
        return text
    return public(text)


def _meta_items(meta: Any) -> List[Dict[str, str]]:
    """Accepts ``{"theme-color": "#fff", "og:locale": "es"}`` or a list of dicts."""
    if not meta:
        return []
    if isinstance(meta, dict):
        items = []
        for key, value in meta.items():
            attr = "property" if str(key).startswith(("og:", "article:", "fb:")) else "name"
            items.append({attr: str(key), "content": str(value)})
        return items
    return [dict(item) for item in meta if isinstance(item, dict)]


def _format_title(title: Optional[str], project: str) -> str:
    project = str(project or "")
    if not title:
        return project or "Lila"
    title = str(title)
    if not project or title == project or project in title:
        return title
    fmt = str(ENV_CONFIG.get("TITLE_TEMPLATE", "{title} - {project}") or "{title} - {project}")
    try:
        return fmt.format(title=title, project=project)
    except Exception:
        return f"{title} - {project}"


def _build_page(
    request: Request,
    ctx: Dict[str, Any],
    explicit: Dict[str, Any],
) -> Dict[str, Any]:
    """Merges ENV defaults < SEO_CONFIG/@seo < context < render() kwargs."""
    trans = ctx.get("translate") or {}
    seo_meta = dict(ctx.get("seo") or getattr(request.state, "seo", None) or {})
    project = str(ENV_CONFIG.get("TITLE_PROJECT", "") or "")

    def pick(key: str, default: Any = None) -> Any:
        value = explicit.get(key)
        if value is None and key in ("title", "description", "keywords", "author", "image", "icon"):
            # Context values (``context={"title": ...}``) override .env defaults.
            ctx_value = ctx.get(key)
            base_value = ctx.get(f"__base_{key}")
            if ctx_value not in (None, "") and ctx_value != base_value:
                value = ctx_value
        if value is None:
            value = seo_meta.get(key)
        return default if value is None else value

    def tr(value: Any) -> Any:
        # render(title="dashboard") -> translated "Dashboard"/"Panel".
        if isinstance(value, str) and value in trans:
            return trans[value]
        return value

    title = tr(pick("title"))
    description = tr(pick("description", ctx.get("description") or ""))
    image = pick("image")
    app_url = str(ctx.get("app_url") or "").rstrip("/")
    canonical = pick("canonical")
    if canonical is True:
        canonical = f"{app_url}{request.url.path}"
    if image and not str(image).startswith(("http://", "https://", "//")):
        image = f"{app_url}{_asset_url(image)}"

    icon = pick("icon", "favicon.ico")
    page = {
        "title": title,
        "full_title": _format_title(title, project),
        "description": description,
        "keywords": pick("keywords", ctx.get("keywords") or ""),
        "author": pick("author", ctx.get("author") or ""),
        "image": image,
        "icon": _asset_url(icon) if icon else "",
        "canonical": canonical,
        "robots": pick("robots"),
        "og_type": pick("og_type", "website"),
        "site_name": project,
        "url": f"{app_url}{request.url.path}",
        "meta": _meta_items(pick("meta")),
        "jsonld": _jsonld_markup(pick("jsonld")) if pick("jsonld") else Markup(""),
        "styles": [_asset_url(item) for item in _as_list(pick("styles"))],
        "scripts": [_asset_url(item) for item in _as_list(pick("scripts"))],
        "head": Markup(pick("head") or ""),
        "body_class": pick("body_class"),
    }
    return page


def render(
    request: Request,
    template_name: Optional[str] = None,
    context: Optional[dict] = None,
    extension: str = "jinja",
    csrf: bool = False,
    status_code: int = 200,
    template: Optional[str] = None,
    layout: Any = None,
    headers: Optional[dict] = None,
    lang_default: Optional[str] = None,
    files_translate: Optional[list] = None,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    keywords: Optional[str] = None,
    author: Optional[str] = None,
    image: Optional[str] = None,
    icon: Optional[str] = None,
    canonical: Any = None,
    robots: Optional[str] = None,
    og_type: Optional[str] = None,
    jsonld: Any = None,
    meta: Any = None,
    styles: Any = None,
    scripts: Any = None,
    head: Optional[str] = None,
    body_class: Optional[str] = None,
) -> HTMLResponse:
    """Renders an HTML page with automatic layout, SEO head, CSRF and SPA support.

    A page template only needs its HTML (no ``{% extends %}``/``{% block %}``)::

        return render(request, "dashboard", {"user": user},
                      title="dashboard", description="Your panel",
                      jsonld={"@context": "https://schema.org", "@type": "WebPage"},
                      scripts=["js/chart.js"])

    ``layout=None`` uses the default layout (``set_default_layout``), a string
    picks another layout and ``layout=False`` renders the template as-is.
    ``head`` is raw trusted HTML; every other value is escaped.
    """
    target_template = template_name or template or "index"
    ctx = get_base_context(request, csrf=csrf, lang_default=lang_default, files_translate=files_translate)
    for key in ("title", "description", "keywords", "author"):
        ctx[f"__base_{key}"] = ctx.get(key)
    use_layout = layout is not False
    if isinstance(layout, str) and layout:
        ctx["layout"] = layout
    if context:
        ctx.update(context)
    if not ctx.get("layout"):
        ctx["layout"] = DEFAULT_LAYOUT
    ctx["layout_id"] = "default" if ctx["layout"] == "lila/base.jinja" else str(ctx["layout"])

    seo_meta = ctx.get("seo") or getattr(request.state, "seo", None)
    ctx["seo"] = dict(seo_meta or {})

    page = _build_page(
        request,
        ctx,
        {
            "title": title,
            "description": description,
            "keywords": keywords,
            "author": author,
            "image": image,
            "icon": icon,
            "canonical": canonical,
            "robots": robots,
            "og_type": og_type,
            "jsonld": jsonld,
            "meta": meta,
            "styles": styles,
            "scripts": scripts,
            "head": head,
            "body_class": body_class,
        },
    )
    # ``page_meta`` (not ``page``): ``page`` is left free for pagination.
    ctx["page_meta"] = page
    # Backwards-compatible variables used by v2.0.0 templates.
    if page["title"]:
        ctx["title"] = page["title"]
    ctx["description"] = page["description"]
    ctx["keywords"] = page["keywords"]
    ctx["author"] = page["author"]
    for key in ("title", "description", "keywords", "author"):
        ctx.pop(f"__base_{key}", None)

    # CSRF token is available on every page so SPA navigations keep working.
    csrf_token = CSRF.generate(request)
    ctx["csrf_token"] = csrf_token
    ctx["csrf_input"] = Markup(
        f'<input type="hidden" name="_csrf" id="csrf" value="{html.escape(csrf_token)}" />'
    )

    try:
        tmpl = None
        last_error = None
        for candidate in _resolve_template_name(target_template, extension):
            try:
                tmpl = jinja_env.get_template(f"{PAGE_PREFIX}{candidate}" if use_layout else candidate)
                break
            except Exception as exc:
                last_error = exc
                if not _is_missing_template(exc):
                    raise
        if tmpl is None:
            raise last_error or RuntimeError(f"Template not found: {target_template}")

        body = tmpl.render(ctx)
        debug_enabled = bool(getattr(getattr(request, "app", None), "_is_debug", is_debug()))
        is_partial = request.headers.get("x-lila-partial") == "1"
        if debug_enabled and not is_partial and 'name="lila-debug"' not in body:
            marker = '<meta name="lila-debug" content="1">'
            if "</head>" in body:
                body = body.replace("</head>", marker + "</head>", 1)
            else:
                body = marker + body
        if debug_enabled and not is_partial and "__lilaDevReload" not in body:
            lower = body.lower()
            close_body = lower.rfind("</body>")
            if close_body >= 0:
                body = body[:close_body] + _DEV_RELOAD_SCRIPT + body[close_body:]
            else:
                body += _DEV_RELOAD_SCRIPT

        response_headers = dict(headers or {})
        if is_partial:
            response_headers["X-Lila-Partial"] = "1"
        if debug_enabled:
            response_headers.setdefault("Cache-Control", "no-store")

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
        debug_enabled = bool(getattr(getattr(request, "app", None), "_is_debug", is_debug()))
        if debug_enabled:
            tb = traceback.format_exc()
            return HTMLResponse(
                f'<div style="padding: 2rem; font-family: sans-serif; background: #fff1f2; color: #9f1239;">'
                f'<h2 style="margin-top: 0;">Template Render Error: {html.escape(str(target_template))}</h2>'
                f'<pre style="background: #ffffff; padding: 1rem; border-radius: 8px; overflow-x: auto;">{html.escape(tb)}</pre>'
                f"</div>",
                status_code=500,
            )
        return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)


def _is_missing_template(exc: Exception) -> bool:
    from jinja2 import TemplateNotFound

    # Only a missing page name falls through to the next candidate
    # (.html -> .jinja); syntax errors are raised immediately.
    return isinstance(exc, TemplateNotFound)


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
