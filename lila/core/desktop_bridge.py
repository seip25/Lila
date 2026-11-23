"""Native bridge for desktop builds: ``window.pywebview.api`` in the page.

Used by ``lila desktop dev`` and the PyInstaller bootstrap. From React:
``desktopApi()?.notify("Saved", "Backup finished")`` (``@lila``) or the
helpers in ``@lila/desktop``. Every method returns JSON-serializable values and
never raises into the page.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
from typing import Any, Dict, Optional

ALLOWED_SCHEMES = ("https://", "http://", "mailto:")


def _windows() -> Optional[list]:
    try:
        import webview  # type: ignore

        return list(webview.windows)
    except Exception:
        return None


def parse_version(value: str) -> tuple:
    """``"1.10.2"`` > ``"1.9"``; non-numeric parts are ignored."""
    parts = []
    for chunk in str(value or "0").lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def platform_key() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def _open_url(request: urllib.request.Request, timeout: float):
    """Bypass proxy env vars when checking/downloading from localhost."""
    if request.full_url.startswith(("http://127.0.0.1", "http://localhost")):
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)  # nosec - https/loopback enforced by caller


def check_update(url: Optional[str], current: Optional[str], timeout: float = 8.0) -> Dict[str, Any]:
    """Reads the update manifest written by ``lila desktop release``::

        {"version": "1.4.0", "notes": "...", "files": {"windows": {"url": "...msi", "sha256": "..."},
                                                      "macos": {"url": "...dmg", "sha256": "..."}}}
    """
    if not url:
        return {"available": False, "reason": "no update URL configured"}
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1") and not url.startswith("http://localhost"):
        return {"available": False, "reason": "update URL must use https"}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "lila-desktop-updater"})
        with _open_url(request, timeout=timeout) as response:
            manifest = json.loads(response.read(1_000_000).decode("utf-8"))
    except Exception as exc:
        return {"available": False, "reason": f"could not read the manifest: {exc.__class__.__name__}"}
    latest = str(manifest.get("version") or "")
    entry = (manifest.get("files") or {}).get(platform_key()) or {}
    available = bool(latest) and parse_version(latest) > parse_version(current or "0") and bool(entry.get("url"))
    return {
        "available": available,
        "current": current or "",
        "version": latest,
        "notes": str(manifest.get("notes") or ""),
        "url": entry.get("url", ""),
        "sha256": entry.get("sha256", ""),
    }


def download_verified(url: str, sha256: str, timeout: float = 120.0) -> str:
    """Downloads the installer to a temp file and checks its SHA-256."""
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise ValueError("installer URL must use https")
    if not sha256 or len(sha256) != 64:
        raise ValueError("missing sha256 in the update manifest")
    suffix = os.path.splitext(url.split("?", 1)[0])[1] or ".bin"
    fd, path = tempfile.mkstemp(prefix="lila-update-", suffix=suffix)
    digest = hashlib.sha256()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "lila-desktop-updater"})
        with _open_url(request, timeout=timeout) as response, os.fdopen(fd, "wb") as fh:
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                digest.update(chunk)
                fh.write(chunk)
    except Exception:
        os.unlink(path)
        raise
    if digest.hexdigest().lower() != sha256.lower():
        os.unlink(path)
        raise ValueError("checksum mismatch: the download was not installed")
    return path


def _open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def notify(title: str, message: str = "") -> bool:
    """Native notification (macOS osascript, Linux notify-send, Windows tray balloon)."""
    title = str(title or "")[:120]
    message = str(message or "")[:400]
    try:
        if sys.platform == "darwin":
            script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
            subprocess.Popen(["osascript", "-e", script])
            return True
        if sys.platform == "win32":
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
                f"$n.ShowBalloonTip(5000,{json.dumps(title)},{json.dumps(message or ' ')},'Info');"
                "Start-Sleep -s 6;$n.Dispose()"
            )
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        subprocess.Popen(["notify-send", title, message])
        return True
    except Exception:
        return False


class DesktopBridge:
    """Exposed to JavaScript as ``window.pywebview.api``."""

    def open_file_dialog(self, title: str = "Open File", file_types: Optional[list] = None) -> Optional[str]:
        try:
            import webview  # type: ignore

            windows = _windows()
            if windows:
                res = windows[0].create_file_dialog(webview.OPEN_DIALOG, title=title,
                                                    file_types=tuple(file_types or ["All files (*.*)"]))
                return res[0] if res else None
        except Exception:
            return None
        return None

    def save_file_dialog(self, title: str = "Save File As", default_filename: str = "") -> Optional[str]:
        try:
            import webview  # type: ignore

            windows = _windows()
            if windows:
                res = windows[0].create_file_dialog(webview.SAVE_DIALOG, title=title, save_filename=default_filename)
                return res if isinstance(res, str) else (res[0] if res else None)
        except Exception:
            return None
        return None

    def select_folder_dialog(self, title: str = "Select Folder") -> Optional[str]:
        try:
            import webview  # type: ignore

            windows = _windows()
            if windows:
                res = windows[0].create_file_dialog(webview.FOLDER_DIALOG, title=title)
                return res[0] if res else None
        except Exception:
            return None
        return None

    def get_system_metrics(self) -> dict:
        from lila.core.debug import get_system_metrics

        return get_system_metrics()

    def notify(self, title: str, message: str = "") -> bool:
        return notify(title, message)

    def open_external(self, url: str) -> bool:
        """Opens http(s)/mailto links in the system browser (never file:// or javascript:)."""
        url = str(url or "")
        if not url.startswith(ALLOWED_SCHEMES):
            return False
        import webbrowser

        return bool(webbrowser.open(url))

    def app_info(self) -> dict:
        import lila
        from lila.core.config import ENV_CONFIG, get_data_path

        return {
            "name": os.environ.get("TITLE_PROJECT") or ENV_CONFIG.get("TITLE_PROJECT", ""),
            "version": os.environ.get("LILA_APP_VERSION") or ENV_CONFIG.get("VERSION_PROJECT", ""),
            "description": os.environ.get("DESCRIPTION_PROJECT") or ENV_CONFIG.get("DESCRIPTION_PROJECT", ""),
            "author": os.environ.get("AUTHOR_DEFAULT") or ENV_CONFIG.get("AUTHOR_DEFAULT", ""),
            "lila_version": getattr(lila, "__version__", ""),
            "platform": platform_key(),
            "os": f"{platform.system()} {platform.release()}",
            "frozen": bool(getattr(sys, "frozen", False)),
            "data_dir": get_data_path(),
        }

    def check_update(self) -> dict:
        return check_update(os.environ.get("LILA_UPDATE_URL"), os.environ.get("LILA_APP_VERSION"))

    def install_update(self) -> dict:
        """Downloads (SHA-256 checked) and opens the new installer, then closes the app."""
        info = self.check_update()
        if not info.get("available"):
            return {"ok": False, "reason": info.get("reason") or "already up to date"}
        try:
            path = download_verified(info["url"], info.get("sha256", ""))
            _open_path(path)
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}
        windows = _windows()
        if windows:
            try:
                windows[0].destroy()
            except Exception:
                pass
        return {"ok": True, "version": info["version"]}

    def set_title(self, title: str) -> bool:
        windows = _windows()
        if not windows:
            return False
        try:
            windows[0].set_title(str(title)[:200])
            return True
        except Exception:
            return False

    def get_help_manual(self) -> dict:
        try:
            from lila.core.desktop_menu import read_help_manual

            return read_help_manual()
        except Exception as exc:
            return {"markdown": "", "html": "", "is_empty": True, "editable": False, "reason": str(exc)}

    def save_help_manual(self, content: str) -> dict:
        try:
            from lila.core.desktop_menu import save_help_manual

            return save_help_manual(content)
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    def reset_help_manual(self) -> dict:
        try:
            from lila.core.desktop_menu import reset_help_manual

            return reset_help_manual()
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    def open_data_dir(self) -> bool:
        try:
            from lila.core.config import get_data_path

            data_dir = get_data_path()
            os.makedirs(data_dir, exist_ok=True)
            _open_path(data_dir)
            return True
        except Exception:
            return False

    def open_help(self) -> bool:
        windows = _windows()
        if not windows:
            return False
        try:
            from lila.core.desktop_menu import DesktopMenuConfig, open_help_modal

            open_help_modal(windows[0], DesktopMenuConfig.from_env())
            return True
        except Exception:
            return False

    def open_about(self) -> bool:
        windows = _windows()
        if not windows:
            return False
        try:
            from lila.core.desktop_menu import DesktopMenuConfig, open_about_modal

            open_about_modal(windows[0], DesktopMenuConfig.from_env())
            return True
        except Exception:
            return False

    def open_preferences(self) -> bool:
        windows = _windows()
        if not windows:
            return False
        try:
            from lila.core.desktop_menu import DesktopMenuConfig, open_preferences_modal

            open_preferences_modal(windows[0], DesktopMenuConfig.from_env())
            return True
        except Exception:
            return False

    def get_clipboard(self) -> str:
        try:
            from lila.core.desktop_menu import get_clipboard_text

            return get_clipboard_text()
        except Exception:
            return ""

    def set_clipboard(self, text: str) -> bool:
        try:
            from lila.core.desktop_menu import set_clipboard_text

            return bool(set_clipboard_text(text))
        except Exception:
            return False

    def get_report_settings(self) -> dict:
        try:
            from lila.core.desktop_reports import get_report_settings

            return get_report_settings()
        except Exception as exc:
            return {"configured": False, "anonymous_telemetry": False, "reason": str(exc)}

    def set_telemetry_opt_in(self, enabled: bool) -> dict:
        try:
            from lila.core.desktop_reports import set_telemetry_opt_in

            return set_telemetry_opt_in(bool(enabled))
        except Exception as exc:
            return {"configured": False, "anonymous_telemetry": False, "reason": str(exc)}

    def send_bug_report(self, note: str = "", include_logs: bool = True) -> dict:
        try:
            from lila.core.desktop_reports import send_bug_report

            return send_bug_report(note=note, include_logs=bool(include_logs))
        except Exception as exc:
            return {"ok": False, "status": "error", "reason": str(exc)}

    def send_telemetry_now(self) -> dict:
        try:
            from lila.core.desktop_reports import send_anonymous_telemetry

            return send_anonymous_telemetry(force=True)
        except Exception as exc:
            return {"ok": False, "status": "error", "reason": str(exc)}

    def open_bug_report(self) -> bool:
        windows = _windows()
        if not windows:
            return False
        try:
            from lila.core.desktop_menu import DesktopMenuConfig, open_bug_report_modal

            open_bug_report_modal(windows[0], DesktopMenuConfig.from_env())
            return True
        except Exception:
            return False

    def create_backup(self, compress: bool = False) -> dict:
        try:
            from lila.cli.backup import run_sqlite_backup

            res = run_sqlite_backup(compress=bool(compress))
            return {"ok": True, "path": res.get("destination"), **res}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    def lan_status(self) -> dict:
        try:
            from lila.core.desktop_lan import lan_status

            return lan_status()
        except Exception as exc:
            return {"running": False, "reason": str(exc)}

    def start_lan(self, port: Optional[int] = None, otp_ttl: Optional[int] = None) -> dict:
        try:
            from lila.core.desktop_lan import start_lan_gateway

            return start_lan_gateway(port=port, otp_ttl=otp_ttl)
        except Exception as exc:
            return {"running": False, "reason": str(exc)}

    def stop_lan(self) -> dict:
        try:
            from lila.core.desktop_lan import stop_lan_gateway

            return stop_lan_gateway()
        except Exception as exc:
            return {"running": False, "reason": str(exc)}

    def rotate_lan_otp(self, ttl: Optional[int] = None) -> dict:
        try:
            from lila.core.desktop_lan import rotate_lan_otp

            return rotate_lan_otp(ttl=ttl)
        except Exception as exc:
            return {"running": False, "reason": str(exc)}

    def revoke_lan_sessions(self) -> dict:
        try:
            from lila.core.desktop_lan import revoke_lan_sessions

            return revoke_lan_sessions()
        except Exception as exc:
            return {"revoked": 0, "running": False, "reason": str(exc)}
