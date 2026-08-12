#!/usr/bin/env python3
"""Build the Linux desktop bundle for LLM Cockpit.

Produces a PyInstaller onedir bundle under `dist/linux/LLM-Cockpit/`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "linux"


def add_data(src: Path, dst: str) -> str:
    return f"{src}{os.pathsep}{dst}"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "LLM-Cockpit",
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build" / "linux"),
        "--specpath",
        str(ROOT / "build" / "linux-spec"),
        "--add-data",
        add_data(ROOT / "app" / "templates", "app/templates"),
        "--add-data",
        add_data(ROOT / "app" / "static", "app/static"),
        "--add-data",
        add_data(ROOT / "app" / "db" / "schema.sql", "app/db"),
        "--add-data",
        add_data(ROOT / "app" / "evals" / "suites", "app/evals/suites"),
        str(ROOT / "app" / "desktop.py"),
    ]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
