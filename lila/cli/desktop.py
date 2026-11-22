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

# The native bridge (window.pywebview.api) lives in lila.core.desktop_bridge so
# `lila desktop dev` and the frozen bootstrap share one implementation.
from lila.core.desktop_bridge import DesktopBridge  # noqa: E402,F401


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
            log_config=None,
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
    menu: Optional[bool] = typer.Option(None, "--menu/--no-menu", help="Show native menu bar (File, Edit, View, Help)"),
    preferences_url: Optional[str] = typer.Option(None, "--preferences-url", help="URL opened by File -> Preferences"),
    help_file: Optional[str] = typer.Option(None, "--help-file", help="Markdown file shown in Help -> Manual / Help"),
    about: Optional[str] = typer.Option(None, "--about", help="Extra description shown in Help -> About"),
):
    """Runs Lila desktop app locally by default or supports build subcommand."""
    if ctx.invoked_subcommand is None:
        dev(title=title, width=width, height=height, port=port, resizable=True, fullscreen=False,
            debug=False, exclude=None, auto_exclude=False, menu=menu,
            preferences_url=preferences_url, help_file=help_file, about=about)


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
    menu: Optional[bool] = typer.Option(None, "--menu/--no-menu", help="Show native menu bar (File, Edit, View, Help)"),
    preferences_url: Optional[str] = typer.Option(None, "--preferences-url", help="URL opened by File -> Preferences"),
    help_file: Optional[str] = typer.Option(None, "--help-file", help="Markdown file shown in Help -> Manual / Help"),
    about: Optional[str] = typer.Option(None, "--about", help="Extra description shown in Help -> About"),
):
    """
    Runs the Lila application inside a native ultra-lightweight desktop window.
    Uses pywebview (WebView2 on Windows, WebKit on macOS/Linux) or fallback App Mode.
    """
    from lila.core.config import ConfigLoader, ENV_CONFIG
    from lila.core.desktop_menu import DesktopMenuConfig, build_desktop_menu

    ConfigLoader.load()
    window_title = title or ENV_CONFIG.get("TITLE_PROJECT", "Lila Desktop")
    menu_enabled = ENV_CONFIG.get_bool("DESKTOP_MENU", True) if menu is None else bool(menu)
    os.environ.setdefault("LILA_APP_VERSION", str(ENV_CONFIG.get("VERSION_PROJECT", "1.0.0") or "1.0.0"))
    os.environ["DESKTOP_MENU"] = "True" if menu_enabled else "False"
    if preferences_url is not None:
        os.environ["DESKTOP_PREFERENCES_URL"] = preferences_url
    if help_file is not None:
        os.environ["DESKTOP_HELP_FILE"] = help_file
    if about is not None:
        os.environ["DESKTOP_ABOUT"] = about

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
            win = webview.create_window(
                title=window_title,
                url=url,
                width=width,
                height=height,
                resizable=resizable,
                fullscreen=fullscreen,
                js_api=bridge,
                text_select=True,
                zoomable=True,
            )
            menu_cfg = DesktopMenuConfig.from_env(app_name=window_title, enabled=menu_enabled)
            menu_items = build_desktop_menu(lambda: win, menu_cfg) if menu_cfg.enabled else []
            webview.start(debug=debug, menu=menu_items)
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
    icon: Optional[str] = typer.Option(None, "--icon", "-i", help="App icon (.ico/.icns/.png). Default: public/icon.*, public/favicon.ico or the Lila logo"),
    windowed: bool = typer.Option(True, "--windowed/--console", help="Hide console window on execution"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-x", help="Route pattern(s) left out of the build: /payments*, /upload*, name:checkout"),
    auto_exclude: bool = typer.Option(False, "--auto-exclude", help="Exclude routes detected as web-only (payments, uploads, webhooks...)"),
    react: Optional[bool] = typer.Option(None, "--react/--no-react", help="Run `lila react build` first (default: auto when vite.config.js exists)"),
    width: int = typer.Option(1200, "--width", help="Initial window width"),
    height: int = typer.Option(800, "--height", help="Initial window height"),
    installer: str = typer.Option("none", "--installer", help="none | auto | dmg (macOS) | msi (Windows, WiX Toolset)"),
    version: Optional[str] = typer.Option(None, "--version", help="App version (default: VERSION_PROJECT from .env)"),
    publisher: Optional[str] = typer.Option(None, "--publisher", help="Publisher/manufacturer shown by the installer"),
    bundle_id: Optional[str] = typer.Option(None, "--bundle-id", help="Reverse-DNS id, e.g. com.acme.invoices (macOS bundle id, MSI upgrade code seed)"),
    update_url: Optional[str] = typer.Option(None, "--update-url", help="https URL of latest.json (lila desktop release) for in-app updates; default DESKTOP_UPDATE_URL"),
    sign_identity: Optional[str] = typer.Option(None, "--sign-identity", help="macOS: 'Developer ID Application: ...' (default MACOS_SIGN_IDENTITY)"),
    notary_profile: Optional[str] = typer.Option(None, "--notary-profile", help="macOS: notarytool keychain profile (default MACOS_NOTARY_PROFILE)"),
    sign_cert: Optional[str] = typer.Option(None, "--sign-cert", help="Windows: .pfx path (password in WINDOWS_SIGN_PASSWORD; default WINDOWS_SIGN_CERT)"),
    sign_thumbprint: Optional[str] = typer.Option(None, "--sign-thumbprint", help="Windows: certificate thumbprint in the store (default WINDOWS_SIGN_THUMBPRINT)"),
    menu: Optional[bool] = typer.Option(None, "--menu/--no-menu", help="Include native menu bar (File, Edit, View, Help)"),
    preferences_url: Optional[str] = typer.Option(None, "--preferences-url", help="URL opened by File -> Preferences"),
    help_file: Optional[str] = typer.Option(None, "--help-file", help="Markdown file bundled for Help -> Manual / Help"),
    help_editable: Optional[bool] = typer.Option(None, "--help-editable/--no-help-editable", help="Allow users to edit the Markdown manual in-app"),
    about: Optional[str] = typer.Option(None, "--about", help="Extra description shown in Help -> About"),
):
    """
    Bundles the Lila application into a standalone native executable (.exe / .app) using PyInstaller.

    ``--installer auto`` also creates ``dist/<name>.dmg`` on macOS (hdiutil) or
    ``dist/<name>.msi`` on Windows (WiX Toolset: ``dotnet tool install --global wix``).

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

    from lila.cli import installers

    installer = (installer or "none").lower()
    if installer == "auto":
        installer = installers.default_installer() or "none"
        if installer == "none":
            typer.secho("ℹ️ No native installer for this OS (.dmg on macOS, .msi on Windows).", fg=typer.colors.YELLOW)
    if installer not in ("none", "dmg", "msi"):
        typer.secho("❌ --installer must be none, auto, dmg or msi.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if installer == "dmg" and sys.platform != "darwin":
        typer.secho("❌ .dmg images can only be built on macOS.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if installer == "msi" and sys.platform != "win32":
        typer.secho("❌ .msi installers can only be built on Windows (WiX Toolset).", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if installer == "dmg" and not windowed:
        windowed = True  # hdiutil packs the .app bundle, which needs --windowed
    app_version = version or str(ENV_CONFIG.get("VERSION_PROJECT", "1.0.0") or "1.0.0")
    update_url = update_url or str(ENV_CONFIG.get("DESKTOP_UPDATE_URL", "") or "") or None
    if update_url and not update_url.startswith("https://"):
        typer.secho("❌ --update-url must use https.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    sign_identity = sign_identity or os.environ.get("MACOS_SIGN_IDENTITY") or None
    notary_profile = notary_profile or os.environ.get("MACOS_NOTARY_PROFILE") or None
    sign_cert = sign_cert or os.environ.get("WINDOWS_SIGN_CERT") or None
    sign_thumbprint = sign_thumbprint or os.environ.get("WINDOWS_SIGN_THUMBPRINT") or None
    app_publisher = publisher or str(ENV_CONFIG.get("AUTHOR_DEFAULT", "") or app_name)
    app_id = bundle_id or f"com.lila.{app_name.lower()}"
    menu_enabled = ENV_CONFIG.get_bool("DESKTOP_MENU", True) if menu is None else bool(menu)
    menu_lang = str(ENV_CONFIG.get("DESKTOP_MENU_LANG", "") or "")
    prefs_url = str(ENV_CONFIG.get("DESKTOP_PREFERENCES_URL", "") or "") if preferences_url is None else preferences_url
    resolved_help_file = str(ENV_CONFIG.get("DESKTOP_HELP_FILE", "resources/manual.md") or "resources/manual.md") if help_file is None else help_file
    editable_help = ENV_CONFIG.get_bool("DESKTOP_HELP_EDITABLE", True) if help_editable is None else bool(help_editable)
    resolved_about = str(ENV_CONFIG.get("DESKTOP_ABOUT", "") or "") if about is None else about
    app_desc = str(ENV_CONFIG.get("DESCRIPTION_PROJECT", "") or "")
    app_lang = str(ENV_CONFIG.get("LANG_DEFAULT", "en") or "en")
    icon_path = installers.convert_icon(installers.find_icon(icon), sys.platform)
    if icon and not icon_path:
        typer.secho(f"⚠️ Icon {icon} not found; using the default.", fg=typer.colors.YELLOW)
        icon_path = installers.convert_icon(installers.find_icon(None), sys.platform)

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

    bootstrap_code = f'''import html as _html, os, sys, threading, socket, time, secrets, tempfile

# PyInstaller --windowed sets stdout/stderr to None on Windows, which crashes
# uvicorn's default logging formatter (isatty check) and print().
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

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

from lila.core.desktop_bridge import DesktopBridge

desktop_token = secrets.token_hex(20)
os.environ["LILA_DESKTOP_TOKEN"] = desktop_token
os.environ["LILA_DESKTOP"] = "1"
os.environ["LILA_DESKTOP_EXCLUDE"] = {",".join(patterns)!r}
os.environ["LILA_APP_VERSION"] = {app_version!r}
os.environ["LILA_UPDATE_URL"] = {(update_url or "")!r}
os.environ.setdefault("TITLE_PROJECT", {app_name!r})
os.environ.setdefault("DESCRIPTION_PROJECT", {app_desc!r})
os.environ.setdefault("AUTHOR_DEFAULT", {app_publisher!r})
os.environ.setdefault("LANG_DEFAULT", {app_lang!r})
os.environ["DESKTOP_MENU"] = {("True" if menu_enabled else "False")!r}
os.environ["DESKTOP_MENU_LANG"] = {menu_lang!r}
os.environ["DESKTOP_PREFERENCES_URL"] = {prefs_url!r}
os.environ["DESKTOP_HELP_FILE"] = {resolved_help_file!r}
os.environ["DESKTOP_HELP_EDITABLE"] = {("True" if editable_help else "False")!r}
os.environ["DESKTOP_ABOUT"] = {resolved_about!r}
os.environ.setdefault("DEBUG", "False")

def find_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

port = find_port()
server_holder = []
error_holder = []

def run_server():
    try:
        import uvicorn
        import main as app_module

        config = uvicorn.Config(
            app_module.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            reload=False,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server_holder.append(server)
        server.run()
    except Exception as e:
        error_holder.append(e)
        try:
            from lila.core.logger import Logger
            Logger.error(f"Desktop server failed to start: {{e}}", exception=e)
        except Exception:
            pass

threading.Thread(target=run_server, daemon=True).start()

server_ready = False
for _ in range(150):
    if error_holder:
        break
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
            server_ready = True
            break
    except Exception:
        time.sleep(0.1)

url = f"http://127.0.0.1:{{port}}/?_dt={{desktop_token}}"
err_html = None
if not server_ready:
    detail = _html.escape(repr(error_holder[0])) if error_holder else "Server startup timed out."
    try:
        from lila.core.config import get_data_path
        log_hint = _html.escape(get_data_path("app", "logs"))
    except Exception:
        log_hint = ""
    err_html = (
        "<!doctype html><html><body style='font-family:system-ui,sans-serif;padding:2rem;color:#1e293b'>"
        "<h2>Could not start application server</h2>"
        f"<pre style='background:#f8fafc;padding:1rem;border-radius:8px;overflow:auto'>{{detail}}</pre>"
        f"<p style='color:#64748b'>Logs: {{log_hint}}</p></body></html>"
    )

try:
    import webview
    from lila.core.desktop_menu import DesktopMenuConfig, build_desktop_menu

    if err_html is not None:
        webview.create_window({app_name!r}, html=err_html, width={int(width)}, height={int(height)})
        webview.start()
    else:
        win = webview.create_window(
            {app_name!r},
            url,
            width={int(width)},
            height={int(height)},
            js_api=DesktopBridge(),
            text_select=True,
            zoomable=True,
        )
        menu_cfg = DesktopMenuConfig.from_env(app_name={app_name!r}, enabled={bool(menu_enabled)!r})
        menu_items = build_desktop_menu(lambda: win, menu_cfg) if menu_cfg.enabled else []
        webview.start(menu=menu_items)
except ImportError:
    if err_html is None:
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

    if icon_path:
        pyinstaller_cmd.extend(["--icon", icon_path])
    if sys.platform == "darwin":
        pyinstaller_cmd.extend(["--osx-bundle-identifier", app_id])

    sep = ";" if sys.platform == "win32" else ":"
    if os.path.isdir("public"):
        pyinstaller_cmd.extend(["--add-data", f"public{sep}public"])
    if os.path.isdir("resources"):
        pyinstaller_cmd.extend(["--add-data", f"resources{sep}resources"])
    if resolved_help_file and os.path.isfile(resolved_help_file):
        norm_help = os.path.normpath(resolved_help_file)
        res_root = os.path.normpath("resources") + os.sep
        if not norm_help.startswith(res_root):
            dest_dir = "." if os.path.isabs(resolved_help_file) else (os.path.dirname(norm_help) or ".")
            pyinstaller_cmd.extend(["--add-data", f"{resolved_help_file}{sep}{dest_dir}"])
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

    def _sign(commands, what: str) -> None:
        ok, detail = installers.run_commands(commands)
        if ok:
            typer.secho(f"🔏 Signed {what}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"❌ Signing {what} {detail}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    # 1. Sign the app itself (before it goes into an installer).
    if sys.platform == "darwin" and sign_identity and os.path.isdir(os.path.join("dist", f"{app_name}.app")):
        _sign([installers.macos_sign_command(os.path.join("dist", f"{app_name}.app"), sign_identity)], f"{app_name}.app")
    if sys.platform == "win32" and (sign_cert or sign_thumbprint):
        exe = os.path.join("dist", f"{app_name}.exe") if onefile else os.path.join("dist", app_name, f"{app_name}.exe")
        tool = installers.find_signtool() or "signtool"
        _sign([installers.windows_sign_command(exe, sign_cert, sign_thumbprint, signtool=tool)], os.path.basename(exe))

    # 2. Installer, then sign (and notarize) it.
    if installer == "dmg":
        ok, detail = installers.build_dmg(app_name)
    elif installer == "msi":
        ok, detail = installers.build_msi(app_name, app_version, app_publisher, icon_path, app_id, onefile)
    else:
        if sys.platform in ("darwin", "win32") and not (sign_identity or sign_cert or sign_thumbprint):
            typer.secho("ℹ️ Unsigned build: Gatekeeper/SmartScreen will warn users (see --sign-identity / --sign-cert).", fg=typer.colors.YELLOW)
        return
    if not ok:
        typer.secho(f"❌ Installer not created: {detail}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if installer == "dmg" and sign_identity:
        _sign([installers.macos_sign_command(detail, sign_identity)], os.path.basename(detail))
        if notary_profile:
            _sign(installers.macos_notarize_commands(detail, notary_profile), f"{os.path.basename(detail)} (notarized + stapled)")
    if installer == "msi" and (sign_cert or sign_thumbprint):
        tool = installers.find_signtool() or "signtool"
        _sign([installers.windows_sign_command(detail, sign_cert, sign_thumbprint, signtool=tool)], os.path.basename(detail))
    if not (sign_identity or sign_cert or sign_thumbprint):
        typer.secho("ℹ️ Unsigned installer: Gatekeeper/SmartScreen will warn users (see --sign-identity / --sign-cert).", fg=typer.colors.YELLOW)
    typer.secho(f"💿 Installer ready: {detail}", fg=typer.colors.GREEN)
    if update_url:
        typer.echo(f"   Publish it and update the manifest: lila desktop release --version {app_version} --base-url <download folder URL>")


@app.command("release")
def release(
    version: str = typer.Option(..., "--version", help="Version being published (must match the build)"),
    base_url: str = typer.Option(..., "--base-url", help="https folder URL where the installers are uploaded"),
    notes: str = typer.Option("", "--notes", help="Release notes shown by the app"),
    dist: str = typer.Option("dist", "--dist", help="Folder with the installers"),
    output: str = typer.Option("dist/latest.json", "--output", "-o", help="Manifest to write (upload it to --update-url)"),
):
    """Write latest.json (version, URLs, SHA-256) for in-app updates.

    Run it on each OS after `lila desktop build --installer auto`; entries for
    the other platform of the same version are kept.
    """
    import json as _json
    from lila.cli import installers

    if not base_url.startswith("https://"):
        typer.secho("❌ --base-url must use https.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    files = [os.path.join(dist, f) for f in sorted(os.listdir(dist))] if os.path.isdir(dist) else []
    files = [f for f in files if os.path.splitext(f)[1].lower() in installers.INSTALLER_PLATFORMS]
    if not files:
        typer.secho(f"❌ No .msi/.dmg/.exe in {dist}/. Build with --installer auto first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    previous = None
    if os.path.isfile(output):
        try:
            with open(output, "r", encoding="utf-8") as fh:
                previous = _json.load(fh)
        except Exception:
            previous = None
    manifest = installers.build_update_manifest(version, base_url, files, notes, previous)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        _json.dump(manifest, fh, indent=2)
    for key, entry in manifest["files"].items():
        typer.echo(f"   {key:<8} {entry['url']}  sha256:{entry['sha256'][:12]}…")
    typer.secho(f"✅ {output} written. Upload the installers to {base_url} and the manifest to your --update-url.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
