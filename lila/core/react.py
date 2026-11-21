"""React integration (Vite) for Lila.

Two complementary models, both with server-side ``<title>``, meta tags,
Open Graph, canonical and JSON-LD (the same keywords as ``render()``):

1. Pages per Python route (server props, like Inertia)::

       from lila.core.react import react_render

       @router.get("/users/{id:int}")
       async def user(request: Request, id: int):
           user = await User.get_by_id_async(id)
           return react_render(request, "Users/Show", {"user": user},
                               title=user["name"], description="Profile",
                               jsonld={"@context": "https://schema.org", "@type": "Person",
                                       "name": user["name"]})

   ``resources/react/pages/Users/Show.jsx`` receives ``user`` as a prop. Links
   built with ``<Link href>`` (``resources/react/lila``) fetch the next page as
   JSON (``X-Lila-React: 1``) and swap component, props and ``<head>`` without
   a full reload.

2. A client-side SPA (React Router) mounted under a path::

       router.spa("/app", meta={
           "*": {"title": "App"},
           "login": {"title": "Sign in", "robots": "noindex"},
           "users/:id": lambda request, params: {"title": f"User {params['id']}"},
       })

   Every URL below ``/app`` returns the shell with the meta of the best
   matching pattern; ``useLilaHead()`` refreshes it on client navigation.
"""

from __future__ import annotations

import html
import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from markupsafe import Markup

from lila.core.config import ENV_CONFIG, is_debug
from lila.core.csrf import CSRF, CSRF_COOKIE_NAME, CSRF_MAX_AGE
from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse, orjson_dumps
from lila.core.vite import ViteBridge, ViteManifestMissing, default_entry
from lila.core import desktop as desktop_mod

REACT_HEADER = "x-lila-react"
HEAD_HEADER = "x-lila-head"
VERSION_HEADER = "x-lila-version"
SHELL_TEMPLATE = "lila/react.jinja"

_SCRIPT_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", " ": "\\u2028", " ": "\\u2029"}

_SEO_KEYS = (
    "title", "description", "keywords", "author", "image", "icon", "canonical", "robots",
    "og_type", "jsonld", "meta", "styles", "scripts", "head", "body_class",
)


def script_json(data: Any) -> Markup:
    """JSON safe to embed in ``<script type="application/json">``."""
    raw = orjson_dumps(data).decode("utf-8")
    for char, repl in _SCRIPT_ESCAPES.items():
        raw = raw.replace(char, repl)
    return Markup(raw)


def _head_payload(page: Dict[str, Any], raw_jsonld: Any, lang: str) -> Dict[str, Any]:
    """The ``<head>`` values the client applies after a JSON navigation."""
    jsonld = raw_jsonld if isinstance(raw_jsonld, (list, tuple)) else ([raw_jsonld] if raw_jsonld else [])
    return {
        "title": page.get("full_title") or page.get("title") or "",
        "description": page.get("description") or "",
        "keywords": page.get("keywords") or "",
        "robots": page.get("robots") or "",
        "canonical": page.get("canonical") or "",
        "image": page.get("image") or "",
        "og_type": page.get("og_type") or "website",
        "url": page.get("url") or "",
        "meta": page.get("meta") or [],
        "jsonld": [item for item in jsonld if item],
        "lang": lang,
    }


def _set_csrf_cookie(response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=CSRF.sign(token),
        max_age=CSRF_MAX_AGE,
        httponly=True,
        secure=str(ENV_CONFIG.get("APP_URL", "") or "").lower().startswith("https://"),
        samesite="lax",
        path="/",
    )


def _wants_json(request: Request) -> bool:
    return request.headers.get(REACT_HEADER) == "1"


def _shell_error(exc: Exception) -> HTMLResponse:
    Logger.error(f"[Lila] React page could not load its assets: {exc}")
    if is_debug():
        message = html.escape(str(exc))
        return HTMLResponse(
            '<div style="font-family:system-ui,sans-serif;padding:2rem;background:#fff7ed;color:#9a3412">'
            f"<h2 style=\"margin-top:0\">React assets are not available</h2><p>{message}</p>"
            "<pre>lila react dev     # Vite dev server + Lila (HMR)\nlila react build   # production build</pre></div>",
            status_code=500,
        )
    return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)


def react_render(
    request: Request,
    component: Optional[str] = None,
    props: Optional[Dict[str, Any]] = None,
    *,
    entry: Any = None,
    root_id: str = "app",
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None,
    template: str = SHELL_TEMPLATE,
    tailwind: bool = False,
    skeleton: Optional[str] = None,
    spa: Optional[Dict[str, Any]] = None,
    lang_default: Optional[str] = None,
    translations: Any = None,
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
):
    """Renders a React page (``resources/react/pages/<component>.jsx``).

    ``props`` must be JSON serializable (dicts from ``BaseModel`` reads are).
    Never put secrets in props: they are visible in the page source.
    ``entry`` is the Vite entry (default ``resources/react/main.tsx``, or
    ``main.jsx`` in ``--js`` projects),
    ``tailwind=True`` also includes Lila's Tailwind runtime/CSS (normally
    Tailwind comes from Vite), ``skeleton`` is raw HTML shown until React mounts.
    """
    from lila.core.templates import _DEV_RELOAD_SCRIPT, _build_page, get_base_context, jinja_env

    ctx = get_base_context(request, lang_default=lang_default)
    for key in ("title", "description", "keywords", "author"):
        ctx[f"__base_{key}"] = ctx.get(key)
    if context:
        ctx.update(context)
    seo_meta = ctx.get("seo") or getattr(request.state, "seo", None)
    ctx["seo"] = dict(seo_meta or {})
    explicit = {
        "title": title, "description": description, "keywords": keywords, "author": author,
        "image": image, "icon": icon, "canonical": canonical, "robots": robots, "og_type": og_type,
        "jsonld": jsonld, "meta": meta, "styles": styles, "scripts": scripts, "head": head,
        "body_class": body_class,
    }
    page_meta = _build_page(request, ctx, explicit)
    raw_jsonld = jsonld if jsonld is not None else ctx["seo"].get("jsonld")
    csrf_token = CSRF.generate(request)
    lang = ctx.get("lang") or "en"

    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    page = {
        "component": component,
        "props": props or {},
        "url": path,
        "version": ViteBridge.version(),
        "csrf": csrf_token,
        **desktop_mod.client_info(),
    }
    if spa:
        page["spa"] = spa
    if translations:
        # useT() in React: True = whole locale, a list = only those keys.
        trans = ctx.get("translate") or {}
        if translations is True:
            page["t"] = dict(trans)
        else:
            page["t"] = {key: trans.get(key, key) for key in translations}
    # Also in the HTML payload: history (back/forward) restores it client-side.
    page["head"] = _head_payload(page_meta, raw_jsonld, lang)
    response_headers = dict(headers or {})
    response_headers.setdefault("Vary", "X-Lila-React, X-Lila-Head")

    if _wants_json(request) or request.headers.get(HEAD_HEADER) == "1":
        client_version = request.headers.get(VERSION_HEADER)
        if _wants_json(request) and client_version and client_version != page["version"]:
            # New deploy: the client reloads to pick up the new bundles.
            return JSONResponse(
                {"reload": True, "url": path}, status_code=409, headers={"X-Lila-Location": path}
            )
        if request.headers.get(HEAD_HEADER) == "1" and not _wants_json(request):
            page = {"head": page["head"], "props": page["props"], "url": path}
        response = JSONResponse(page, status_code=status_code, headers=response_headers)
        _set_csrf_cookie(response, csrf_token)
        return response

    try:
        vite_tags = ViteBridge.tags(entry or default_entry(spa=bool(spa)))
    except ViteManifestMissing as exc:
        return _shell_error(exc)

    ctx.update({
        "page_meta": page_meta,
        "csrf_token": csrf_token,
        "lila_skip_tailwind": not tailwind,
        "vite_tags": Markup(vite_tags),
        "react_page": script_json(page),
        "react_root_id": re.sub(r"[^A-Za-z0-9_-]", "", root_id) or "app",
        "react_skeleton": Markup(skeleton or ""),
        # Reloads the page when the Python server restarts (Vite handles JS/CSS).
        "react_dev_reload": Markup(_DEV_RELOAD_SCRIPT) if is_debug() else Markup(""),
    })
    if page_meta.get("title"):
        ctx["title"] = page_meta["title"]
    for key in ("title", "description", "keywords", "author"):
        ctx.pop(f"__base_{key}", None)

    try:
        body = jinja_env.get_template(template).render(ctx)
    except Exception as exc:  # pragma: no cover - template errors are logged
        Logger.error(f"React shell render error: {exc}", exception=exc)
        return _shell_error(exc)
    if is_debug():
        response_headers.setdefault("Cache-Control", "no-store")
    response = HTMLResponse(body, status_code=status_code, headers=response_headers)
    _set_csrf_cookie(response, csrf_token)
    return response


# ── SPA meta tree ────────────────────────────────────────────────────────────

class _MetaRoute:
    __slots__ = ("pattern", "regex", "score", "value")

    def __init__(self, pattern: str, value: Any):
        self.pattern = pattern
        self.value = value
        segments = [s for s in pattern.strip("/").split("/") if s]
        parts, score = [], 0
        for seg in segments:
            if seg == "*" or seg == "**":
                parts.append(r"(?:/(?P<wildcard>.*))?")
                score += 1
                break
            if seg.startswith(":"):
                name = re.sub(r"\W", "_", seg[1:].rstrip("?")) or "param"
                optional = seg.endswith("?")
                parts.append(rf"(?:/(?P<{name}>[^/]+))?" if optional else rf"/(?P<{name}>[^/]+)")
                score += 10
            else:
                parts.append("/" + re.escape(seg))
                score += 100
        self.regex = re.compile("^" + "".join(parts) + "/?$")
        self.score = score


def compile_meta(meta: Optional[Dict[str, Any]]) -> Tuple[Any, List[_MetaRoute]]:
    meta = dict(meta or {})
    default = meta.pop("*", None)
    routes = [_MetaRoute(key, value) for key, value in meta.items()]
    routes.sort(key=lambda r: (-r.score, -len(r.pattern)))
    return default, routes


async def _resolve(value: Any, request: Request, params: Dict[str, str]) -> Dict[str, Any]:
    if callable(value):
        try:
            arity = len(inspect.signature(value).parameters)
        except (TypeError, ValueError):
            arity = 2
        value = value(request, params) if arity >= 2 else value(request)
        if inspect.isawaitable(value):
            value = await value
    return dict(value or {})


def _meta_list(key: str, value: Any) -> List[Any]:
    if isinstance(value, dict) and key == "meta":
        return [
            {"property" if str(k).startswith(("og:", "article:", "fb:")) else "name": k, "content": str(v)}
            for k, v in value.items()
        ]
    return list(value) if isinstance(value, (list, tuple)) else [value]


def merge_meta(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Later values win; ``meta``/``styles``/``scripts``/``jsonld`` accumulate."""
    merged = dict(base)
    for key, value in extra.items():
        if key in ("meta", "styles", "scripts", "jsonld") and merged.get(key) is not None and value is not None:
            merged[key] = _meta_list(key, merged[key]) + _meta_list(key, value)
        elif key == "props" and isinstance(value, dict) and isinstance(merged.get("props"), dict):
            merged["props"] = {**merged["props"], **value}
        else:
            merged[key] = value
    return merged


async def resolve_spa_meta(request: Request, relative: str, default: Any, routes: List[_MetaRoute],
                           base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    path = "/" + relative.strip("/")
    merged = dict(base or {})
    if default is not None:
        merged = merge_meta(merged, await _resolve(default, request, {}))
    for route in routes:
        match = route.regex.match(path)
        if match:
            params = {k: v for k, v in match.groupdict().items() if v is not None}
            merged = merge_meta(merged, await _resolve(route.value, request, params))
            break
    return merged


_STATIC_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")


def make_spa_handler(mount: str, meta: Optional[Dict[str, Any]] = None, entry: Any = None,
                     root_id: str = "root", tailwind: bool = False, skeleton: Optional[str] = None,
                     **defaults: Any) -> Callable:
    """Endpoint serving the SPA shell for ``mount`` and every path below it."""
    mount = "/" + mount.strip("/") if mount.strip("/") else ""
    default, routes = compile_meta(meta)

    async def spa_handler(request: Request):
        full = request.url.path
        relative = full[len(mount):] if mount and full.startswith(mount) else full
        if _STATIC_EXT_RE.search(relative):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        accept = request.headers.get("accept", "*/*")
        if "text/html" not in accept and "*/*" not in accept and not (
            request.headers.get(HEAD_HEADER) == "1" or _wants_json(request)
        ):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        merged = await resolve_spa_meta(request, relative, default, routes, defaults)
        status_code = int(merged.pop("status", 200) or 200)
        props = merged.pop("props", None) or {}
        kwargs = {key: merged.get(key) for key in _SEO_KEYS if merged.get(key) is not None}
        return react_render(
            request, None, props, entry=entry, root_id=root_id, tailwind=tailwind, skeleton=skeleton,
            status_code=status_code, spa={"mount": mount or "/"}, **kwargs,
        )

    spa_handler.__name__ = f"spa_{(mount or 'root').strip('/').replace('/', '_') or 'root'}"
    return spa_handler
