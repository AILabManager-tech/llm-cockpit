#!/usr/bin/env python3
"""Build a desktop bundle for LLM Cockpit with PyInstaller.

Same bundle as `build_linux_bundle.py`, written to the default `dist/`.
The PyInstaller options themselves live in `build_linux_bundle.common_args()`
so the two scripts cannot drift apart.

Usage:
  uv run python scripts/build_desktop.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_linux_bundle import ROOT, common_args  # noqa: E402


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        *common_args(),
        str(ROOT / "app" / "desktop.py"),
    ]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
