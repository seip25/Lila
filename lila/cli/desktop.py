import os
import sys
import time
import socket
import threading
import subprocess
import shutil
import tempfile
import secrets
import typer
from typing import Optional, Any, List

app = typer.Typer(help="Lila Desktop CLI - Run and bundle full-stack Python apps as native desktop applications.")

class DesktopBridge:
    """Exposes native OS capabilities to JavaScript in pywebview via window.pywebview.api."""

    def open_file_dialog(self, title: str = "Open File", file_types: Optional[list] = None) -> Optional[str]:
        """Opens native file picker dialog."""
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(
                    webview.OPEN_DIALOG,
                    title=title,
                    file_types=tuple(file_types or ["All files (*.*)"]),
                )
                return res[0] if res else None
        except Exception:
            return None
        return None

    def save_file_dialog(self, title: str = "Save File As", default_filename: str = "") -> Optional[str]:
        """Opens native save file dialog."""
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(
                    webview.SAVE_DIALOG,
                    title=title,
                    save_filename=default_filename,
                )
                return res if isinstance(res, str) else (res[0] if res else None)
        except Exception:
            return None
        return None

    def select_folder_dialog(self, title: str = "Select Folder") -> Optional[str]:
        """Opens native directory picker dialog."""
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(
                    webview.FOLDER_DIALOG,
                    title=title,
                )
                return res[0] if res else None
        except Exception:
            return None
        return None

    def get_system_metrics(self) -> dict:
        """Returns live process and system telemetry."""
        from lila.core.debug import get_system_metrics
        return get_system_metrics()


def acquire_single_instance_lock(app_name: str) -> Optional[Any]:
    """Ensures only one instance of the desktop application runs at a time."""
    clean_name = "".join(c for c in app_name if c.isalnum() or c in ("_", "-")) or "LilaDesktop"
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            mutex = ctypes.windll.kernel32.CreateMutexW(None, True, f"Local\\LilaDesktop_{clean_name}")
            last_err = ctypes.windll.kernel32.GetLastError()
            if last_err == 183:  # ERROR_ALREADY_EXISTS
                return None
            return mutex
        except Exception:
            return True
    else:
        try:
            import fcntl
            lock_path = os.path.join(tempfile.gettempdir(), f"lila_{clean_name}.lock")
            lock_fd = open(lock_path, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except (IOError, OSError):
            return None


def find_free_port(preferred_port: int = 8000) -> int:
    """Finds a free port on 127.0.0.1 starting with the preferred port."""
    if preferred_port > 0:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", preferred_port))
                return preferred_port
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(host: str, port: int, timeout: float = 10.0, error_holder: Optional[list] = None) -> bool:
    """Polls host:port until it accepts TCP connections."""
    start = time.time()
    while time.time() - start < timeout:
        if error_holder:
            return False
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except (socket.error, ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def run_uvicorn_thread(host: str, port: int, server_holder: list, error_holder: list):
    """Runs uvicorn in a background thread with signal handlers disabled."""
    try:
        cwd = os.getcwd()
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
        elif sys.path[0] != cwd:
            sys.path.remove(cwd)
            sys.path.insert(0, cwd)

        import uvicorn
        import main as app_module

        config = uvicorn.Config(
            app_module.app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            reload=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server_holder.append(server)
        server.run()
    except Exception as exc:
        error_holder.append(exc)


def launch_native_browser(url: str, width: int = 1200, height: int = 800) -> Optional[subprocess.Popen]:
    """Fallback mode: launches Edge, Chrome, or Brave in standalone app mode."""
    candidates = []
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            "msedge",
            "chrome",
            "brave"
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        ]
    else:
        candidates = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"]

    executable = None
    for cand in candidates:
        if os.path.isabs(cand) and os.path.isfile(cand):
            executable = cand
            break
        elif shutil.which(cand):
            executable = shutil.which(cand)
            break

    if not executable:
        return None

    user_data_dir = os.path.join(tempfile.gettempdir(), f"lila_desktop_{int(time.time())}")
    cmd = [
        executable,
        f"--app={url}",
        f"--window-size={width},{height}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    return subprocess.Popen(cmd)


def _load_project_routes(patterns: List[str]):
    """Imports main:app in desktop mode and returns ``(all_routes, statuses)``."""
    import importlib
    from lila.core import desktop as desktop_mod

    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    previous = os.environ.get("LILA_DESKTOP")
    os.environ["LILA_DESKTOP"] = "1"
    try:
        module = sys.modules.get("main") or importlib.import_module("main")
    finally:
        if previous is None:
            os.environ.pop("LILA_DESKTOP", None)
        else:
            os.environ["LILA_DESKTOP"] = previous
    app_obj = getattr(module, "app", None)
    routes = list(getattr(app_obj, "_lila_all_routes", None) or getattr(app_obj, "routes", []))
    all_patterns = list(dict.fromkeys(desktop_mod.exclude_patterns() + list(patterns)))
    statuses = []
    for route in routes:
        path = getattr(route, "path", "")
        if not path:
            continue
        enabled, reason = desktop_mod.route_status(route, desktop=True, patterns=all_patterns)
        methods = getattr(route, "methods", None)
        kind = ",".join(sorted(m for m in methods if m != "HEAD")) if methods else type(route).__name__.replace("Route", "") or "MOUNT"
        statuses.append((path, kind, enabled, reason))
    return routes, statuses


def _resolve_patterns(exclude: Optional[List[str]], auto_exclude: bool, routes=None) -> List[str]:
    from lila.core import desktop as desktop_mod

    patterns: List[str] = []
    for item in exclude or []:
        patterns.extend(p.strip() for p in str(item).split(",") if p.strip())
    if auto_exclude:
        if routes is None:
            try:
                routes, _ = _load_project_routes(patterns)
            except Exception as exc:
                typer.secho(f"⚠️ Could not inspect routes for --auto-exclude: {exc}", fg=typer.colors.YELLOW)
                routes = []
        for path, reason in desktop_mod.suggest_exclusions(routes):
            typer.echo(f"   auto-exclude {path} ({reason})")
            patterns.append(path)
    return list(dict.fromkeys(patterns))


def _print_route_table(statuses) -> None:
    kept = [s for s in statuses if s[2]]
    removed = [s for s in statuses if not s[2]]
    for path, kind, _enabled, reason in sorted(kept):
        typer.secho(f"  ✅ {kind:<16} {path}" + (f"  ({reason})" if reason and reason != "framework" else ""), fg=typer.colors.GREEN)
    for path, kind, _enabled, reason in sorted(removed):
        typer.secho(f"  ⛔ {kind:<16} {path}  ({reason})", fg=typer.colors.RED)
    typer.echo(f"\n{len(kept)} route(s) in the desktop app, {len(removed)} web-only.")


@app.command("routes")
def routes_command(
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-x", help="Extra pattern(s) to exclude: /payments*, name:checkout"),
    auto_exclude: bool = typer.Option(False, "--auto-exclude", help="Also exclude routes detected as web-only."),
):
    """Preview which routes ship in the desktop app (and suggestions)."""
    from lila.core.config import ConfigLoader
    from lila.core import desktop as desktop_mod

    ConfigLoader.load()
    try:
        routes, _ = _load_project_routes([])
    except Exception as exc:
        typer.secho(f"❌ Could not import main:app: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    patterns = _resolve_patterns(exclude, auto_exclude, routes)
    _, statuses = _load_project_routes(patterns)
    _print_route_table(statuses)
    if not auto_exclude:
        suggestions = [
            (path, reason) for path, reason in desktop_mod.suggest_exclusions(routes)
            if desktop_mod.route_status(next(r for r in routes if getattr(r, "path", "") == path),
                                        desktop=True, patterns=desktop_mod.exclude_patterns() + patterns)[0]
        ]
        if suggestions:
            typer.secho("\n💡 These look web-only (use desktop=False, DESKTOP_EXCLUDE or --auto-exclude):", fg=typer.colors.YELLOW)
            for path, reason in suggestions:
                typer.echo(f"   {path}  ({reason})")


@app.callback(invoke_without_command=True)
def default_desktop(
    ctx: typer.Context,
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Window title (default: TITLE_PROJECT from .env)"),
    width: int = typer.Option(1200, "--width", "-w", help="Initial window width"),
    height: int = typer.Option(800, "--height", "-h", help="Initial window height"),
    port: int = typer.Option(0, "--port", "-p", help="Server port (0 = autodetect free port)"),
):
    """Runs Lila desktop app locally by default or supports build subcommand."""
    if ctx.invoked_subcommand is None:
        dev(title=title, width=width, height=height, port=port, resizable=True, fullscreen=False,
            debug=False, exclude=None, auto_exclude=False)


@app.command("dev")
@app.command("run")
def dev(
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Window title (default: TITLE_PROJECT from .env)"),
    width: int = typer.Option(1200, "--width", "-w", help="Initial window width"),
    height: int = typer.Option(800, "--height", "-h", help="Initial window height"),
    resizable: bool = typer.Option(True, "--resizable/--no-resizable", help="Whether window is resizable"),
    fullscreen: bool = typer.Option(False, "--fullscreen", help="Start window in fullscreen"),
    port: int = typer.Option(0, "--port", "-p", help="Server port (0 = autodetect free port)"),
    debug: bool = typer.Option(False, "--debug", help="Enable webview developer tools"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-x", help="Route pattern(s) left out of the desktop app"),
    auto_exclude: bool = typer.Option(False, "--auto-exclude", help="Exclude routes detected as web-only (payments, uploads...)"),
):
    """
    Runs the Lila application inside a native ultra-lightweight desktop window.
    Uses pywebview (WebView2 on Windows, WebKit on macOS/Linux) or fallback App Mode.
    """
    from lila.core.config import ConfigLoader, ENV_CONFIG

    ConfigLoader.load()
    window_title = title or ENV_CONFIG.get("TITLE_PROJECT", "Lila Desktop")

    # 1. Single Instance Lock
    lock_handle = acquire_single_instance_lock(window_title)
    if lock_handle is None:
        typer.secho(f"⚠️ {window_title} is already running in another window.", fg=typer.colors.YELLOW, bold=True)
        return

    try:
        preferred_port = int(ENV_CONFIG.get("PORT", 8000) or 8000)
    except (TypeError, ValueError):
        preferred_port = 8000
    target_port = port if port > 0 else find_free_port(preferred_port)

    # 2. Local Session Security Token (blocks external callers on same machine)
    desktop_token = secrets.token_hex(20)
    os.environ["LILA_DESKTOP_TOKEN"] = desktop_token
    os.environ["LILA_DESKTOP"] = "1"
    patterns = _resolve_patterns(exclude, auto_exclude)
    if patterns:
        os.environ["LILA_DESKTOP_EXCLUDE"] = ",".join(patterns)
        typer.echo(f"🧩 Web-only routes excluded: {', '.join(patterns)}")

    typer.echo(f"🚀 Starting Lila Desktop on http://127.0.0.1:{target_port} ...")

    # Start uvicorn strictly bound to 127.0.0.1
    server_holder = []
    error_holder = []
    server_thread = threading.Thread(
        target=run_uvicorn_thread,
        args=("127.0.0.1", target_port, server_holder, error_holder),
        daemon=True,
    )
    server_thread.start()

    if not wait_for_server("127.0.0.1", target_port, timeout=10.0, error_holder=error_holder):
        typer.secho("❌ Failed to start background Lila server.", fg=typer.colors.RED)
        if error_holder:
            import traceback
            err = error_holder[0]
            tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            typer.secho(tb, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    url = f"http://127.0.0.1:{target_port}/?_dt={desktop_token}"

    # Try pywebview first
    has_webview = False
    try:
        import webview
        has_webview = True
    except ImportError:
        pass

    bridge = DesktopBridge()

    try:
        if has_webview:
            typer.secho("🖥️ Launching with pywebview native window (window.pywebview.api enabled)...", fg=typer.colors.GREEN)
            webview.create_window(
                title=window_title,
                url=url,
                width=width,
                height=height,
                resizable=resizable,
                fullscreen=fullscreen,
                js_api=bridge,
            )
            webview.start(debug=debug)
        else:
            typer.secho("ℹ️ pywebview not found. Falling back to native App-Mode window.", fg=typer.colors.YELLOW)
            proc = launch_native_browser(url, width=width, height=height)
            if proc:
                typer.echo("🖥️ Application opened in standalone app mode. Close the window to exit.")
                try:
                    proc.wait()
                except KeyboardInterrupt:
                    proc.terminate()
            else:
                typer.secho("⚠️ No suitable browser or pywebview found. Opening default web browser.", fg=typer.colors.YELLOW)
                import webbrowser
                webbrowser.open(url)
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
    finally:
        if server_holder:
            server_holder[0].should_exit = True

    typer.echo("🛑 Lila Desktop closed.")


@app.command("build")
def build(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Executable name"),
    onefile: bool = typer.Option(True, "--onefile/--onedir", help="Package into a single executable"),
    icon: Optional[str] = typer.Option("public/favicon.ico", "--icon", "-i", help="Path to .ico icon"),
    windowed: bool = typer.Option(True, "--windowed/--console", help="Hide console window on execution"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-x", help="Route pattern(s) left out of the build: /payments*, /upload*, name:checkout"),
    auto_exclude: bool = typer.Option(False, "--auto-exclude", help="Exclude routes detected as web-only (payments, uploads, webhooks...)"),
    react: Optional[bool] = typer.Option(None, "--react/--no-react", help="Run `lila react build` first (default: auto when vite.config.js exists)"),
    width: int = typer.Option(1200, "--width", help="Initial window width"),
    height: int = typer.Option(800, "--height", help="Initial window height"),
):
    """
    Bundles the Lila application into a standalone native executable (.exe / .app) using PyInstaller.

    Routes declared with ``desktop=False``, matched by ``DESKTOP_EXCLUDE`` or by
    ``--exclude`` are removed from the build (404, hidden from React links).
    """
    import importlib.util
    if not importlib.util.find_spec("PyInstaller"):
        typer.secho("❌ PyInstaller is not installed.", fg=typer.colors.RED)
        typer.echo("Install it using: pip install pyinstaller OR pip install \"lila-framework[desktop]\"")
        raise typer.Exit(code=1)

    from lila.core.config import ConfigLoader, ENV_CONFIG

    ConfigLoader.load()
    app_name = (name or ENV_CONFIG.get("TITLE_PROJECT", "LilaApp")).replace(" ", "_")
    app_name = "".join(ch for ch in app_name if ch.isalnum() or ch in ("_", "-")) or "LilaApp"

    from lila.cli.react import is_react_project, run_build

    if react is None:
        react = is_react_project()
    if react:
        if not run_build(install=True):
            raise typer.Exit(code=1)

    from lila.core.desktop import exclude_patterns

    # .env is not bundled: bake DESKTOP_EXCLUDE together with --exclude.
    patterns = list(dict.fromkeys(exclude_patterns() + _resolve_patterns(exclude, auto_exclude)))
    try:
        _, statuses = _load_project_routes(patterns)
        removed = [s for s in statuses if not s[2]]
        if removed:
            typer.secho("🧩 Web-only routes left out of the desktop build:", fg=typer.colors.CYAN)
            for path, kind, _enabled, reason in sorted(removed):
                typer.echo(f"   ⛔ {kind:<14} {path}  ({reason})")
    except Exception as exc:
        typer.secho(f"⚠️ Could not preview routes ({exc}); exclusions still apply at runtime.", fg=typer.colors.YELLOW)

    bootstrap_code = f'''import os, sys, threading, socket, time, secrets, tempfile

# 1. Ensure runtime directories are correctly registered on sys.path
meipass = getattr(sys, '_MEIPASS', None)
if meipass:
    if meipass not in sys.path:
        sys.path.insert(0, meipass)
else:
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    try:
        os.chdir(exe_dir)
    except Exception:
        pass
    if exe_dir not in sys.path:
        sys.path.insert(1, exe_dir)

def acquire_lock(app_name):
    clean = "".join(c for c in app_name if c.isalnum() or c in ("_", "-")) or "LilaApp"
    if sys.platform == "win32":
        try:
            import ctypes
            mutex = ctypes.windll.kernel32.CreateMutexW(None, True, f"Local\\\\Lila_{{clean}}")
            if ctypes.windll.kernel32.GetLastError() == 183:
                return None
            return mutex
        except Exception:
            return True
    else:
        try:
            import fcntl
            lock_path = os.path.join(tempfile.gettempdir(), f"lila_{{clean}}.lock")
            fd = open(lock_path, "w")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except Exception:
            return None

if acquire_lock({app_name!r}) is None:
    sys.exit(0)

class DesktopBridge:
    def open_file_dialog(self, title="Open File", file_types=None):
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, title=title, file_types=tuple(file_types or ["All files (*.*)"]))
                return res[0] if res else None
        except Exception:
            return None
    def save_file_dialog(self, title="Save File As", default_filename=""):
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG, title=title, save_filename=default_filename)
                return res if isinstance(res, str) else (res[0] if res else None)
        except Exception:
            return None
    def select_folder_dialog(self, title="Select Folder"):
        try:
            import webview
            if webview.windows:
                res = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG, title=title)
                return res[0] if res else None
        except Exception:
            return None

desktop_token = secrets.token_hex(20)
os.environ["LILA_DESKTOP_TOKEN"] = desktop_token
os.environ["LILA_DESKTOP"] = "1"
os.environ["LILA_DESKTOP_EXCLUDE"] = {",".join(patterns)!r}
os.environ.setdefault("TITLE_PROJECT", {app_name!r})

import uvicorn
import main as app_module

def find_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

port = find_port()
server_holder = []

def run_server():
    try:
        config = uvicorn.Config(
            app_module.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            reload=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server_holder.append(server)
        server.run()
    except Exception as e:
        print(f"Error starting server: {{e}}", file=sys.stderr)

threading.Thread(target=run_server, daemon=True).start()

for _ in range(100):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
            break
    except Exception:
        time.sleep(0.1)

url = f"http://127.0.0.1:{{port}}/?_dt={{desktop_token}}"

try:
    import webview
    webview.create_window({app_name!r}, url, width={int(width)}, height={int(height)}, js_api=DesktopBridge())
    webview.start()
except ImportError:
    import webbrowser
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
finally:
    if server_holder:
        server_holder[0].should_exit = True
'''

    bootstrap_file = "_desktop_entry.py"
    with open(bootstrap_file, "w", encoding="utf-8") as f:
        f.write(bootstrap_code)

    import lila
    lila_pkg_dir = os.path.dirname(os.path.abspath(lila.__file__))
    lila_root = os.path.dirname(lila_pkg_dir)

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--clean",
        "--noconfirm",
        "--hidden-import", "main",
        "--hidden-import", "aiosqlite",
        "--collect-all", "lila",
        "--collect-submodules", "app",
        "--collect-submodules", "lila",
        "--collect-data", "lila",
        "--collect-submodules", "uvicorn",
        "--paths", ".",
        "--paths", lila_root,
    ]

    try:
        import webview
        pyinstaller_cmd.extend(["--collect-submodules", "webview"])
    except ImportError:
        pass

    if onefile:
        pyinstaller_cmd.append("--onefile")
    else:
        pyinstaller_cmd.append("--onedir")

    if windowed:
        pyinstaller_cmd.append("--windowed")

    if icon and os.path.isfile(icon):
        pyinstaller_cmd.extend(["--icon", icon])

    sep = ";" if sys.platform == "win32" else ":"
    if os.path.isdir("public"):
        pyinstaller_cmd.extend(["--add-data", f"public{sep}public"])
    if os.path.isdir("resources"):
        pyinstaller_cmd.extend(["--add-data", f"resources{sep}resources"])
    # Project translations are JSON data, not Python modules: bundle them too
    # (otherwise the build silently falls back to the framework's locales).
    if os.path.isdir(os.path.join("app", "locales")):
        pyinstaller_cmd.extend(["--add-data", f"{os.path.join('app', 'locales')}{sep}{os.path.join('app', 'locales')}"])

    pyinstaller_cmd.append(bootstrap_file)

    typer.secho(f"📦 Compiling {app_name} with PyInstaller...", fg=typer.colors.CYAN)
    result = None
    try:
        result = subprocess.run(pyinstaller_cmd)
    finally:
        if os.path.exists(bootstrap_file):
            os.remove(bootstrap_file)

    if result is not None and result.returncode == 0:
        typer.secho(f"✅ Desktop application built successfully! Output in dist/{app_name}", fg=typer.colors.GREEN)
    else:
        typer.secho("❌ PyInstaller build failed.", fg=typer.colors.RED)
        raise typer.Exit(code=result.returncode if result else 1)


if __name__ == "__main__":
    app()
