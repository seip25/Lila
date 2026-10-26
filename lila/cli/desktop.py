import os
import sys
import time
import socket
import threading
import subprocess
import shutil
import tempfile
import typer
from typing import Optional

app = typer.Typer(help="Lila Desktop CLI - Run and bundle full-stack Python apps as native desktop applications.")

def find_free_port(preferred_port: int = 8000) -> int:
    """Finds a free port on localhost starting with the preferred port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred_port)) != 0:
            return preferred_port
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_for_server(host: str, port: int, timeout: float = 6.0) -> bool:
    """Polls host:port until it accepts TCP connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (socket.error, ConnectionRefusedError):
            time.sleep(0.1)
    return False

def run_uvicorn_thread(host: str, port: int):
    """Runs uvicorn in a background daemon thread."""
    import uvicorn
    # Suppress verbose access logs for desktop mode
    uvicorn.run("main:app", host=host, port=port, log_level="warning", access_log=False)

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
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            "msedge",
            "chrome"
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
        dev(title=title, width=width, height=height, port=port)


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
):
    """
    Runs the Lila application inside a native ultra-lightweight desktop window.
    Uses pywebview (WebView2 on Windows, WebKit on macOS/Linux) or fallback App Mode.
    """
    from lila.core.config import ENV_CONFIG
    window_title = title or ENV_CONFIG.get("TITLE_PROJECT", "Lila Desktop")
    target_port = port if port > 0 else find_free_port(int(ENV_CONFIG.get("PORT", 8000)))

    typer.echo(f"🚀 Starting Lila Desktop on http://127.0.0.1:{target_port} ...")

    # Start uvicorn in daemon thread
    server_thread = threading.Thread(target=run_uvicorn_thread, args=("127.0.0.1", target_port), daemon=True)
    server_thread.start()

    if not wait_for_server("127.0.0.1", target_port):
        typer.secho("❌ Failed to start background Lila server.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    url = f"http://127.0.0.1:{target_port}"

    # Try pywebview first
    has_webview = False
    try:
        import webview
        has_webview = True
    except ImportError:
        pass

    if has_webview:
        typer.secho("🖥️ Launching with pywebview native window...", fg=typer.colors.GREEN)
        webview.create_window(
            title=window_title,
            url=url,
            width=width,
            height=height,
            resizable=resizable,
            fullscreen=fullscreen,
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

    typer.echo("🛑 Lila Desktop closed.")

@app.command("build")
def build(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Executable name"),
    onefile: bool = typer.Option(True, "--onefile/--onedir", help="Package into a single executable"),
    icon: Optional[str] = typer.Option("public/favicon.ico", "--icon", "-i", help="Path to .ico icon"),
    windowed: bool = typer.Option(True, "--windowed/--console", help="Hide console window on execution"),
):
    """
    Bundles the Lila application into a standalone native executable (.exe) using PyInstaller.
    """
    import importlib.util
    if not importlib.util.find_spec("PyInstaller"):
        typer.secho("❌ PyInstaller is not installed.", fg=typer.colors.RED)
        typer.echo("Install it using: pip install pyinstaller OR pip install \"lila-framework[desktop]\"")
        raise typer.Exit(code=1)

    from lila.core.config import ENV_CONFIG
    app_name = name or ENV_CONFIG.get("TITLE_PROJECT", "LilaApp").replace(" ", "_")

    # Generate bootstrap entry script
    bootstrap_code = f"""import os, sys, threading, socket, time
from lila.core.config import get_base_path, get_data_path
import uvicorn

def find_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

port = find_port()

def run_server():
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning", access_log=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()

# Wait for server
for _ in range(50):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.1):
            break
    except Exception:
        time.sleep(0.1)

url = f"http://127.0.0.1:{{port}}"

try:
    import webview
    webview.create_window("{app_name}", url, width=1200, height=800)
    webview.start()
except ImportError:
    import webbrowser
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
"""

    bootstrap_file = "_desktop_entry.py"
    with open(bootstrap_file, "w", encoding="utf-8") as f:
        f.write(bootstrap_code)

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--clean",
        "-y"
    ]

    if onefile:
        pyinstaller_cmd.append("--onefile")
    else:
        pyinstaller_cmd.append("--onedir")

    if windowed:
        pyinstaller_cmd.append("--windowed")

    if icon and os.path.isfile(icon):
        pyinstaller_cmd.extend(["--icon", icon])

    # Add data directories: public and resources
    sep = ";" if sys.platform == "win32" else ":"
    if os.path.isdir("public"):
        pyinstaller_cmd.extend(["--add-data", f"public{sep}public"])
    if os.path.isdir("resources"):
        pyinstaller_cmd.extend(["--add-data", f"resources{sep}resources"])

    pyinstaller_cmd.append(bootstrap_file)

    typer.secho(f"📦 Compiling {app_name} with PyInstaller...", fg=typer.colors.CYAN)
    result = subprocess.run(pyinstaller_cmd)

    if os.path.exists(bootstrap_file):
        os.remove(bootstrap_file)

    if result.returncode == 0:
        typer.secho(f"✅ Desktop application built successfully! Output in dist/{app_name}", fg=typer.colors.GREEN)
    else:
        typer.secho("❌ PyInstaller build failed.", fg=typer.colors.RED)
        raise typer.Exit(code=result.returncode)

if __name__ == "__main__":
    app()
