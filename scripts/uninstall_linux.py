#!/usr/bin/env python3
"""Remove the Linux desktop installation from the current user profile."""

from __future__ import annotations

import shutil
from pathlib import Path


APP_NAME = "llm-cockpit"


def main() -> int:
    data_base = Path.home() / ".local" / "share"
    install_root = data_base / APP_NAME
    desktop_file = data_base / "applications" / f"{APP_NAME}.desktop"
    icon_file = data_base / "icons" / "hicolor" / "scalable" / "apps" / "llm-cockpit.svg"
    launcher = Path.home() / ".local" / "bin" / APP_NAME

    for path in [desktop_file, icon_file, launcher]:
        if path.exists():
            path.unlink()

    if install_root.exists():
        shutil.rmtree(install_root)

    print("uninstalled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
