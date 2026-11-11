"""Finds translation keys used in templates/code that are missing per language.

    lila i18n check            # report
    lila i18n check --strict   # exit code 1 when something is missing (CI)

Keys are collected from ``translate['key']``, ``t('key')`` and
``Translate.t(key='key')`` in ``resources/**/*.jinja|html`` and ``app/**/*.py``.
A key counts as available for a language when it exists in Lila's built-in
locales or in ``app/locales/<lang>.json``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Set

_PATTERNS = [
    re.compile(r"""translate\[\s*(['"])(?P<key>[^'"\n]+)\1\s*\]"""),
    re.compile(r"""(?<![\w.])t\(\s*(['"])(?P<key>[^'"\n]+)\1"""),
    re.compile(r"""Translate\.t\(\s*(?:key\s*=\s*)?(['"])(?P<key>[^'"\n]+)\1"""),
]


def _files(root: str, exts: tuple) -> List[str]:
    found = []
    if not os.path.isdir(root):
        return found
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__pycache__", "node_modules"))]
        for name in files:
            if name.endswith(exts):
                found.append(os.path.join(base, name))
    return found


def used_keys(project_dir: str = ".") -> Dict[str, Set[str]]:
    """key -> set of files using it."""
    keys: Dict[str, Set[str]] = {}
    sources = _files(os.path.join(project_dir, "resources"), (".jinja", ".html")) + _files(
        os.path.join(project_dir, "app"), (".py",)
    )
    for path in sources:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in _PATTERNS:
            for match in pattern.finditer(text):
                keys.setdefault(match.group("key"), set()).add(os.path.relpath(path, project_dir))
    return keys


def available_keys(project_dir: str = ".") -> Dict[str, Set[str]]:
    """lang -> keys (built-in + project overrides)."""
    from lila.core.translate import Translate

    langs: Dict[str, Set[str]] = {lang: set(d.keys()) for lang, d in Translate.BUILTIN_LOCALES.items()}
    folder = os.path.join(project_dir, "app", "locales")
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if not name.endswith(".json"):
                continue
            lang = name[:-5][:2].lower()
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                langs.setdefault(lang, set()).update(data.keys())
    return langs


def check(project_dir: str = ".") -> Dict[str, object]:
    used = used_keys(project_dir)
    langs = available_keys(project_dir)
    missing: Dict[str, List[str]] = {}
    for lang, keys in sorted(langs.items()):
        lacking = sorted(k for k in used if k not in keys)
        if lacking:
            missing[lang] = lacking
    all_keys = set().union(*langs.values()) if langs else set()
    parity: Dict[str, List[str]] = {}
    folder = os.path.join(project_dir, "app", "locales")
    project_langs = {n[:-5][:2].lower() for n in os.listdir(folder)} if os.path.isdir(folder) else set()
    project_keys: Set[str] = set()
    for lang in project_langs:
        project_keys |= {k for k in langs.get(lang, set())}
    for lang in sorted(project_langs):
        gaps = sorted(k for k in project_keys if k not in langs.get(lang, set()))
        if gaps:
            parity[lang] = gaps
    return {"used": len(used), "languages": sorted(langs), "missing": missing, "parity": parity,
            "total_keys": len(all_keys)}
