"""Desktop/web route targeting.

A project can ship one codebase as a website and as a desktop app
(``lila desktop dev|build``) while keeping web-only features (payments,
uploads, webhooks, OAuth callbacks...) out of the desktop build:

* Per route: ``@router.get("/checkout", desktop=False)``; desktop-only routes:
  ``desktop="only"`` (removed from the website).
* Per router: ``Router(prefix="/billing", desktop=False)``.
* By pattern: ``DESKTOP_EXCLUDE=/payments*,/upload*,name:stripe_webhook`` in
  ``.env`` or ``lila desktop build --exclude "/payments*"`` (baked into the
  executable). ``--auto-exclude`` adds the routes :func:`suggest_exclusions`
  detects.

Removed routes do not exist at all in that mode (404, not in ``/openapi.json``).
Templates get ``is_desktop()`` / ``route_available(path)``; React pages get
``desktop`` and ``unavailable`` (regex list) in the page payload, used by
``<Link>``, ``<DesktopOnly>``/``<WebOnly>`` and ``useLila().isAvailable``.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from lila.core.config import ENV_CONFIG

_TRUE = {"1", "true", "yes", "on", "y", "s", "si", "sí"}

DESKTOP_ONLY = "only"
WEB_ONLY = False

# Routes the framework itself always needs (client scripts, static files).
_ALWAYS_KEEP = ("/js", "/public", "/img", "/_lila", "/favicon.ico")


def _is_framework_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _ALWAYS_KEEP)

_SUGGEST_KEYWORDS: Dict[str, str] = {
    "pay": "payments",
    "checkout": "payments",
    "billing": "payments",
    "invoice": "payments",
    "subscription": "payments",
    "stripe": "payments",
    "paypal": "payments",
    "mercadopago": "payments",
    "webhook": "webhooks are called by external services",
    "upload": "uploads",
    "oauth": "OAuth callbacks need a public redirect URL",
    "sitemap": "SEO only",
    "robots.txt": "SEO only",
    "newsletter": "marketing",
    "pricing": "marketing",
}


def is_desktop() -> bool:
    """True inside ``lila desktop dev`` and frozen desktop builds."""
    flag = str(os.environ.get("LILA_DESKTOP", "") or "").strip().lower()
    if flag in _TRUE:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    return bool(os.environ.get("LILA_DESKTOP_TOKEN"))


def _split(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = str(value).replace("\n", ",").split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def exclude_patterns() -> List[str]:
    """``DESKTOP_EXCLUDE`` (.env) + ``LILA_DESKTOP_EXCLUDE`` (baked in by build)."""
    patterns = _split(ENV_CONFIG.get("DESKTOP_EXCLUDE", "")) + _split(os.environ.get("LILA_DESKTOP_EXCLUDE", ""))
    return list(dict.fromkeys(patterns))


def _route_path(route: Any) -> str:
    return str(getattr(route, "path", "") or "")


def _route_name(route: Any) -> str:
    return str(getattr(route, "name", "") or "")


def match_pattern(pattern: str, path: str, name: str = "") -> bool:
    """``/payments`` matches the path and everything below it; ``*``/``?`` are
    globs (``/api/*/upload``); ``name:checkout`` matches the route name."""
    pattern = pattern.strip()
    if not pattern:
        return False
    if pattern.startswith("name:"):
        return fnmatch.fnmatchcase(name, pattern[5:].strip())
    if not pattern.startswith("/"):
        pattern = "/" + pattern
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatchcase(path, pattern)
    base = pattern.rstrip("/") or "/"
    return path == base or (base != "/" and path.startswith(base + "/"))


def route_mode(route: Any) -> Any:
    """``True``/``None`` (both), ``False`` (web only) or ``"only"`` (desktop only)."""
    return getattr(route, "lila_desktop", None)


def route_status(route: Any, desktop: Optional[bool] = None,
                 patterns: Optional[Sequence[str]] = None) -> Tuple[bool, str]:
    """Returns ``(enabled, reason)`` for a route in desktop or web mode."""
    desktop = is_desktop() if desktop is None else desktop
    path = _route_path(route)
    mode = route_mode(route)
    if desktop:
        if mode is False:
            return False, "desktop=False"
        if _is_framework_path(path):
            return True, "framework"
        for pattern in (exclude_patterns() if patterns is None else patterns):
            if match_pattern(pattern, path, _route_name(route)):
                return False, f"excluded by {pattern!r}"
        return True, "desktop='only'" if mode == DESKTOP_ONLY else ""
    if mode == DESKTOP_ONLY:
        return False, "desktop='only'"
    return True, ""


def filter_routes(routes: Iterable[Any], desktop: Optional[bool] = None,
                  patterns: Optional[Sequence[str]] = None) -> Tuple[List[Any], List[Any]]:
    kept, removed = [], []
    for route in routes:
        enabled, _ = route_status(route, desktop=desktop, patterns=patterns)
        (kept if enabled else removed).append(route)
    return kept, removed


def suggest_exclusions(routes: Iterable[Any]) -> List[Tuple[str, str]]:
    """Heuristic: routes that look web-only (payments, uploads, webhooks...)."""
    suggestions = []
    for route in routes:
        path = _route_path(route)
        if not path or route_mode(route) is not None:
            continue
        if _is_framework_path(path) or path == "/uploads":
            continue
        endpoint = getattr(route, "endpoint", None)
        haystack = f"{path} {_route_name(route)} {getattr(endpoint, '__name__', '')}".lower()
        for keyword, reason in _SUGGEST_KEYWORDS.items():
            if keyword in haystack:
                suggestions.append((path, reason))
                break
    return suggestions


def path_regex(route: Any) -> str:
    """JavaScript-compatible regex source of a Starlette route path."""
    regex = getattr(route, "path_regex", None)
    source = regex.pattern if regex is not None else "^" + re.escape(_route_path(route)) + "$"
    return source.replace("(?P<", "(?<").replace("\\Z", "$")


# The App registers the routes it removed so templates/React can hide links.
_UNAVAILABLE: List[Any] = []


def register_unavailable(routes: Iterable[Any]) -> None:
    _UNAVAILABLE[:] = list(routes)


def unavailable_routes() -> List[Any]:
    return list(_UNAVAILABLE)


def unavailable_patterns() -> List[str]:
    return list(dict.fromkeys(path_regex(route) for route in _UNAVAILABLE))


def route_available(path: str) -> bool:
    """False when ``path`` belongs to a route removed in the current mode."""
    path = str(path or "").split("?", 1)[0].split("#", 1)[0]
    for route in _UNAVAILABLE:
        regex = getattr(route, "path_regex", None)
        if regex is not None and regex.match(path):
            return False
        if regex is None and _route_path(route) == path:
            return False
    return True


def client_info() -> Dict[str, Any]:
    return {"desktop": is_desktop(), "unavailable": unavailable_patterns()}
