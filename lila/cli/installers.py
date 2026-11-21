"""Native installers for ``lila desktop build --installer``.

* macOS ``.dmg``: ``hdiutil`` (built into macOS) packs ``dist/<Name>.app`` with
  an ``Applications`` shortcut for drag-and-drop install.
* Windows ``.msi``: WiX Toolset v4+ (``dotnet tool install --global wix``).
  Installs ``<Name>.exe`` into Program Files with Start-menu and desktop
  shortcuts, the app icon in "Apps & features", and upgrades in place (stable
  UpgradeCode derived from the bundle id).

Each installer can only be produced on its own operating system. Icons: an
``.ico`` (Windows) or ``.icns`` (macOS) is used as is; a ``.png`` is converted
with Pillow when installed (``pip install pillow``), otherwise PyInstaller
receives it unchanged.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import List, Optional, Tuple
from xml.sax.saxutils import quoteattr

ICON_CANDIDATES = (
    "public/icon.ico",
    "public/icon.icns",
    "public/icon.png",
    "public/img/icon.png",
    "public/favicon.ico",
    "public/img/lila.png",
)


def package_icon() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "img", "lila.png")


def find_icon(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for candidate in ICON_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    fallback = package_icon()
    return fallback if os.path.isfile(fallback) else None


def convert_icon(source: Optional[str], platform: str, work_dir: str = os.path.join("build", "lila-icons")) -> Optional[str]:
    """Returns an icon PyInstaller/WiX accept on ``platform`` (``win32``/``darwin``/other)."""
    if not source:
        return None
    ext = os.path.splitext(source)[1].lower()
    wanted = ".ico" if platform == "win32" else ".icns" if platform == "darwin" else ext
    if ext == wanted or platform not in ("win32", "darwin"):
        return source
    try:
        from PIL import Image
    except ImportError:
        return source  # PyInstaller converts it itself when Pillow is present at build time
    os.makedirs(work_dir, exist_ok=True)
    target = os.path.join(work_dir, "app" + wanted)
    try:
        with Image.open(source) as img:
            img = img.convert("RGBA")
            side = max(img.size)
            if img.size[0] != img.size[1]:
                square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                square.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2))
                img = square
            if wanted == ".ico":
                img.save(target, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(side, 16)])
            else:
                img.resize((max(side, 512), max(side, 512))).save(target)
        return target
    except Exception:
        return source


def msi_version(value: Optional[str]) -> str:
    """MSI versions are ``major.minor.build`` numbers (<=255.255.65535)."""
    numbers = [int(n) for n in re.findall(r"\d+", str(value or ""))][:3]
    while len(numbers) < 3:
        numbers.append(0)
    if not any(numbers):
        numbers = [1, 0, 0]
    major, minor, build = numbers
    return f"{min(major, 255)}.{min(minor, 255)}.{min(build, 65535)}"


def upgrade_code(identifier: str) -> str:
    """Stable per app: every new version upgrades the previous install."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"lila-desktop:{identifier}")).upper()


def wix_source(
    name: str,
    exe_path: str,
    version: str = "1.0.0",
    manufacturer: str = "Lila",
    icon: Optional[str] = None,
    identifier: Optional[str] = None,
    onedir: Optional[str] = None,
    desktop_shortcut: bool = True,
) -> str:
    """WiX v4+ source for a per-machine MSI.

    ``exe_path`` is the PyInstaller ``--onefile`` executable; with ``onedir``
    (the ``dist/<name>`` folder) every file is harvested with ``<Files>``
    (WiX v5+).
    """
    exe_name = os.path.basename(exe_path)
    q = quoteattr
    reg_key = f"Software\\{manufacturer}\\{name}"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">',
        f"  <Package Name={q(name)} Manufacturer={q(manufacturer)} Version={q(msi_version(version))}",
        f"           UpgradeCode={q(upgrade_code(identifier or name))} Scope=\"perMachine\" Compressed=\"yes\">",
        '    <MajorUpgrade DowngradeErrorMessage="A newer version of [ProductName] is already installed." />',
        '    <MediaTemplate EmbedCab="yes" />',
    ]
    if icon:
        lines += [
            f"    <Icon Id=\"AppIcon\" SourceFile={q(os.path.abspath(icon))} />",
            '    <Property Id="ARPPRODUCTICON" Value="AppIcon" />',
        ]
    lines += [
        '    <StandardDirectory Id="ProgramFiles64Folder">',
        f"      <Directory Id=\"INSTALLFOLDER\" Name={q(name)}>",
    ]
    if not onedir:
        lines += [
            '        <Component Id="MainExecutable">',
            f"          <File Id=\"MainExe\" Source={q(os.path.abspath(exe_path))} KeyPath=\"yes\" />",
            "        </Component>",
        ]
    lines += ["      </Directory>", "    </StandardDirectory>"]

    shortcut_icon = ' Icon="AppIcon"' if icon else ""

    def shortcut(component: str, folder: str, shortcut_id: str) -> List[str]:
        return [
            f'    <StandardDirectory Id="{folder}">',
            f'      <Component Id="{component}">',
            f"        <Shortcut Id=\"{shortcut_id}\" Name={q(name)} Target=\"[INSTALLFOLDER]{exe_name}\""
            f' WorkingDirectory="INSTALLFOLDER"{shortcut_icon} />',
            f"        <RegistryValue Root=\"HKCU\" Key={q(reg_key)} Name=\"{component}\" Type=\"integer\" Value=\"1\" KeyPath=\"yes\" />",
            "      </Component>",
            "    </StandardDirectory>",
        ]

    lines += shortcut("StartMenuShortcut", "ProgramMenuFolder", "StartMenuLink")
    if desktop_shortcut:
        lines += shortcut("DesktopShortcut", "DesktopFolder", "DesktopLink")
    lines += [
        '    <Feature Id="Main">',
        "      <ComponentRef Id=\"MainExecutable\" />" if not onedir else
        f"      <Files Directory=\"INSTALLFOLDER\" Include={q(os.path.join(os.path.abspath(onedir), '**'))} />",
        '      <ComponentRef Id="StartMenuShortcut" />',
        '      <ComponentRef Id="DesktopShortcut" />' if desktop_shortcut else "",
        "    </Feature>",
        "  </Package>",
        "</Wix>",
        "",
    ]
    return "\n".join(line for line in lines if line != "")


def wix_command(wxs_path: str, output: str, wix: str = "wix") -> List[str]:
    return [wix, "build", wxs_path, "-arch", "x64", "-o", output]


def find_wix() -> Optional[str]:
    found = shutil.which("wix") or shutil.which("wix.exe")
    if found:
        return found
    candidate = os.path.join(os.path.expanduser("~"), ".dotnet", "tools", "wix.exe" if sys.platform == "win32" else "wix")
    return candidate if os.path.isfile(candidate) else None


def build_msi(name: str, version: str, manufacturer: str, icon: Optional[str], identifier: str,
              onefile: bool, dist: str = "dist") -> Tuple[bool, str]:
    """Writes ``build/installer/<name>.wxs`` and runs ``wix build``."""
    exe = os.path.join(dist, f"{name}.exe") if onefile else os.path.join(dist, name, f"{name}.exe")
    if not os.path.isfile(exe):
        return False, f"{exe} not found (the PyInstaller build must run on Windows)."
    ico = convert_icon(icon, "win32") if icon else None
    if ico and not ico.lower().endswith(".ico"):
        ico = None  # WiX/Windows need a real .ico
    os.makedirs(os.path.join("build", "installer"), exist_ok=True)
    wxs = os.path.join("build", "installer", f"{name}.wxs")
    with open(wxs, "w", encoding="utf-8") as fh:
        fh.write(wix_source(name, exe, version, manufacturer, ico, identifier,
                            onedir=None if onefile else os.path.join(dist, name)))
    wix = find_wix()
    if not wix:
        return False, (
            f"WiX Toolset not found. Install it with `dotnet tool install --global wix` and run "
            f"`wix build {wxs} -arch x64 -o {os.path.join(dist, name + '.msi')}`."
        )
    output = os.path.join(dist, f"{name}.msi")
    result = subprocess.run(wix_command(wxs, output, wix))
    if result.returncode != 0:
        return False, f"wix build failed (source kept in {wxs})."
    return True, output


def dmg_command(staging: str, output: str, volume: str) -> List[str]:
    return ["hdiutil", "create", "-volname", volume, "-srcfolder", staging, "-ov", "-format", "UDZO", output]


def build_dmg(name: str, dist: str = "dist") -> Tuple[bool, str]:
    """Packs ``dist/<name>.app`` into ``dist/<name>.dmg`` (macOS only)."""
    if sys.platform != "darwin":
        return False, ".dmg images can only be created on macOS (hdiutil)."
    app_bundle = os.path.join(dist, f"{name}.app")
    if not os.path.isdir(app_bundle):
        return False, f"{app_bundle} not found: build with --windowed on macOS."
    if not shutil.which("hdiutil"):
        return False, "hdiutil not found."
    output = os.path.join(dist, f"{name}.dmg")
    staging = tempfile.mkdtemp(prefix="lila-dmg-")
    try:
        shutil.copytree(app_bundle, os.path.join(staging, f"{name}.app"), symlinks=True)
        os.symlink("/Applications", os.path.join(staging, "Applications"))
        result = subprocess.run(dmg_command(staging, output, name))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if result.returncode != 0:
        return False, "hdiutil create failed."
    return True, output


def default_installer(platform: str = sys.platform) -> Optional[str]:
    return "msi" if platform == "win32" else "dmg" if platform == "darwin" else None
