"""Responsive images: ``{{ image("img/hero.jpg", alt="Hero", widths=[480, 960, 1440]) }}``.

Generates WebP variants once (``public/img/_r/hero-480.webp`` ...) with Pillow
(``pip install "lila-framework[images]"``) and renders::

    <img src=".../hero-1440.webp" srcset="...-480.webp 480w, ...-960.webp 960w, ..."
         sizes="100vw" width="1440" height="810" loading="lazy" decoding="async" alt="Hero">

Variants are regenerated only when the original changes (mtime), never
upscaled, and kept in memory after the first lookup. Without Pillow the
original file is used. Paths outside ``public/`` are rejected.
"""

from __future__ import annotations

import html
import os
import threading
from typing import Dict, Iterable, List, Optional, Tuple

from markupsafe import Markup

from lila.core.config import get_base_path

_cache: Dict[Tuple[str, float, tuple], dict] = {}
_lock = threading.Lock()
DEFAULT_WIDTHS = (480, 960, 1440)


def _public_root() -> str:
    return os.path.realpath(get_base_path("public"))


def _resolve(src: str) -> Optional[str]:
    root = _public_root()
    full = os.path.realpath(os.path.join(root, src.lstrip("/\\")))
    if not (full == root or full.startswith(root + os.sep)) or not os.path.isfile(full):
        return None
    return full


def variants(src: str, widths: Iterable[int] = DEFAULT_WIDTHS, quality: int = 80) -> dict:
    """``{"src", "srcset": [(url, w)], "width", "height"}`` (creates missing variants)."""
    from lila.core.templates import public

    clean = src.lstrip("/\\")
    full = _resolve(clean)
    if full is None:
        return {"src": "/" + clean, "srcset": [], "width": None, "height": None}
    mtime = os.path.getmtime(full)
    key = (full, mtime, tuple(sorted(set(int(w) for w in widths))))
    cached = _cache.get(key)
    if cached is not None:
        return cached
    with _lock:
        cached = _cache.get(key)
        if cached is not None:
            return cached
        try:
            from PIL import Image
        except ImportError:
            result = {"src": public(clean), "srcset": [], "width": None, "height": None}
            _cache[key] = result
            return result
        root = _public_root()
        rel_dir, filename = os.path.split(os.path.relpath(full, root))
        stem = os.path.splitext(filename)[0]
        out_dir = os.path.join(root, rel_dir, "_r")
        os.makedirs(out_dir, exist_ok=True)
        srcset: List[Tuple[str, int]] = []
        with Image.open(full) as img:
            orig_w, orig_h = img.size
            for width in key[2]:
                target_w = min(width, orig_w)  # never upscale
                out_name = f"{stem}-{target_w}.webp"
                out_path = os.path.join(out_dir, out_name)
                if not os.path.isfile(out_path) or os.path.getmtime(out_path) < mtime:
                    ratio = target_w / float(orig_w)
                    resized = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
                    resized = resized.resize((target_w, max(1, round(orig_h * ratio))), Image.LANCZOS)
                    resized.save(out_path, "WEBP", quality=int(quality), method=4)
                url = public("/".join(p for p in (rel_dir.replace(os.sep, "/"), "_r", out_name) if p))
                if (url, target_w) not in srcset:
                    srcset.append((url, target_w))
                if target_w == orig_w:
                    break
        largest = srcset[-1] if srcset else (public(clean), orig_w)
        result = {
            "src": largest[0],
            "srcset": srcset,
            "width": largest[1],
            "height": round(orig_h * largest[1] / float(orig_w)),
        }
        for old in [k for k in _cache if k[0] == full and k != key]:
            _cache.pop(old, None)
        _cache[key] = result
        return result


def responsive_image(src: str, alt: str = "", widths: Iterable[int] = DEFAULT_WIDTHS, sizes: str = "100vw",
                     lazy: bool = True, quality: int = 80, **attrs) -> Markup:
    data = variants(src, widths, quality)
    esc = html.escape
    parts = [f'src="{esc(data["src"])}"']
    if data["srcset"]:
        parts.append('srcset="' + esc(", ".join(f"{url} {w}w" for url, w in data["srcset"])) + '"')
        parts.append(f'sizes="{esc(sizes)}"')
    if data["width"]:
        parts.append(f'width="{data["width"]}" height="{data["height"]}"')
    parts.append(f'alt="{esc(alt)}"')
    if lazy:
        parts.append('loading="lazy" decoding="async"')
    else:
        parts.append('fetchpriority="high"')
    for key, value in attrs.items():
        name = key.rstrip("_").replace("_", "-")
        if value is True:
            parts.append(name)
        elif value not in (None, False):
            parts.append(f'{name}="{esc(str(value))}"')
    return Markup("<img " + " ".join(parts) + ">")
