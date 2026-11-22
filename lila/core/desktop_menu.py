"""Native desktop menu bar, clipboard helpers and built-in modals.

Builds the native menu (File / Edit / View / Help + macOS ``__app__``) for
``pywebview`` windows in ``lila desktop dev`` and ``lila desktop build``.
Includes three CSP-safe built-in modals when not intercepted by the app via
``CustomEvent('lila:desktop-about' | 'lila:desktop-preferences' | 'lila:desktop-help')``:

- **About**: app name, version, description, author, OS info, copyable diagnostics.
- **Preferences**: navigates to ``DESKTOP_PREFERENCES_URL`` if configured, or
  shows theme, zoom and data-folder controls.
- **Help / Manual**: renders a Markdown file (``resources/manual.md`` by default,
  empty until authored) with optional in-app view/edit/save support.
"""

from __future__ import annotations

import html
import importlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from lila.core.config import ENV_CONFIG, get_base_path, get_data_path

MAX_MANUAL_BYTES = 512 * 1024  # 512 KB cap for in-app manual persistence

_ALLOWED_LINK_SCHEMES = ("https://", "http://", "mailto:", "/", "#")
_FALSE_MARKERS = {"0", "false", "no", "off"}


# ─── Localization ─────────────────────────────────────────────────────────────

MENU_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "menu_file": "File",
        "menu_edit": "Edit",
        "menu_view": "View",
        "menu_help": "Help",
        "preferences": "Preferences...",
        "quit": "Quit",
        "undo": "Undo",
        "redo": "Redo",
        "cut": "Cut",
        "copy": "Copy",
        "paste": "Paste",
        "select_all": "Select All",
        "back": "Back",
        "forward": "Forward",
        "reload": "Reload",
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "zoom_reset": "Reset Zoom (100%)",
        "fullscreen": "Toggle Fullscreen",
        "manual": "Manual / Help",
        "check_updates": "Check for Updates...",
        "about_fmt": "About {app}",
        "close": "Close",
        "view": "View",
        "edit": "Edit",
        "preview": "Preview",
        "save": "Save",
        "saved": "Saved!",
        "saving": "Saving...",
        "reset_original": "Reset to original",
        "empty_manual_hint": "The manual is empty. Click Edit to write documentation in Markdown.",
        "empty_manual_readonly": "No documentation has been added to this application yet.",
        "edit_manual_cta": "Edit manual",
        "theme": "Appearance",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "theme_system": "System",
        "zoom": "Zoom",
        "data_folder": "Data folder",
        "open_folder": "Open folder",
        "version": "Version",
        "platform": "Platform",
        "lila_version": "Lila Framework",
        "author": "Author",
        "up_to_date": "You are using the latest version.",
        "update_available": "Update available",
        "install_update": "Download & install update",
        "checking_updates": "Checking for updates...",
        "check_again": "Check again",
        "copy_system_info": "Copy system info",
        "copied": "Copied!",
        "preferences_title": "Preferences",
        "manual_title": "Manual / Help",
        "about_title": "About",
        "updates_title": "Updates",
        "manual_characters": "chars",
        "manual_lines": "lines",
        "save_error": "Could not save manual",
        "unsaved_changes": "Unsaved changes",
        "markdown_placeholder": "# Application Manual\n\nWrite your documentation in **Markdown**...",
    },
    "es": {
        "menu_file": "Archivo",
        "menu_edit": "Editar",
        "menu_view": "Ver",
        "menu_help": "Ayuda",
        "preferences": "Preferencias...",
        "quit": "Salir",
        "undo": "Deshacer",
        "redo": "Rehacer",
        "cut": "Cortar",
        "copy": "Copiar",
        "paste": "Pegar",
        "select_all": "Seleccionar todo",
        "back": "Ir atrás",
        "forward": "Ir adelante",
        "reload": "Recargar",
        "zoom_in": "Acercar",
        "zoom_out": "Alejar",
        "zoom_reset": "Restablecer zoom (100%)",
        "fullscreen": "Pantalla completa",
        "manual": "Manual / Ayuda",
        "check_updates": "Buscar actualizaciones...",
        "about_fmt": "Acerca de {app}",
        "close": "Cerrar",
        "view": "Ver",
        "edit": "Editar",
        "preview": "Vista previa",
        "save": "Guardar",
        "saved": "¡Guardado!",
        "saving": "Guardando...",
        "reset_original": "Restaurar original",
        "empty_manual_hint": "El manual está vacío. Haz clic en Editar para escribir la documentación en Markdown.",
        "empty_manual_readonly": "Todavía no se ha agregado documentación a esta aplicación.",
        "edit_manual_cta": "Editar manual",
        "theme": "Apariencia",
        "theme_light": "Claro",
        "theme_dark": "Oscuro",
        "theme_system": "Sistema",
        "zoom": "Zoom",
        "data_folder": "Carpeta de datos",
        "open_folder": "Abrir carpeta",
        "version": "Versión",
        "platform": "Plataforma",
        "lila_version": "Lila Framework",
        "author": "Autor",
        "up_to_date": "Estás usando la última versión.",
        "update_available": "Actualización disponible",
        "install_update": "Descargar e instalar actualización",
        "checking_updates": "Buscando actualizaciones...",
        "check_again": "Buscar de nuevo",
        "copy_system_info": "Copiar información del sistema",
        "copied": "¡Copiado!",
        "preferences_title": "Preferencias",
        "manual_title": "Manual / Ayuda",
        "about_title": "Acerca de",
        "updates_title": "Actualizaciones",
        "manual_characters": "caracteres",
        "manual_lines": "líneas",
        "save_error": "No se pudo guardar el manual",
        "unsaved_changes": "Cambios sin guardar",
        "markdown_placeholder": "# Manual de la aplicación\n\nEscribe la documentación en **Markdown**...",
    },
    "pt": {
        "menu_file": "Arquivo",
        "menu_edit": "Editar",
        "menu_view": "Exibir",
        "menu_help": "Ajuda",
        "preferences": "Preferências...",
        "quit": "Sair",
        "undo": "Desfazer",
        "redo": "Refazer",
        "cut": "Recortar",
        "copy": "Copiar",
        "paste": "Colar",
        "select_all": "Selecionar tudo",
        "back": "Voltar",
        "forward": "Avançar",
        "reload": "Recarregar",
        "zoom_in": "Aumentar zoom",
        "zoom_out": "Diminuir zoom",
        "zoom_reset": "Redefinir zoom (100%)",
        "fullscreen": "Tela cheia",
        "manual": "Manual / Ajuda",
        "check_updates": "Verificar atualizações...",
        "about_fmt": "Sobre {app}",
        "close": "Fechar",
        "view": "Visualizar",
        "edit": "Editar",
        "preview": "Pré-visualizar",
        "save": "Salvar",
        "saved": "Salvo!",
        "saving": "Salvando...",
        "reset_original": "Restaurar original",
        "empty_manual_hint": "O manual está vazio. Clique em Editar para escrever a documentação em Markdown.",
        "empty_manual_readonly": "Nenhuma documentação foi adicionada a este aplicativo ainda.",
        "edit_manual_cta": "Editar manual",
        "theme": "Aparência",
        "theme_light": "Claro",
        "theme_dark": "Escuro",
        "theme_system": "Sistema",
        "zoom": "Zoom",
        "data_folder": "Pasta de dados",
        "open_folder": "Abrir pasta",
        "version": "Versão",
        "platform": "Plataforma",
        "lila_version": "Lila Framework",
        "author": "Autor",
        "up_to_date": "Você está usando a versão mais recente.",
        "update_available": "Atualização disponível",
        "install_update": "Baixar e instalar atualização",
        "checking_updates": "Verificando atualizações...",
        "check_again": "Verificar novamente",
        "copy_system_info": "Copiar informações do sistema",
        "copied": "Copiado!",
        "preferences_title": "Preferências",
        "manual_title": "Manual / Ajuda",
        "about_title": "Sobre",
        "updates_title": "Atualizações",
        "manual_characters": "caracteres",
        "manual_lines": "linhas",
        "save_error": "Não foi possível salvar o manual",
        "unsaved_changes": "Alterações não salvas",
        "markdown_placeholder": "# Manual do aplicativo\n\nEscreva a documentação em **Markdown**...",
    },
    "zh": {
        "menu_file": "文件",
        "menu_edit": "编辑",
        "menu_view": "视图",
        "menu_help": "帮助",
        "preferences": "偏好设置...",
        "quit": "退出",
        "undo": "撤销",
        "redo": "重做",
        "cut": "剪切",
        "copy": "复制",
        "paste": "粘贴",
        "select_all": "全选",
        "back": "后退",
        "forward": "前进",
        "reload": "重新加载",
        "zoom_in": "放大",
        "zoom_out": "缩小",
        "zoom_reset": "重置缩放 (100%)",
        "fullscreen": "切换全屏",
        "manual": "手册 / 帮助",
        "check_updates": "检查更新...",
        "about_fmt": "关于 {app}",
        "close": "关闭",
        "view": "查看",
        "edit": "编辑",
        "preview": "预览",
        "save": "保存",
        "saved": "已保存！",
        "saving": "保存中...",
        "reset_original": "恢复默认",
        "empty_manual_hint": "手册为空。点击“编辑”使用 Markdown 编写文档。",
        "empty_manual_readonly": "此应用尚未添加文档。",
        "edit_manual_cta": "编辑手册",
        "theme": "外观",
        "theme_light": "浅色",
        "theme_dark": "深色",
        "theme_system": "跟随系统",
        "zoom": "缩放",
        "data_folder": "数据目录",
        "open_folder": "打开目录",
        "version": "版本",
        "platform": "平台",
        "lila_version": "Lila Framework",
        "author": "作者",
        "up_to_date": "当前已是最新版本。",
        "update_available": "有可用更新",
        "install_update": "下载并安装更新",
        "checking_updates": "正在检查更新...",
        "check_again": "重新检查",
        "copy_system_info": "复制系统信息",
        "copied": "已复制！",
        "preferences_title": "偏好设置",
        "manual_title": "手册 / 帮助",
        "about_title": "关于",
        "updates_title": "更新",
        "manual_characters": "字符",
        "manual_lines": "行",
        "save_error": "无法保存手册",
        "unsaved_changes": "有未保存的更改",
        "markdown_placeholder": "# 应用手册\n\n使用 **Markdown** 编写文档...",
    },
}


def _env_str(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val is not None and str(val).strip() != "":
        return str(val).strip()
    cfg = ENV_CONFIG.get(key, "")
    return str(cfg).strip() if cfg is not None and str(cfg).strip() != "" else default


def _env_bool(key: str, default: bool = True) -> bool:
    raw = os.environ.get(key)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() not in _FALSE_MARKERS
    return ENV_CONFIG.get_bool(key, default)


def get_menu_labels(lang: Optional[str] = None) -> Dict[str, str]:
    """Returns localized labels for the native menu bar and built-in modals."""
    raw = (
        lang
        or _env_str("DESKTOP_MENU_LANG")
        or _env_str("LANG_DEFAULT")
        or "en"
    )
    code = str(raw).strip().lower()[:2]
    return dict(MENU_LABELS.get(code, MENU_LABELS["en"]))


# ─── Cross-platform Clipboard ─────────────────────────────────────────────────

def _win32_clipboard_fns():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    return ctypes, user32, kernel32


def _win32_open_clipboard(user32) -> bool:
    for _ in range(3):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_clipboard_text() -> str:
    """Reads plain UTF-8 text from the OS clipboard (empty string on failure)."""
    try:
        if sys.platform == "win32":
            ctypes, user32, kernel32 = _win32_clipboard_fns()
            cf_unicode = 13
            if not _win32_open_clipboard(user32):
                return ""
            try:
                if not user32.IsClipboardFormatAvailable(cf_unicode):
                    return ""
                handle = user32.GetClipboardData(cf_unicode)
                if not handle:
                    return ""
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    return ""
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        if sys.platform == "darwin":
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            return res.stdout if res.returncode == 0 else ""
        for cmd in (
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    return res.stdout
            except FileNotFoundError:
                continue
    except Exception:
        return ""
    return ""


def set_clipboard_text(text: str) -> bool:
    """Writes plain text to the OS clipboard cleanly."""
    payload = "" if text is None else str(text)
    try:
        if sys.platform == "win32":
            ctypes, user32, kernel32 = _win32_clipboard_fns()
            cf_unicode = 13
            gmem_moveable = 0x0002
            encoded = payload.encode("utf-16-le") + b"\x00\x00"
            if not _win32_open_clipboard(user32):
                return False
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(gmem_moveable, len(encoded))
                if not h_mem:
                    return False
                ptr = kernel32.GlobalLock(h_mem)
                if not ptr:
                    kernel32.GlobalFree(h_mem)
                    return False
                try:
                    ctypes.memmove(ptr, encoded, len(encoded))
                finally:
                    kernel32.GlobalUnlock(h_mem)
                if not user32.SetClipboardData(cf_unicode, h_mem):
                    kernel32.GlobalFree(h_mem)
                    return False
                return True
            finally:
                user32.CloseClipboard()
        if sys.platform == "darwin":
            res = subprocess.run(["pbcopy"], input=payload, text=True, timeout=3)
            return res.returncode == 0
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                res = subprocess.run(cmd, input=payload, text=True, timeout=3)
                if res.returncode == 0:
                    return True
            except FileNotFoundError:
                continue
    except Exception:
        return False
    return False


# ─── XSS-Safe Markdown Renderer ───────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_FENCE_RE = re.compile(r"^```([a-zA-Z0-9_+-]*)\s*$")
_TABLE_SEP_CELL_RE = re.compile(r"^:?-{2,}:?$")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\[\]\n]+)\]\(([^()\n]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^\s*][^*\n]*?[^\s*]|[^\s*])\*(?!\*)|(?<!\w)_([^\s_][^_\n]*?[^\s_]|[^\s_])_(?!\w)")
_STRIKE_RE = re.compile(r"~~(.+?)~~")


def _safe_url(raw_url: str) -> Optional[str]:
    cleaned = raw_url.strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if any(lower.startswith(scheme) for scheme in _ALLOWED_LINK_SCHEMES):
        return cleaned
    return None


def _render_inline(raw_text: str) -> str:
    """Escapes raw HTML and applies safe inline Markdown formatting."""
    placeholders: List[str] = []

    def _stash_code(match: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00CODE{idx}\x00"

    protected = _INLINE_CODE_RE.sub(_stash_code, raw_text)
    escaped = html.escape(protected, quote=True)

    link_placeholders: List[str] = []

    def _stash_link(match: re.Match) -> str:
        label_raw = match.group(1)
        url_unescaped = html.unescape(match.group(2))
        safe = _safe_url(url_unescaped)
        if not safe:
            # Neutralize unsafe schemes like javascript: or data:
            return f"{label_raw} ({html.escape(url_unescaped, quote=True)})"
        escaped_href = html.escape(safe, quote=True)
        external = safe.lower().startswith(("http://", "https://", "mailto:"))
        attrs = ' target="_blank" rel="noopener noreferrer" data-lila-external="1"' if external else ""
        idx = len(link_placeholders)
        link_placeholders.append(f'<a href="{escaped_href}"{attrs}>{_format_inline_styles(label_raw)}</a>')
        return f"\x00LINK{idx}\x00"

    def _format_inline_styles(text: str) -> str:
        out = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
        out = _STRIKE_RE.sub(r"<del>\1</del>", out)
        out = _ITALIC_RE.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", out)
        return out

    with_links = _LINK_RE.sub(_stash_link, escaped)
    formatted = _format_inline_styles(with_links)

    for idx, link_html in enumerate(link_placeholders):
        formatted = formatted.replace(f"\x00LINK{idx}\x00", link_html)
    for idx, code_html in enumerate(placeholders):
        formatted = formatted.replace(f"\x00CODE{idx}\x00", code_html)
    return formatted


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_header(lines: List[str], idx: int) -> bool:
    if idx + 1 >= len(lines):
        return False
    row, sep = lines[idx], lines[idx + 1]
    if "|" not in row or "|" not in sep:
        return False
    sep_cells = _split_table_row(sep)
    return bool(sep_cells) and all(_TABLE_SEP_CELL_RE.match(cell) for cell in sep_cells)


def render_markdown(text: str) -> str:
    """Renders Markdown to sanitized HTML with zero third-party dependencies."""
    if not text or not str(text).strip():
        return ""

    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 1. Fenced code block
        fence = _FENCE_RE.match(line.strip())
        if fence:
            lang = re.sub(r"[^a-zA-Z0-9_+-]", "", fence.group(1) or "")
            code_lines: List[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        # 2. Horizontal rule
        if _HR_RE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # 3. Heading
        heading = _HEADING_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        # 4. Blockquote
        if line.lstrip().startswith(">"):
            quote_lines: List[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = "<br>".join(_render_inline(q) for q in quote_lines)
            out.append(f"<blockquote><p>{inner}</p></blockquote>")
            continue

        # 5. Table
        if _is_table_header(lines, i):
            headers = _split_table_row(lines[i])
            i += 2  # skip header + separator
            body_rows: List[List[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                body_rows.append(_split_table_row(lines[i]))
                i += 1
            ths = "".join(f"<th>{_render_inline(h)}</th>" for h in headers)
            trs = "".join(
                "<tr>" + "".join(f"<td>{_render_inline(cell)}</td>" for cell in row) + "</tr>"
                for row in body_rows
            )
            out.append(f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>")
            continue

        # 6. Unordered / Ordered lists
        if _UL_RE.match(line):
            items: List[str] = []
            while i < n:
                m = _UL_RE.match(lines[i])
                if not m:
                    break
                items.append(f"<li>{_render_inline(m.group(1).strip())}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        if _OL_RE.match(line):
            items = []
            while i < n:
                m = _OL_RE.match(lines[i])
                if not m:
                    break
                items.append(f"<li>{_render_inline(m.group(1).strip())}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # 7. Paragraph
        para_lines: List[str] = []
        while i < n and lines[i].strip():
            cur = lines[i]
            if (
                _FENCE_RE.match(cur.strip())
                or _HR_RE.match(cur)
                or _HEADING_RE.match(cur.strip())
                or cur.lstrip().startswith(">")
                or _UL_RE.match(cur)
                or _OL_RE.match(cur)
                or _is_table_header(lines, i)
            ):
                break
            para_lines.append(_render_inline(cur.strip()))
            i += 1
        out.append("<p>" + "<br>".join(para_lines) + "</p>")

    return "\n".join(out)


# ─── Help / Manual Persistence ────────────────────────────────────────────────

def default_manual_path() -> str:
    return _env_str("DESKTOP_HELP_FILE", "resources/manual.md") or "resources/manual.md"


def is_help_editable() -> bool:
    return _env_bool("DESKTOP_HELP_EDITABLE", True)


def _resolve_dev_manual_path(help_file: Optional[str] = None) -> str:
    raw = str(help_file or default_manual_path()).strip() or "resources/manual.md"
    if os.path.isabs(raw):
        return raw
    return os.path.abspath(os.path.join(os.getcwd(), raw))


def _resolve_frozen_paths(help_file: Optional[str] = None) -> Tuple[str, str]:
    rel = str(help_file or default_manual_path()).strip() or "resources/manual.md"
    if os.path.isabs(rel):
        bundled = get_base_path(os.path.basename(rel))
    else:
        bundled = get_base_path(rel)
    override = get_data_path("manual.md")
    return override, bundled


def read_help_manual(help_file: Optional[str] = None) -> Dict[str, Any]:
    """Reads the Markdown manual (override -> bundled/project) and renders HTML."""
    is_frozen = bool(getattr(sys, "frozen", False))
    has_override = False
    has_bundled = False

    if is_frozen:
        override_path, bundled_path = _resolve_frozen_paths(help_file)
        has_override = os.path.isfile(override_path)
        has_bundled = os.path.isfile(bundled_path)
        active_path = override_path if has_override else (bundled_path if has_bundled else override_path)
    else:
        active_path = _resolve_dev_manual_path(help_file)

    text = ""
    if active_path and os.path.isfile(active_path):
        try:
            with open(active_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            text = ""

    return {
        "markdown": text,
        "html": render_markdown(text) if text.strip() else "",
        "is_empty": not bool(text.strip()),
        "editable": is_help_editable(),
        "path": active_path,
        "has_override": has_override,
        "has_bundled": has_bundled,
    }


def save_help_manual(content: str, help_file: Optional[str] = None) -> Dict[str, Any]:
    """Persists edits to the Markdown manual unless read-only or oversized."""
    if not is_help_editable():
        return {"ok": False, "reason": "read-only"}

    text = "" if content is None else str(content)
    if len(text.encode("utf-8")) > MAX_MANUAL_BYTES:
        return {"ok": False, "reason": "manual too large (max 512 KB)"}

    if getattr(sys, "frozen", False):
        target, _ = _resolve_frozen_paths(help_file)
    else:
        target = _resolve_dev_manual_path(help_file)

    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}

    return {"ok": True, **read_help_manual(help_file)}


def reset_help_manual(help_file: Optional[str] = None) -> Dict[str, Any]:
    """Removes a user override in frozen builds so the bundled manual applies again."""
    if getattr(sys, "frozen", False):
        override_path, _ = _resolve_frozen_paths(help_file)
        if os.path.isfile(override_path):
            try:
                os.remove(override_path)
            except OSError as exc:
                return {"ok": False, "reason": str(exc)}
    return {"ok": True, **read_help_manual(help_file)}


# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class DesktopMenuConfig:
    enabled: bool = True
    app_name: str = "Lila Desktop"
    app_version: str = "1.0.0"
    description: str = ""
    author: str = ""
    about_text: str = ""
    lang: Optional[str] = None
    preferences_url: str = ""
    help_file: str = "resources/manual.md"
    help_editable: bool = True
    update_url: str = ""

    @classmethod
    def from_env(
        cls,
        app_name: Optional[str] = None,
        enabled: Optional[bool] = None,
        preferences_url: Optional[str] = None,
        help_file: Optional[str] = None,
        help_editable: Optional[bool] = None,
        about_text: Optional[str] = None,
        update_url: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> "DesktopMenuConfig":
        return cls(
            enabled=_env_bool("DESKTOP_MENU", True) if enabled is None else bool(enabled),
            app_name=app_name or _env_str("TITLE_PROJECT", "Lila Desktop"),
            app_version=_env_str("LILA_APP_VERSION") or _env_str("VERSION_PROJECT", "1.0.0"),
            description=_env_str("DESCRIPTION_PROJECT", ""),
            author=_env_str("AUTHOR_DEFAULT", ""),
            about_text=_env_str("DESKTOP_ABOUT", "") if about_text is None else str(about_text),
            lang=lang or _env_str("DESKTOP_MENU_LANG") or _env_str("LANG_DEFAULT", "en"),
            preferences_url=_env_str("DESKTOP_PREFERENCES_URL", "") if preferences_url is None else str(preferences_url),
            help_file=default_manual_path() if help_file is None else str(help_file),
            help_editable=is_help_editable() if help_editable is None else bool(help_editable),
            update_url=_env_str("LILA_UPDATE_URL") or _env_str("DESKTOP_UPDATE_URL") if update_url is None else str(update_url),
        )


# ─── Window JS Helpers ────────────────────────────────────────────────────────

def _run_js(window: Any, script: str) -> None:
    if window is None:
        return
    try:
        if hasattr(window, "evaluate_js"):
            window.evaluate_js(script)
        elif hasattr(window, "run_js"):
            window.run_js(script)
    except Exception:
        pass


def _eval_js(window: Any, script: str) -> Any:
    if window is None:
        return None
    try:
        if hasattr(window, "evaluate_js"):
            return window.evaluate_js(script)
    except Exception:
        return None
    return None


def _dispatch_custom_event(window: Any, event_name: str, detail: Dict[str, Any]) -> bool:
    """Dispatches a cancelable CustomEvent; returns True if an app listener called preventDefault()."""
    script = (
        "(function(){"
        f"var ev = new CustomEvent({json.dumps(event_name)}, {{cancelable: true, detail: {json.dumps(detail)}}});"
        "return !window.dispatchEvent(ev);"
        "})()"
    )
    return bool(_eval_js(window, script))


# ─── Edit Actions (HTML, Jinja & React Controlled Inputs) ─────────────────────

def action_undo(window_getter: Callable[[], Any]) -> None:
    _run_js(window_getter(), "(function(){var a=document.activeElement;if(a&&a.focus)try{a.focus({preventScroll:true});}catch(e){}try{document.execCommand('undo');}catch(e){}})()")


def action_redo(window_getter: Callable[[], Any]) -> None:
    _run_js(window_getter(), "(function(){var a=document.activeElement;if(a&&a.focus)try{a.focus({preventScroll:true});}catch(e){}try{document.execCommand('redo');}catch(e){}})()")


def action_copy(window_getter: Callable[[], Any]) -> None:
    win = window_getter()
    selected = _eval_js(
        win,
        """(function(){
  var a = document.activeElement;
  if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')) {
    try {
      var s = a.selectionStart, e = a.selectionEnd;
      if (typeof s === 'number' && typeof e === 'number' && e > s) {
        return a.value.slice(s, e);
      }
    } catch (_) {}
  }
  var sel = window.getSelection ? window.getSelection().toString() : '';
  if (!sel) { try { document.execCommand('copy'); } catch (_) {} }
  return sel;
})()""",
    )
    if selected:
        set_clipboard_text(str(selected))


def action_cut(window_getter: Callable[[], Any]) -> None:
    win = window_getter()
    cut_text = _eval_js(
        win,
        """(function(){
  var a = document.activeElement;
  if (a && !a.readOnly && !a.disabled && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')) {
    try {
      var s = a.selectionStart, e = a.selectionEnd;
      if (typeof s === 'number' && typeof e === 'number' && e > s) {
        var cut = a.value.slice(s, e);
        var next = a.value.slice(0, s) + a.value.slice(e);
        var proto = a.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(a, next);
        a.setSelectionRange(s, s);
        a.dispatchEvent(new Event('input', {bubbles: true}));
        a.dispatchEvent(new Event('change', {bubbles: true}));
        return cut;
      }
    } catch (_) {}
  }
  var sel = window.getSelection ? window.getSelection().toString() : '';
  if (a && a.isContentEditable && sel) {
    try {
      if (a.focus) a.focus({preventScroll: true});
      document.execCommand('cut');
    } catch (_) {}
  }
  return sel;
})()""",
    )
    if cut_text:
        set_clipboard_text(str(cut_text))


def action_paste(window_getter: Callable[[], Any]) -> None:
    win = window_getter()
    text = get_clipboard_text()
    if not text:
        return
    _run_js(
        win,
        f"""(function(val){{
  var a = document.activeElement;
  if (!a) return;
  if (!a.readOnly && !a.disabled && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')) {{
    try {{
      var s = typeof a.selectionStart === 'number' ? a.selectionStart : a.value.length;
      var e = typeof a.selectionEnd === 'number' ? a.selectionEnd : a.value.length;
      var next = a.value.slice(0, s) + val + a.value.slice(e);
      var proto = a.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(a, next);
      var pos = s + val.length;
      a.setSelectionRange(pos, pos);
      a.dispatchEvent(new Event('input', {{bubbles: true}}));
      a.dispatchEvent(new Event('change', {{bubbles: true}}));
      return;
    }} catch (_) {{}}
  }}
  if (a.isContentEditable) {{
    try {{
      if (a.focus) a.focus({{preventScroll: true}});
      document.execCommand('insertText', false, val);
    }} catch (_) {{}}
  }}
}})({json.dumps(text)})""",
    )


def action_select_all(window_getter: Callable[[], Any]) -> None:
    _run_js(
        window_getter(),
        """(function(){
  var a = document.activeElement;
  if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA') && a.select) {
    a.focus({preventScroll: true});
    a.select();
    return;
  }
  try { document.execCommand('selectAll'); } catch (_) {}
})()""",
    )


# ─── View & Navigation Actions ────────────────────────────────────────────────

def action_back(window_getter: Callable[[], Any]) -> None:
    _run_js(window_getter(), "window.history.back();")


def action_forward(window_getter: Callable[[], Any]) -> None:
    _run_js(window_getter(), "window.history.forward();")


def action_reload(window_getter: Callable[[], Any]) -> None:
    _run_js(window_getter(), "window.location.reload();")


def action_zoom(window_getter: Callable[[], Any], delta: Optional[int] = None) -> None:
    """Adjusts root zoom (50%..200%, persisted to localStorage) and flashes a badge."""
    delta_js = "null" if delta is None else str(int(delta))
    _run_js(
        window_getter(),
        f"""(function(delta){{
  var cur = parseInt(localStorage.getItem('lila-desktop-zoom') || '100', 10);
  if (isNaN(cur) || cur < 50 || cur > 200) cur = 100;
  var next = delta === null ? 100 : Math.max(50, Math.min(200, cur + delta));
  localStorage.setItem('lila-desktop-zoom', String(next));
  document.documentElement.style.zoom = (next / 100).toFixed(2);
  var badge = document.getElementById('lila-desktop-zoom-badge');
  if (!badge) {{
    badge = document.createElement('div');
    badge.id = 'lila-desktop-zoom-badge';
    badge.style.cssText = 'position:fixed;bottom:18px;right:18px;z-index:2147483647;padding:6px 12px;border-radius:999px;background:rgba(15,23,42,0.88);color:#f8fafc;font:600 12px/1.2 system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,0.22);pointer-events:none;transition:opacity .2s;';
    document.body.appendChild(badge);
  }}
  badge.textContent = next + '%';
  badge.style.opacity = '1';
  clearTimeout(window.__lilaZoomTimer);
  window.__lilaZoomTimer = setTimeout(function(){{
    if (badge) badge.style.opacity = '0';
  }}, 1100);
}})({delta_js})""",
    )


def action_fullscreen(window_getter: Callable[[], Any]) -> None:
    win = window_getter()
    if win is not None and hasattr(win, "toggle_fullscreen"):
        try:
            win.toggle_fullscreen()
        except Exception:
            pass


def action_quit(window_getter: Callable[[], Any]) -> None:
    win = window_getter()
    if win is not None and hasattr(win, "destroy"):
        try:
            win.destroy()
        except Exception:
            pass


# ─── CSP-Safe Built-in Modals ─────────────────────────────────────────────────

_MODAL_STYLES = """
#lila-desktop-modal{position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;padding:20px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;--ldm-bg:#ffffff;--ldm-fg:#0f172a;--ldm-muted:#475569;--ldm-border:#e2e8f0;--ldm-soft:#f8fafc;--ldm-accent:#4f46e5;--ldm-accent-fg:#ffffff;--ldm-code:#f1f5f9;}
#lila-desktop-modal[data-lila-dm-theme="dark"]{--ldm-bg:#0f172a;--ldm-fg:#f1f5f9;--ldm-muted:#94a3b8;--ldm-border:#1e293b;--ldm-soft:#1e293b;--ldm-accent:#6366f1;--ldm-accent-fg:#ffffff;--ldm-code:#0b1220;}
.ldm-backdrop{position:absolute;inset:0;background:rgba(2,6,23,0.58);backdrop-filter:blur(4px);}
.ldm-card{position:relative;width:100%;max-height:86vh;display:flex;flex-direction:column;background:var(--ldm-bg);color:var(--ldm-fg);border:1px solid var(--ldm-border);border-radius:16px;box-shadow:0 24px 60px rgba(0,0,0,0.32);overflow:hidden;}
.ldm-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--ldm-border);}
.ldm-title-wrap{display:flex;align-items:center;gap:10px;min-width:0;}
.ldm-title{margin:0;font-size:17px;font-weight:700;line-height:1.25;}
.ldm-badge{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;background:var(--ldm-soft);color:var(--ldm-accent);border:1px solid var(--ldm-border);}
.ldm-close{border:1px solid var(--ldm-border);background:transparent;color:var(--ldm-muted);width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:18px;line-height:1;display:inline-flex;align-items:center;justify-content:center;}
.ldm-close:hover{background:var(--ldm-soft);color:var(--ldm-fg);}
.ldm-body{padding:20px;overflow-y:auto;font-size:14px;line-height:1.6;}
.ldm-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 20px;border-top:1px solid var(--ldm-border);background:var(--ldm-soft);flex-wrap:wrap;}
.ldm-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:7px 14px;border-radius:8px;border:1px solid var(--ldm-border);background:var(--ldm-bg);color:var(--ldm-fg);font-size:13px;font-weight:600;cursor:pointer;}
.ldm-btn:hover{background:var(--ldm-soft);}
.ldm-btn-primary{background:var(--ldm-accent);color:var(--ldm-accent-fg);border-color:transparent;}
.ldm-btn-primary:hover{filter:brightness(1.06);background:var(--ldm-accent);}
.ldm-btn[data-active="true"]{background:var(--ldm-accent);color:var(--ldm-accent-fg);border-color:transparent;}
.ldm-btn:disabled{opacity:0.55;cursor:not-allowed;}
.ldm-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--ldm-border);}
.ldm-row:last-child{border-bottom:none;}
.ldm-label{color:var(--ldm-muted);font-size:13px;font-weight:500;}
.ldm-value{font-size:13px;font-weight:600;text-align:right;word-break:break-word;}
.ldm-tabs{display:inline-flex;gap:4px;padding:3px;border-radius:10px;background:var(--ldm-soft);border:1px solid var(--ldm-border);}
.ldm-tab{border:none;background:transparent;color:var(--ldm-muted);padding:5px 12px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;}
.ldm-tab[data-active="true"]{background:var(--ldm-bg);color:var(--ldm-fg);box-shadow:0 1px 3px rgba(0,0,0,0.1);}
.ldm-editor{width:100%;min-height:320px;box-sizing:border-box;padding:14px;border-radius:10px;border:1px solid var(--ldm-border);background:var(--ldm-soft);color:var(--ldm-fg);font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:13px;line-height:1.55;resize:vertical;outline:none;}
.ldm-editor:focus{border-color:var(--ldm-accent);}
.ldm-empty{padding:36px 20px;text-align:center;color:var(--ldm-muted);border:1px dashed var(--ldm-border);border-radius:12px;background:var(--ldm-soft);}
.ldm-md h1,.ldm-md h2,.ldm-md h3,.ldm-md h4{margin:1.1em 0 .45em;font-weight:700;line-height:1.3;}
.ldm-md h1:first-child,.ldm-md h2:first-child,.ldm-md p:first-child{margin-top:0;}
.ldm-md h1{font-size:1.45em;border-bottom:1px solid var(--ldm-border);padding-bottom:6px;}
.ldm-md h2{font-size:1.22em;}
.ldm-md h3{font-size:1.08em;}
.ldm-md p{margin:.65em 0;}
.ldm-md ul,.ldm-md ol{margin:.65em 0;padding-left:1.5em;}
.ldm-md li{margin:.25em 0;}
.ldm-md blockquote{margin:.8em 0;padding:8px 14px;border-left:3px solid var(--ldm-accent);background:var(--ldm-soft);color:var(--ldm-muted);border-radius:0 8px 8px 0;}
.ldm-md code{padding:2px 6px;border-radius:5px;background:var(--ldm-code);font-family:ui-monospace,Consolas,monospace;font-size:0.9em;}
.ldm-md pre{margin:.8em 0;padding:12px 14px;border-radius:10px;background:var(--ldm-code);border:1px solid var(--ldm-border);overflow-x:auto;}
.ldm-md pre code{padding:0;background:transparent;}
.ldm-md table{width:100%;border-collapse:collapse;margin:.8em 0;font-size:13px;}
.ldm-md th,.ldm-md td{padding:8px 10px;border:1px solid var(--ldm-border);text-align:left;}
.ldm-md th{background:var(--ldm-soft);font-weight:600;}
.ldm-md hr{border:none;border-top:1px solid var(--ldm-border);margin:1.2em 0;}
.ldm-md a{color:var(--ldm-accent);text-decoration:underline;}
"""

_MODAL_BOOT_JS = f"""(function(){{
  if (window.__lilaDesktopModal) return window.__lilaDesktopModal;
  function ensureStyle() {{
    if (document.getElementById('lila-desktop-modal-style')) return;
    try {{
      var s = document.createElement('style');
      s.id = 'lila-desktop-modal-style';
      s.textContent = {json.dumps(_MODAL_STYLES)};
      (document.head || document.documentElement).appendChild(s);
    }} catch (_) {{}}
  }}
  function isDark() {{
    var d = document.documentElement;
    if (d.getAttribute('data-theme') === 'dark' || d.classList.contains('dark')) return true;
    if (d.getAttribute('data-theme') === 'light') return false;
    try {{ return window.matchMedia('(prefers-color-scheme: dark)').matches; }} catch (_) {{ return false; }}
  }}
  function close() {{
    var existing = document.getElementById('lila-desktop-modal');
    if (existing) existing.remove();
    if (window.__lilaEscHandler) {{
      document.removeEventListener('keydown', window.__lilaEscHandler);
      window.__lilaEscHandler = null;
    }}
  }}
  function open(opts) {{
    ensureStyle();
    close();
    var root = document.createElement('div');
    root.id = 'lila-desktop-modal';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('data-lila-dm-theme', isDark() ? 'dark' : 'light');

    var backdrop = document.createElement('div');
    backdrop.className = 'ldm-backdrop';
    backdrop.addEventListener('click', close);

    var card = document.createElement('div');
    card.className = 'ldm-card';
    card.style.maxWidth = opts.maxWidth || '520px';

    var header = document.createElement('div');
    header.className = 'ldm-header';

    var titleWrap = document.createElement('div');
    titleWrap.className = 'ldm-title-wrap';
    var h2 = document.createElement('h2');
    h2.className = 'ldm-title';
    h2.textContent = opts.title || '';
    titleWrap.appendChild(h2);
    if (opts.badge) {{
      var badge = document.createElement('span');
      badge.className = 'ldm-badge';
      badge.textContent = opts.badge;
      titleWrap.appendChild(badge);
    }}
    if (opts.headerExtra) titleWrap.appendChild(opts.headerExtra);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'ldm-close';
    closeBtn.setAttribute('aria-label', opts.closeLabel || 'Close');
    closeBtn.textContent = '\\u00d7';
    closeBtn.addEventListener('click', close);

    header.appendChild(titleWrap);
    header.appendChild(closeBtn);

    var body = document.createElement('div');
    body.className = 'ldm-body';

    card.appendChild(header);
    card.appendChild(body);

    var footer = null;
    if (opts.withFooter !== false) {{
      footer = document.createElement('div');
      footer.className = 'ldm-footer';
      card.appendChild(footer);
    }}

    root.appendChild(backdrop);
    root.appendChild(card);
    document.body.appendChild(root);

    window.__lilaEscHandler = function(ev) {{
      if (ev.key === 'Escape') close();
    }};
    document.addEventListener('keydown', window.__lilaEscHandler);
    closeBtn.focus();
    return {{ root: root, card: card, body: body, footer: footer, close: close, syncTheme: function() {{
      root.setAttribute('data-lila-dm-theme', isDark() ? 'dark' : 'light');
    }} }};
  }}
  window.__lilaDesktopModal = {{ open: open, close: close }};
  return window.__lilaDesktopModal;
}})()"""


def _about_payload(config: DesktopMenuConfig) -> Dict[str, Any]:
    import lila

    labels = get_menu_labels(config.lang)
    return {
        "app_name": config.app_name,
        "version": config.app_version,
        "description": config.description,
        "author": config.author,
        "about_text": config.about_text,
        "os": f"{platform.system()} {platform.release()}",
        "platform": {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"),
        "lila_version": getattr(lila, "__version__", ""),
        "labels": labels,
    }


def open_about_modal(window: Any, config: Optional[DesktopMenuConfig] = None) -> None:
    cfg = config or DesktopMenuConfig.from_env()
    payload = _about_payload(cfg)
    if _dispatch_custom_event(window, "lila:desktop-about", payload):
        return
    script = f"""(function(data){{
  var M = {_MODAL_BOOT_JS};
  var L = data.labels;
  var dlg = M.open({{ title: L.about_title + ' ' + data.app_name, badge: 'v' + (data.version || '1.0.0'), closeLabel: L.close, maxWidth: '480px' }});
  if (data.description) {{
    var desc = document.createElement('p');
    desc.style.cssText = 'margin:0 0 12px;color:var(--ldm-muted)';
    desc.textContent = data.description;
    dlg.body.appendChild(desc);
  }}
  if (data.about_text) {{
    var custom = document.createElement('p');
    custom.style.cssText = 'margin:0 0 14px;white-space:pre-wrap';
    custom.textContent = data.about_text;
    dlg.body.appendChild(custom);
  }}
  var rows = [
    [L.version, 'v' + (data.version || '1.0.0')],
    [L.platform, data.os || data.platform],
    [L.lila_version, data.lila_version ? 'v' + data.lila_version : 'Lila']
  ];
  if (data.author) rows.push([L.author, data.author]);
  rows.forEach(function(item) {{
    var row = document.createElement('div');
    row.className = 'ldm-row';
    var k = document.createElement('span'); k.className = 'ldm-label'; k.textContent = item[0];
    var v = document.createElement('span'); v.className = 'ldm-value'; v.textContent = item[1];
    row.appendChild(k); row.appendChild(v);
    dlg.body.appendChild(row);
  }});
  var copyBtn = document.createElement('button');
  copyBtn.type = 'button';
  copyBtn.className = 'ldm-btn';
  copyBtn.textContent = L.copy_system_info;
  copyBtn.addEventListener('click', function() {{
    var summary = data.app_name + ' v' + (data.version || '1.0.0') + ' | ' + (data.os || data.platform) + ' | Lila v' + (data.lila_version || '');
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_clipboard) {{
      window.pywebview.api.set_clipboard(summary);
    }} else if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(summary).catch(function(){{}});
    }}
    copyBtn.textContent = L.copied;
    setTimeout(function() {{ copyBtn.textContent = L.copy_system_info; }}, 1500);
  }});
  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'ldm-btn ldm-btn-primary';
  closeBtn.textContent = L.close;
  closeBtn.addEventListener('click', dlg.close);
  dlg.footer.appendChild(copyBtn);
  dlg.footer.appendChild(closeBtn);
}})({json.dumps(payload)})"""
    _run_js(window, script)


def open_preferences_modal(window: Any, config: Optional[DesktopMenuConfig] = None) -> None:
    cfg = config or DesktopMenuConfig.from_env()
    labels = get_menu_labels(cfg.lang)
    payload = {
        "app_name": cfg.app_name,
        "preferences_url": cfg.preferences_url,
        "data_dir": get_data_path(),
        "labels": labels,
    }
    if _dispatch_custom_event(window, "lila:desktop-preferences", payload):
        return
    if cfg.preferences_url:
        _run_js(window, f"window.location.href = {json.dumps(cfg.preferences_url)};")
        return

    script = f"""(function(data){{
  var M = {_MODAL_BOOT_JS};
  var L = data.labels;
  var dlg = M.open({{ title: L.preferences_title, closeLabel: L.close, maxWidth: '500px' }});

  // Theme row
  var themeRow = document.createElement('div');
  themeRow.className = 'ldm-row';
  var tLbl = document.createElement('span'); tLbl.className = 'ldm-label'; tLbl.textContent = L.theme;
  var tGrp = document.createElement('div'); tGrp.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap';
  var curTheme = localStorage.getItem('lila-theme') || 'system';
  var tButtons = [];
  function applyTheme(mode) {{
    localStorage.setItem('lila-theme', mode);
    var isDark = mode === 'dark' || (mode === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', isDark);
    window.dispatchEvent(new CustomEvent('lila:theme-change', {{ detail: {{ theme: mode, resolved: isDark ? 'dark' : 'light' }} }}));
    tButtons.forEach(function(item) {{ item.btn.setAttribute('data-active', item.mode === mode ? 'true' : 'false'); }});
    dlg.syncTheme();
  }}
  [['light', L.theme_light], ['dark', L.theme_dark], ['system', L.theme_system]].forEach(function(pair) {{
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'ldm-btn';
    b.textContent = pair[1];
    b.setAttribute('data-active', curTheme === pair[0] ? 'true' : 'false');
    b.addEventListener('click', function() {{ applyTheme(pair[0]); }});
    tButtons.push({{ mode: pair[0], btn: b }});
    tGrp.appendChild(b);
  }});
  themeRow.appendChild(tLbl); themeRow.appendChild(tGrp);
  dlg.body.appendChild(themeRow);

  // Zoom row
  var zoomRow = document.createElement('div');
  zoomRow.className = 'ldm-row';
  var zLbl = document.createElement('span'); zLbl.className = 'ldm-label'; zLbl.textContent = L.zoom;
  var zGrp = document.createElement('div'); zGrp.style.cssText = 'display:flex;gap:6px;align-items:center';
  function curZoom() {{
    var n = parseInt(localStorage.getItem('lila-desktop-zoom') || '100', 10);
    return (isNaN(n) || n < 50 || n > 200) ? 100 : n;
  }}
  var zReset = document.createElement('button'); zReset.type = 'button'; zReset.className = 'ldm-btn'; zReset.textContent = curZoom() + '%';
  function setZoom(val) {{
    var next = Math.max(50, Math.min(200, val));
    localStorage.setItem('lila-desktop-zoom', String(next));
    document.documentElement.style.zoom = (next / 100).toFixed(2);
    zReset.textContent = next + '%';
  }}
  var zOut = document.createElement('button'); zOut.type = 'button'; zOut.className = 'ldm-btn'; zOut.textContent = '-';
  zOut.addEventListener('click', function() {{ setZoom(curZoom() - 10); }});
  zReset.addEventListener('click', function() {{ setZoom(100); }});
  var zIn = document.createElement('button'); zIn.type = 'button'; zIn.className = 'ldm-btn'; zIn.textContent = '+';
  zIn.addEventListener('click', function() {{ setZoom(curZoom() + 10); }});
  zGrp.appendChild(zOut); zGrp.appendChild(zReset); zGrp.appendChild(zIn);
  zoomRow.appendChild(zLbl); zoomRow.appendChild(zGrp);
  dlg.body.appendChild(zoomRow);

  // Data folder row
  var dirRow = document.createElement('div');
  dirRow.className = 'ldm-row';
  var dLbl = document.createElement('span'); dLbl.className = 'ldm-label'; dLbl.textContent = L.data_folder;
  var dVal = document.createElement('span'); dVal.className = 'ldm-value'; dVal.style.fontFamily = 'ui-monospace,Consolas,monospace'; dVal.style.fontSize = '12px'; dVal.textContent = data.data_dir;
  dirRow.appendChild(dLbl); dirRow.appendChild(dVal);
  dlg.body.appendChild(dirRow);

  var openDirBtn = document.createElement('button');
  openDirBtn.type = 'button';
  openDirBtn.className = 'ldm-btn';
  openDirBtn.textContent = L.open_folder;
  openDirBtn.addEventListener('click', function() {{
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_data_dir) {{
      window.pywebview.api.open_data_dir();
    }}
  }});
  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'ldm-btn ldm-btn-primary';
  closeBtn.textContent = L.close;
  closeBtn.addEventListener('click', dlg.close);
  dlg.footer.appendChild(openDirBtn);
  dlg.footer.appendChild(closeBtn);
}})({json.dumps(payload)})"""
    _run_js(window, script)


def open_help_modal(window: Any, config: Optional[DesktopMenuConfig] = None) -> None:
    cfg = config or DesktopMenuConfig.from_env()
    labels = get_menu_labels(cfg.lang)
    manual = read_help_manual(cfg.help_file)
    payload = {
        "app_name": cfg.app_name,
        "manual": manual,
        "labels": labels,
    }
    if _dispatch_custom_event(window, "lila:desktop-help", payload):
        return

    script = f"""(function(data){{
  var M = {_MODAL_BOOT_JS};
  var L = data.labels;
  var state = data.manual;
  var activeTab = 'view';

  var tabs = null;
  var viewTab = null;
  var editTab = null;
  if (state.editable) {{
    tabs = document.createElement('div');
    tabs.className = 'ldm-tabs';
    viewTab = document.createElement('button'); viewTab.type = 'button'; viewTab.className = 'ldm-tab'; viewTab.textContent = L.view;
    editTab = document.createElement('button'); editTab.type = 'button'; editTab.className = 'ldm-tab'; editTab.textContent = L.edit;
    tabs.appendChild(viewTab);
    tabs.appendChild(editTab);
  }}

  var dlg = M.open({{ title: L.manual_title, headerExtra: tabs, closeLabel: L.close, maxWidth: '820px' }});
  var viewPane = document.createElement('div');
  var editPane = document.createElement('div');
  editPane.style.display = 'none';

  var mdWrap = document.createElement('div');
  mdWrap.className = 'ldm-md';
  mdWrap.addEventListener('click', function(ev) {{
    var a = ev.target && ev.target.closest ? ev.target.closest('a') : null;
    if (!a) return;
    if (a.getAttribute('data-lila-external') === '1' && window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {{
      ev.preventDefault();
      window.pywebview.api.open_external(a.href);
    }}
  }});

  var textarea = document.createElement('textarea');
  textarea.className = 'ldm-editor';
  textarea.placeholder = L.markdown_placeholder;
  textarea.value = state.markdown || '';

  var stats = document.createElement('div');
  stats.style.cssText = 'margin-top:8px;font-size:12px;color:var(--ldm-muted);display:flex;justify-content:space-between;gap:12px';
  var countEl = document.createElement('span');
  var statusEl = document.createElement('span');
  stats.appendChild(countEl);
  stats.appendChild(statusEl);

  function updateCounts() {{
    var val = textarea.value || '';
    var lines = val ? val.split('\\n').length : 0;
    countEl.textContent = val.length + ' ' + L.manual_characters + ' · ' + lines + ' ' + L.manual_lines;
  }}
  textarea.addEventListener('input', function() {{
    updateCounts();
    statusEl.textContent = (textarea.value !== (state.markdown || '')) ? L.unsaved_changes : '';
  }});

  editPane.appendChild(textarea);
  editPane.appendChild(stats);
  dlg.body.appendChild(viewPane);
  dlg.body.appendChild(editPane);

  var leftFooter = document.createElement('div');
  leftFooter.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap';
  var rightFooter = document.createElement('div');
  rightFooter.style.cssText = 'display:flex;gap:8px;align-items:center';
  dlg.footer.appendChild(leftFooter);
  dlg.footer.appendChild(rightFooter);

  var saveBtn = null;
  var resetBtn = null;
  if (state.editable) {{
    saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'ldm-btn ldm-btn-primary';
    saveBtn.textContent = L.save;
    saveBtn.style.display = 'none';
    saveBtn.addEventListener('click', function() {{
      if (!(window.pywebview && window.pywebview.api && window.pywebview.api.save_help_manual)) return;
      saveBtn.disabled = true;
      saveBtn.textContent = L.saving;
      window.pywebview.api.save_help_manual(textarea.value).then(function(res) {{
        saveBtn.disabled = false;
        saveBtn.textContent = L.save;
        if (res && res.ok) {{
          state = res;
          textarea.value = res.markdown || '';
          statusEl.textContent = L.saved;
          renderView();
          setTab('view');
        }} else {{
          statusEl.textContent = (res && res.reason) ? (L.save_error + ': ' + res.reason) : L.save_error;
        }}
      }}).catch(function() {{
        saveBtn.disabled = false;
        saveBtn.textContent = L.save;
        statusEl.textContent = L.save_error;
      }});
    }});

    resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'ldm-btn';
    resetBtn.textContent = L.reset_original;
    resetBtn.style.display = (state.has_override && state.has_bundled) ? 'inline-flex' : 'none';
    resetBtn.addEventListener('click', function() {{
      if (!(window.pywebview && window.pywebview.api && window.pywebview.api.reset_help_manual)) return;
      window.pywebview.api.reset_help_manual().then(function(res) {{
        if (res && res.ok) {{
          state = res;
          textarea.value = res.markdown || '';
          statusEl.textContent = '';
          updateCounts();
          renderView();
        }}
      }});
    }});
    leftFooter.appendChild(saveBtn);
    leftFooter.appendChild(resetBtn);
  }}

  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'ldm-btn';
  closeBtn.textContent = L.close;
  closeBtn.addEventListener('click', dlg.close);
  rightFooter.appendChild(closeBtn);

  function renderView() {{
    viewPane.innerHTML = '';
    if (state.is_empty || !state.html) {{
      var empty = document.createElement('div');
      empty.className = 'ldm-empty';
      var p = document.createElement('p');
      p.style.margin = '0 0 12px';
      p.textContent = state.editable ? L.empty_manual_hint : L.empty_manual_readonly;
      empty.appendChild(p);
      if (state.editable) {{
        var cta = document.createElement('button');
        cta.type = 'button';
        cta.className = 'ldm-btn ldm-btn-primary';
        cta.textContent = L.edit_manual_cta;
        cta.addEventListener('click', function() {{ setTab('edit'); }});
        empty.appendChild(cta);
      }}
      viewPane.appendChild(empty);
    }} else {{
      mdWrap.innerHTML = state.html;
      viewPane.appendChild(mdWrap);
    }}
    if (resetBtn) {{
      resetBtn.style.display = (state.has_override && state.has_bundled) ? 'inline-flex' : 'none';
    }}
  }}

  function setTab(name) {{
    activeTab = name;
    viewPane.style.display = name === 'view' ? 'block' : 'none';
    editPane.style.display = name === 'edit' ? 'block' : 'none';
    if (viewTab && editTab) {{
      viewTab.setAttribute('data-active', name === 'view' ? 'true' : 'false');
      editTab.setAttribute('data-active', name === 'edit' ? 'true' : 'false');
    }}
    if (saveBtn) saveBtn.style.display = name === 'edit' ? 'inline-flex' : 'none';
    if (name === 'edit') {{
      updateCounts();
      textarea.focus();
    }}
  }}

  if (viewTab && editTab) {{
    viewTab.addEventListener('click', function() {{ setTab('view'); }});
    editTab.addEventListener('click', function() {{ setTab('edit'); }});
  }}

  renderView();
  setTab('view');
}})({json.dumps(payload)})"""
    _run_js(window, script)


def open_updates_modal(window: Any, config: Optional[DesktopMenuConfig] = None) -> None:
    cfg = config or DesktopMenuConfig.from_env()
    labels = get_menu_labels(cfg.lang)
    payload = {"app_name": cfg.app_name, "version": cfg.app_version, "labels": labels}
    script = f"""(function(data){{
  var M = {_MODAL_BOOT_JS};
  var L = data.labels;
  var dlg = M.open({{ title: L.updates_title, badge: 'v' + (data.version || '1.0.0'), closeLabel: L.close, maxWidth: '460px' }});
  var box = document.createElement('div');
  box.textContent = L.checking_updates;
  dlg.body.appendChild(box);

  var installBtn = document.createElement('button');
  installBtn.type = 'button';
  installBtn.className = 'ldm-btn ldm-btn-primary';
  installBtn.textContent = L.install_update;
  installBtn.style.display = 'none';
  installBtn.addEventListener('click', function() {{
    if (window.pywebview && window.pywebview.api && window.pywebview.api.install_update) {{
      installBtn.disabled = true;
      window.pywebview.api.install_update();
    }}
  }});

  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'ldm-btn';
  closeBtn.textContent = L.close;
  closeBtn.addEventListener('click', dlg.close);
  dlg.footer.appendChild(installBtn);
  dlg.footer.appendChild(closeBtn);

  function renderResult(res) {{
    box.innerHTML = '';
    if (res && res.available) {{
      var h = document.createElement('p');
      h.style.cssText = 'margin:0 0 8px;font-weight:700';
      h.textContent = L.update_available + ': v' + (res.version || '');
      box.appendChild(h);
      if (res.notes) {{
        var n = document.createElement('p');
        n.style.cssText = 'margin:0;color:var(--ldm-muted);white-space:pre-wrap';
        n.textContent = res.notes;
        box.appendChild(n);
      }}
      installBtn.style.display = 'inline-flex';
    }} else {{
      var p = document.createElement('p');
      p.style.margin = '0';
      p.textContent = (res && res.reason && res.reason !== 'no update URL configured') ? (L.up_to_date + ' (' + res.reason + ')') : L.up_to_date;
      box.appendChild(p);
    }}
  }}

  if (window.pywebview && window.pywebview.api && window.pywebview.api.check_update) {{
    window.pywebview.api.check_update().then(renderResult).catch(function() {{ renderResult(null); }});
  }} else {{
    renderResult(null);
  }}
}})({json.dumps(payload)})"""
    _run_js(window, script)


# ─── Menu Builder ─────────────────────────────────────────────────────────────

def _call_in_bg(fn: Callable[..., Any], *args: Any) -> Callable[[], None]:
    def _runner() -> None:
        try:
            fn(*args)
        except Exception:
            pass

    return _runner


def _call_win(fn: Callable[..., Any], window_getter: Callable[[], Any], *args: Any) -> Callable[[], None]:
    def _runner() -> None:
        try:
            fn(window_getter(), *args)
        except Exception:
            pass

    return _runner


def build_desktop_menu(
    window_getter: Callable[[], Any],
    config: Optional[DesktopMenuConfig] = None,
    platform_name: Optional[str] = None,
) -> list:
    """Builds the ``webview.menu.Menu`` tree (cross-platform + optional ``app.desktop_menu`` hook)."""
    from webview.menu import Menu, MenuAction, MenuSeparator  # type: ignore

    cfg = config or DesktopMenuConfig.from_env()
    if not cfg.enabled:
        return []

    labels = get_menu_labels(cfg.lang)
    plat = platform_name or sys.platform

    edit_menu = Menu(
        labels["menu_edit"],
        [
            MenuAction(labels["undo"], _call_in_bg(action_undo, window_getter)),
            MenuAction(labels["redo"], _call_in_bg(action_redo, window_getter)),
            MenuSeparator(),
            MenuAction(labels["cut"], _call_in_bg(action_cut, window_getter)),
            MenuAction(labels["copy"], _call_in_bg(action_copy, window_getter)),
            MenuAction(labels["paste"], _call_in_bg(action_paste, window_getter)),
            MenuSeparator(),
            MenuAction(labels["select_all"], _call_in_bg(action_select_all, window_getter)),
        ],
    )

    view_menu = Menu(
        labels["menu_view"],
        [
            MenuAction(labels["back"], _call_in_bg(action_back, window_getter)),
            MenuAction(labels["forward"], _call_in_bg(action_forward, window_getter)),
            MenuAction(labels["reload"], _call_in_bg(action_reload, window_getter)),
            MenuSeparator(),
            MenuAction(labels["zoom_in"], _call_in_bg(action_zoom, window_getter, 10)),
            MenuAction(labels["zoom_out"], _call_in_bg(action_zoom, window_getter, -10)),
            MenuAction(labels["zoom_reset"], _call_in_bg(action_zoom, window_getter, None)),
            MenuSeparator(),
            MenuAction(labels["fullscreen"], _call_in_bg(action_fullscreen, window_getter)),
        ],
    )

    help_items: List[Any] = [
        MenuAction(labels["manual"], _call_win(open_help_modal, window_getter, cfg)),
    ]
    if cfg.update_url:
        help_items.append(MenuAction(labels["check_updates"], _call_win(open_updates_modal, window_getter, cfg)))
    if plat != "darwin":
        help_items.append(MenuSeparator())
        help_items.append(MenuAction(labels["about_fmt"].format(app=cfg.app_name), _call_win(open_about_modal, window_getter, cfg)))

    help_menu = Menu(labels["menu_help"], help_items)

    menus: List[Any] = []
    if plat == "darwin":
        menus.append(
            Menu(
                "__app__",
                [
                    MenuAction(labels["about_fmt"].format(app=cfg.app_name), _call_win(open_about_modal, window_getter, cfg)),
                    MenuSeparator(),
                    MenuAction(labels["preferences"], _call_win(open_preferences_modal, window_getter, cfg)),
                    MenuSeparator(),
                    MenuAction(labels["quit"], _call_in_bg(action_quit, window_getter)),
                ],
            )
        )
    else:
        file_menu = Menu(
            labels["menu_file"],
            [
                MenuAction(labels["preferences"], _call_win(open_preferences_modal, window_getter, cfg)),
                MenuSeparator(),
                MenuAction(labels["quit"], _call_in_bg(action_quit, window_getter)),
            ],
        )
        menus.append(file_menu)

    menus.extend([edit_menu, view_menu, help_menu])

    # Optional user customization via app/desktop_menu.py
    try:
        user_mod = importlib.import_module("app.desktop_menu")
        if callable(getattr(user_mod, "get_menu", None)):
            return list(user_mod.get_menu(window_getter, menus, cfg))
        if callable(getattr(user_mod, "extra_menus", None)):
            extra = user_mod.extra_menus(window_getter, cfg)
            if extra:
                menus.extend(extra)
    except ModuleNotFoundError as exc:
        if exc.name not in ("app", "app.desktop_menu"):
            raise
    except Exception:
        pass

    return menus
