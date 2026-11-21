"""Vite bridge: dev server (HMR / React Fast Refresh) and production manifest.

Development
    ``lila react dev`` (or ``npm run dev``) starts Vite. The Lila Vite plugin in
    ``vite.config.js`` writes ``public/build/hot`` with the dev-server URL; while
    the app runs with ``DEBUG=True`` and that file exists, pages load their
    scripts straight from Vite (HMR, React Fast Refresh).

Production
    ``lila react build`` runs ``vite build`` into ``public/build`` with
    ``public/build/.vite/manifest.json``. Lila reads the manifest and emits
    hashed ``<script type="module">``, ``<link rel="modulepreload">`` and CSS
    tags. Node.js is never needed on the server.

The ``hot`` file is ignored unless ``DEBUG`` is on, so a stale file left in a
deploy can never point production pages at a dev server.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lila.core.config import ENV_CONFIG, get_base_path, is_debug

DEFAULT_ENTRY = "resources/react/main.tsx"
DEFAULT_SPA_ENTRY = "resources/react/spa.tsx"
_EXTENSIONS = (".tsx", ".jsx", ".ts", ".js")


def default_entry(spa: bool = False) -> str:
    """``resources/react/main.tsx`` (TypeScript) or ``main.jsx`` (``--js``)."""
    stem = "resources/react/spa" if spa else "resources/react/main"
    manifest = ViteBridge.manifest() if not ViteBridge.is_dev() else {}
    for ext in _EXTENSIONS:
        candidate = stem + ext
        if candidate in manifest or os.path.isfile(get_base_path(*candidate.split("/"))):
            return candidate
    return stem + ".tsx"
BUILD_DIR = ("public", "build")
BUILD_URL = "/public/build/"


class ViteManifestMissing(RuntimeError):
    """Raised when production pages need assets that were never built."""


def _build_path(*parts: str) -> str:
    return get_base_path(*BUILD_DIR, *parts)


def manifest_path() -> str:
    """``public/build/.vite/manifest.json`` (Vite 5+) or ``public/build/manifest.json``."""
    modern = _build_path(".vite", "manifest.json")
    if os.path.isfile(modern):
        return modern
    legacy = _build_path("manifest.json")
    return legacy if os.path.isfile(legacy) else modern


def hot_file() -> str:
    return _build_path("hot")


class ViteBridge:
    """Resolves entry points to ``<script>``/``<link>`` tags (dev or build)."""

    _lock = threading.Lock()
    _manifest: Optional[Dict[str, Any]] = None
    _manifest_mtime: float = -1.0
    _version: str = ""

    # ── mode ────────────────────────────────────────────────────────────────
    @classmethod
    def dev_url(cls) -> Optional[str]:
        """Vite dev-server URL when running in development, else ``None``."""
        explicit = str(ENV_CONFIG.get("VITE_DEV_SERVER", "") or "").strip()
        if not is_debug():
            return None
        if explicit:
            return explicit.rstrip("/")
        path = hot_file()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                url = fh.read().strip()
        except OSError:
            return None
        if url.startswith(("http://", "https://")):
            return url.rstrip("/")
        return None

    @classmethod
    def is_dev(cls) -> bool:
        return cls.dev_url() is not None

    # ── manifest ────────────────────────────────────────────────────────────
    @classmethod
    def manifest(cls) -> Dict[str, Any]:
        path = manifest_path()
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return {}
        # In production the manifest only changes on deploy; checking the mtime
        # is a single stat() and lets `lila react build` work without restart.
        if cls._manifest is not None and mtime == cls._manifest_mtime:
            return cls._manifest
        with cls._lock:
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
                data = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError):
                return cls._manifest or {}
            cls._manifest = data if isinstance(data, dict) else {}
            cls._manifest_mtime = mtime
            cls._version = hashlib.sha256(raw).hexdigest()[:12]
        return cls._manifest

    @classmethod
    def version(cls) -> str:
        """Asset version: changes on every build (``ASSET_VERSION`` overrides)."""
        override = str(ENV_CONFIG.get("ASSET_VERSION", "") or "")
        if override:
            return override
        if cls.is_dev():
            return "dev"
        cls.manifest()
        return cls._version

    @classmethod
    def reset(cls) -> None:
        cls._manifest = None
        cls._manifest_mtime = -1.0
        cls._version = ""

    # ── tags ────────────────────────────────────────────────────────────────
    @staticmethod
    def _base_url() -> str:
        base = str(ENV_CONFIG.get("VITE_BASE", "") or BUILD_URL)
        if not base.endswith("/"):
            base += "/"
        app_url = str(ENV_CONFIG.get("ASSET_URL", "") or "").rstrip("/")
        return f"{app_url}{base}" if app_url else base

    @classmethod
    def _collect(cls, manifest: Dict[str, Any], key: str, seen: set, css: List[str], preload: List[str]) -> None:
        if key in seen:
            return
        seen.add(key)
        chunk = manifest.get(key) or {}
        for name in chunk.get("imports", []) or []:
            imported = manifest.get(name) or {}
            if imported.get("file"):
                preload.append(imported["file"])
            cls._collect(manifest, name, seen, css, preload)
        for file in chunk.get("css", []) or []:
            css.append(file)

    @classmethod
    def build_tags(cls, entries: Iterable[str], nonce: str = "") -> str:
        manifest = cls.manifest()
        if not manifest:
            raise ViteManifestMissing(
                "Vite manifest not found (public/build/.vite/manifest.json). "
                "Run `lila react build` before starting in production, or `lila react dev` for development."
            )
        base = cls._base_url()
        css: List[str] = []
        preload: List[str] = []
        scripts: List[str] = []
        seen: set = set()
        for entry in entries:
            chunk = manifest.get(entry)
            if not chunk:
                raise ViteManifestMissing(
                    f"Entry '{entry}' is not in the Vite manifest. Add it to build.rollupOptions.input "
                    "in vite.config.js and run `lila react build` again."
                )
            if entry.endswith((".css", ".scss", ".sass", ".less")):
                css.append(chunk["file"])
            else:
                scripts.append(chunk["file"])
            for file in chunk.get("css", []) or []:
                css.append(file)
            cls._collect(manifest, entry, seen, css, preload)

        def unique(items: List[str]) -> List[str]:
            return list(dict.fromkeys(items))

        tags = [f'<link rel="stylesheet" href="{html.escape(base + f)}" />' for f in unique(css)]
        tags += [f'<link rel="modulepreload" href="{html.escape(base + f)}"{nonce} />' for f in unique(preload)]
        tags += [f'<script type="module" src="{html.escape(base + f)}"{nonce}></script>' for f in unique(scripts)]
        return "\n".join(tags)

    @classmethod
    def dev_tags(cls, entries: Iterable[str], react: bool = True, nonce: str = "") -> str:
        url = cls.dev_url() or ""
        esc = html.escape(url)
        tags = []
        if react:
            # Same preamble @vitejs/plugin-react injects in index.html (needed
            # when the HTML comes from the backend instead of Vite).
            tags.append(
                f'<script type="module"{nonce}>'
                f'import RefreshRuntime from "{esc}/@react-refresh";'
                "RefreshRuntime.injectIntoGlobalHook(window);"
                "window.$RefreshReg$ = () => {};"
                "window.$RefreshSig$ = () => (type) => type;"
                "window.__vite_plugin_react_preamble_installed__ = true;"
                "</script>"
            )
        tags.append(f'<script type="module" src="{esc}/@vite/client"{nonce}></script>')
        for entry in entries:
            src = f"{esc}/{html.escape(entry.lstrip('/'))}"
            if entry.endswith((".css", ".scss", ".sass", ".less")):
                tags.append(f'<link rel="stylesheet" href="{src}" />')
            else:
                tags.append(f'<script type="module" src="{src}"{nonce}></script>')
        return "\n".join(tags)

    @classmethod
    def tags(cls, entries: Any = None, react: bool = True, nonce: str = "") -> str:
        """``<script>``/``<link>`` tags for one or more entries (dev or build).

        ``nonce`` is the ``' nonce="..."'`` attribute (``lila.core.csp.nonce_attr``)."""
        if not entries:
            entries = [default_entry()]
        elif isinstance(entries, str):
            entries = [entries]
        entries = [str(e).lstrip("/") for e in entries]
        if cls.is_dev():
            return cls.dev_tags(entries, react=react, nonce=nonce)
        return cls.build_tags(entries, nonce=nonce)


def vite(entries: Any = None, react: bool = True, nonce: str = "") -> str:
    """Jinja helper: ``{{ vite("resources/react/main.jsx") }}``."""
    from markupsafe import Markup

    try:
        return Markup(ViteBridge.tags(entries, react=react, nonce=str(nonce or "")))
    except ViteManifestMissing as exc:
        from lila.core.logger import Logger

        Logger.error(f"[Lila] {exc}")
        if is_debug():
            return Markup(f"<!-- {html.escape(str(exc))} -->")
        raise


def status() -> Tuple[str, str]:
    """``("dev", url)``, ``("build", manifest_path)`` or ``("missing", hint)``."""
    url = ViteBridge.dev_url()
    if url:
        return "dev", url
    if ViteBridge.manifest():
        return "build", manifest_path()
    return "missing", "run `lila react build` (production) or `lila react dev` (development)"
