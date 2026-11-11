"""``lila css build`` — compile Tailwind CSS without Node.js.

Downloads the official Tailwind standalone binary once (cached per version,
verified against the release's ``sha256sums.txt``), scans the project's and
Lila's templates/scripts for classes and writes a minified
``public/css/lila.css`` (+ ``.gz``/``.br``). In production ``lila/tailwind.jinja``
then links that file instead of running the 276 KB Tailwind browser runtime.

    lila css build            # one-off build (use before deploying)
    lila css build --watch    # rebuild on changes
    lila css clean            # remove the compiled file (back to the runtime)
"""

from __future__ import annotations

import gzip
import hashlib
import os
import platform
import re
import stat
import subprocess
import sys
import urllib.request
from typing import Optional

import typer

app = typer.Typer(help="Compile Tailwind CSS (standalone binary, no Node.js).")

DEFAULT_VERSION = "4.3.2"  # matches the bundled browser runtime (public/js/tailwind.js)
RELEASE_URL = "https://github.com/tailwindlabs/tailwindcss/releases/download/v{version}/{asset}"
OUTPUT_DEFAULT = os.path.join("public", "css", "lila.css")


def _package_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def asset_name(system: Optional[str] = None, machine: Optional[str] = None, musl: Optional[bool] = None) -> str:
    """Release asset for this OS/CPU (e.g. ``tailwindcss-linux-x64``)."""
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    arch = "arm64" if machine in ("arm64", "aarch64", "armv8", "armv8l") else "x64"
    if system.startswith("win"):
        return f"tailwindcss-windows-{arch}.exe"
    if system == "darwin":
        return f"tailwindcss-macos-{arch}"
    if musl is None:
        musl = os.path.exists("/etc/alpine-release")
    return f"tailwindcss-linux-{arch}{'-musl' if musl else ''}"


def cache_dir(version: str) -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "lila", "tailwind", version)


def _download(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "lila-framework"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def expected_sha256(sums_text: str, asset: str) -> Optional[str]:
    for line in sums_text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*./") == asset:
            return parts[0].lower()
    return None


def ensure_binary(version: str = DEFAULT_VERSION, verify: bool = True, downloader=_download) -> str:
    """Returns the path of a verified Tailwind binary, downloading it once."""
    explicit = os.environ.get("TAILWIND_BIN")
    if explicit:
        if not os.path.isfile(explicit):
            raise RuntimeError(f"TAILWIND_BIN points to a missing file: {explicit}")
        return explicit

    asset = asset_name()
    target_dir = cache_dir(version)
    target = os.path.join(target_dir, asset)
    if os.path.isfile(target):
        return target

    typer.echo(f"⬇️  Downloading Tailwind CSS v{version} ({asset})...")
    data = downloader(RELEASE_URL.format(version=version, asset=asset))
    if verify:
        sums = downloader(RELEASE_URL.format(version=version, asset="sha256sums.txt")).decode("utf-8", "ignore")
        expected = expected_sha256(sums, asset)
        actual = hashlib.sha256(data).hexdigest()
        if not expected:
            raise RuntimeError(f"{asset} is not listed in sha256sums.txt of v{version}")
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch for {asset}: expected {expected}, got {actual}")
    os.makedirs(target_dir, exist_ok=True)
    tmp = f"{target}.part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(tmp, target)
    typer.secho(f"✅ Tailwind binary cached in {target_dir}", fg=typer.colors.GREEN)
    return target


_STYLE_RE = re.compile(r'<style type="text/tailwindcss">(.*?)</style>', re.S)


def theme_css() -> str:
    """The @theme / custom CSS used by the runtime (project override first)."""
    from lila.core.templates import jinja_env

    try:
        source, _, _ = jinja_env.loader.get_source(jinja_env, "lila/tailwind.jinja")
    except Exception:
        with open(os.path.join(_package_dir(), "resources", "html", "lila", "tailwind.jinja"), encoding="utf-8") as fh:
            source = fh.read()
    match = _STYLE_RE.search(source)
    return match.group(1) if match else ""


def _css_path(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/").replace('"', '\\"')


def build_input(project_dir: str = ".") -> str:
    """Tailwind entry file: sources to scan + Lila's theme + project CSS."""
    project = os.path.abspath(project_dir)
    pkg = _package_dir()
    sources = [
        os.path.join(project, "resources"),
        os.path.join(project, "app"),
        os.path.join(project, "public", "js"),
        os.path.join(pkg, "resources", "html"),
        os.path.join(pkg, "public", "js", "lila-client.js"),
        os.path.join(pkg, "core"),  # classes generated in Python (helpers, admin menu)
    ]
    lines = ['@import "tailwindcss" source(none);']
    for src in sources:
        if os.path.exists(src):
            lines.append(f'@source "{_css_path(src)}";')
    lines.append(f'@source not "{_css_path(os.path.join(project, "public", "js", "tailwind.js"))}";')
    lines.append(theme_css())
    custom = os.path.join(project, "resources", "css", "app.css")
    if os.path.isfile(custom):
        with open(custom, encoding="utf-8") as fh:
            lines.append(fh.read())
    return "\n".join(lines) + "\n"


def write_precompressed(path: str) -> None:
    with open(path, "rb") as fh:
        data = fh.read()
    with open(f"{path}.gz", "wb") as fh:
        fh.write(gzip.compress(data, compresslevel=9))
    try:
        import brotli  # type: ignore

        with open(f"{path}.br", "wb") as fh:
            fh.write(brotli.compress(data, quality=11))
    except Exception:
        pass


@app.command("build")
def build(
    output: str = typer.Option(OUTPUT_DEFAULT, "--output", "-o", help="Compiled CSS path."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Rebuild when templates change."),
    version: str = typer.Option(DEFAULT_VERSION, "--version", help="Tailwind CSS version."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip the SHA-256 check (not recommended)."),
):
    """Compile and minify Tailwind CSS for production (no Node.js needed)."""
    try:
        binary = ensure_binary(version, verify=not no_verify)
    except Exception as exc:
        typer.secho(f"❌ Could not get the Tailwind binary: {exc}", fg=typer.colors.RED)
        typer.echo("   Tip: set TAILWIND_BIN=/path/to/tailwindcss to use an existing binary.")
        raise typer.Exit(code=1)

    input_path = os.path.join("app", "cache", "tailwind.input.css")
    os.makedirs(os.path.dirname(input_path), exist_ok=True)
    with open(input_path, "w", encoding="utf-8") as fh:
        fh.write(build_input("."))
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    cmd = [binary, "-i", input_path, "-o", output, "--minify"]
    if watch:
        cmd.append("--watch")
    typer.echo(f"🎨 {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        typer.secho("❌ Tailwind build failed.", fg=typer.colors.RED)
        raise typer.Exit(code=result.returncode)
    if not watch and os.path.isfile(output):
        write_precompressed(output)
        size = os.path.getsize(output) / 1024
        typer.secho(f"✅ {output} ({size:.1f} KB). Production pages now use it instead of the Tailwind runtime.",
                    fg=typer.colors.GREEN)


@app.command("clean")
def clean(output: str = typer.Option(OUTPUT_DEFAULT, "--output", "-o")):
    """Remove the compiled CSS (pages fall back to the Tailwind runtime)."""
    removed = 0
    for path in (output, f"{output}.gz", f"{output}.br"):
        if os.path.isfile(path):
            os.remove(path)
            removed += 1
    typer.echo(f"🧹 Removed {removed} file(s).")
