#!/usr/bin/env python3
"""Remove the Linux desktop installation from the current user profile.

Path resolution is imported from `install_linux.py` on purpose: computing it
a second time here is how this script used to look at `~/.local/share` while
the installer had honoured `XDG_DATA_HOME`, remove nothing, and still report
success.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from app.desktop import _default_data_dir  # noqa: E402
from install_linux import (  # noqa: E402
    APP_NAME,
    applications_dir,
    bin_dir,
    icons_dir,
    install_dir,
)


def main() -> int:
    install_root = install_dir()
    files = [
        applications_dir() / f"{APP_NAME}.desktop",
        icons_dir() / f"{APP_NAME}.svg",
        bin_dir() / APP_NAME,
    ]

    removed: list[Path] = []
    for path in files:
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed.append(path)

    if install_root.exists():
        shutil.rmtree(install_root)
        removed.append(install_root)

    if not removed:
        print(f"nothing to uninstall (looked under {install_root.parent})")
        return 0

    for path in removed:
        print(f"removed {path}")

    # Never removed by an uninstall: gateway history, role assignments,
    # ingested documents, datasets and adapters all live there.
    data_dir = _default_data_dir()
    if data_dir.exists():
        print(f"kept your data in {data_dir} (delete it by hand if you want it gone)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
