#!/usr/bin/env python3
"""Build the Linux desktop bundle for LLM Cockpit.

Produces a PyInstaller onedir bundle under `dist/linux/LLM-Cockpit/`.

This module is the single source of truth for the PyInstaller options:
`build_desktop.py` reuses `common_args()` so the two entry points can never
diverge and ship a differently-broken bundle.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "linux"

# The Qt backend is imported by name inside pywebview, and qtpy resolves its
# bindings at runtime; neither survives PyInstaller's static analysis, so both
# are pulled in explicitly.
HIDDEN_IMPORTS = (
    "webview.platforms.qt",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
)


# Qt modules the cockpit never touches. Excluding them keeps the bundle to
# what a web view actually needs.
UNUSED_QT_MODULES = (
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtQuick3D",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
)


def add_data(src: Path, dst: str) -> str:
    return f"{src}{os.pathsep}{dst}"


def _excluded_qt_modules() -> list[str]:
    args: list[str] = []
    for module in UNUSED_QT_MODULES:
        args += ["--exclude-module", module]
    return args


def common_args() -> list[str]:
    """PyInstaller options shared by every desktop build."""
    args = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "LLM-Cockpit",
        "--add-data",
        add_data(ROOT / "app" / "templates", "app/templates"),
        "--add-data",
        add_data(ROOT / "app" / "static", "app/static"),
        "--add-data",
        add_data(ROOT / "app" / "db" / "schema.sql", "app/db"),
        "--add-data",
        add_data(ROOT / "app" / "evals" / "suites", "app/evals/suites"),
        # QtWebEngine (the window engine) is shipped inside the bundle so the
        # app depends on no browser and no system toolkit. The PySide6 hooks
        # pull in QtWebEngineProcess and its resources from the hidden imports
        # below; `--collect-all PySide6` would work too but drags in every
        # unused Qt module (Qt3D, Charts, Multimedia, Quick3D...) and doubles
        # the bundle for nothing.
        *_excluded_qt_modules(),
    ]
    for module in HIDDEN_IMPORTS:
        args += ["--hidden-import", module]
    return args


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        *common_args(),
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build" / "linux"),
        "--specpath",
        str(ROOT / "build" / "linux-spec"),
        str(ROOT / "app" / "desktop.py"),
    ]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
