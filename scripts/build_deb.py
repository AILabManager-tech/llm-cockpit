#!/usr/bin/env python3
"""Build a Debian package for LLM Cockpit.

Workflow:
1. Build the Linux onedir bundle with PyInstaller.
2. Assemble a Debian filesystem tree.
3. Emit `dist/linux/llm-cockpit_<version>_amd64.deb`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "linux"
BUILD_ROOT = ROOT / "build" / "deb"
PKG_ROOT = BUILD_ROOT / "pkg"
DEBIAN = PKG_ROOT / "DEBIAN"
OPT_ROOT = PKG_ROOT / "opt" / "llm-cockpit"
USR_BIN = PKG_ROOT / "usr" / "bin"
APP_DIR = PKG_ROOT / "usr" / "share" / "applications"
ICON_DIR = PKG_ROOT / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"


# System libraries QtWebEngine needs but the bundle does not carry. Measured,
# not guessed: `ldd` on LLM-Cockpit and on QtWebEngineProcess, resolved to
# packages with `dpkg -S`, minus what any glibc system already provides.
# `a | b` alternatives cover Ubuntu 24.04's t64 renaming without making the
# package uninstallable on distributions that kept the historical names.
RUNTIME_DEPENDS = (
    "libasound2t64 | libasound2",
    "libdbus-1-3",
    "libegl1",
    "libfontconfig1",
    "libfreetype6",
    "libgbm1",
    "libgl1",
    "libnspr4",
    "libnss3",
    "libx11-6",
    "libxcomposite1",
    "libxdamage1",
    "libxext6",
    "libxfixes3",
    "libxkbcommon0",
    "libxkbfile1",
    "libxrandr2",
    "libxrender1",
    "libxtst6",
)


def package_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def add_data(src: Path, dst: str) -> str:
    return f"{src}{os.pathsep}{dst}"


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd, cwd=ROOT)


def build_bundle() -> Path:
    run([sys.executable, str(ROOT / "scripts" / "build_linux_bundle.py")])
    bundle = DIST / "LLM-Cockpit"
    if not bundle.exists():
        raise SystemExit(f"bundle not found: {bundle}")
    return bundle


def clean_tree() -> None:
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)


def copy_bundle(bundle: Path) -> Path:
    target = OPT_ROOT / "LLM-Cockpit"
    shutil.copytree(bundle, target, symlinks=True)
    return target


def write_file(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def assemble_deb_files(bundle_dir: Path) -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    launcher_path = USR_BIN / "llm-cockpit"
    write_file(
        launcher_path,
        "#!/bin/sh\nexec /opt/llm-cockpit/LLM-Cockpit/LLM-Cockpit \"$@\"\n",
        0o755,
    )

    write_file(
        APP_DIR / "llm-cockpit.desktop",
        "\n".join(
            [
                "[Desktop Entry]",
                "Version=1.0",
                "Type=Application",
                "Name=LLM Cockpit",
                "Comment=Local-first LLM cockpit",
                "Exec=/usr/bin/llm-cockpit",
                "Icon=llm-cockpit",
                "Terminal=false",
                "Categories=Development;Utility;",
                "StartupWMClass=LLM-Cockpit",
            ]
        )
        + "\n",
    )

    shutil.copy2(
        ROOT / "app" / "static" / "llm-cockpit-favicon.svg",
        ICON_DIR / "llm-cockpit.svg",
    )

    write_file(
        DEBIAN / "control",
        "\n".join(
            [
                "Package: llm-cockpit",
                f"Version: {package_version()}",
                "Section: utils",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: LLM Cockpit <no-reply@llm-cockpit.local>",
                f"Depends: {', '.join(RUNTIME_DEPENDS)}",
                "Description: Local-first LLM cockpit desktop application",
                " LLM Cockpit wraps the existing FastAPI runtime in a Linux",
                " desktop package. The window engine (Qt WebEngine) travels",
                " inside the package: no browser and no Python are required on",
                " the machine.",
            ]
        )
        + "\n",
    )

    write_file(
        DEBIAN / "postinst",
        "\n".join(
            [
                "#!/bin/sh",
                "set -e",
                "if command -v gtk-update-icon-cache >/dev/null 2>&1; then",
                "  gtk-update-icon-cache -q /usr/share/icons/hicolor || true",
                "fi",
                "if command -v update-desktop-database >/dev/null 2>&1; then",
                "  update-desktop-database /usr/share/applications || true",
                "fi",
                "exit 0",
            ]
        )
        + "\n",
        0o755,
    )

    write_file(
        DEBIAN / "prerm",
        "\n".join(
            [
                "#!/bin/sh",
                "set -e",
                "exit 0",
            ]
        )
        + "\n",
        0o755,
    )


def build_deb() -> Path:
    version = package_version()
    pkg_name = f"llm-cockpit_{version}_amd64.deb"
    out = DIST / pkg_name
    run(["dpkg-deb", "--build", "--root-owner-group", str(PKG_ROOT), str(out)])
    return out


def main() -> int:
    clean_tree()
    bundle = build_bundle()
    copied = copy_bundle(bundle)
    assemble_deb_files(copied)
    out = build_deb()
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
