#!/usr/bin/env python3
"""Install the Linux desktop bundle into the current user profile."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "linux" / "LLM-Cockpit"
APP_NAME = "llm-cockpit"


def user_dir(env_key: str, fallback: Path) -> Path:
    value = os.getenv(env_key)
    return Path(value) if value else fallback


def install_dir() -> Path:
    base = user_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return base / APP_NAME


def applications_dir() -> Path:
    return user_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "applications"


ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def icons_root() -> Path:
    base = user_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return base / "icons" / "hicolor"


def icons_dir(size: int = 256) -> Path:
    """Directory for one icon size. The theme spec wants a PNG per size."""
    return icons_root() / f"{size}x{size}" / "apps"


def bin_dir() -> Path:
    base = user_dir("XDG_BIN_HOME", Path.home() / ".local" / "bin")
    return base


def refresh_desktop_caches() -> None:
    """Make the desktop pick up the new icon and menu entry.

    Without this the icon theme cache keeps answering from its previous
    contents and the launcher shows a generic or stale icon.
    `--ignore-theme-index` is required because a user-level hicolor tree has
    no index.theme, and gtk-update-icon-cache refuses to run without one.
    """
    commands = [
        ["gtk-update-icon-cache", "--ignore-theme-index", "-f", "-q",
         str(icons_root())],
        ["update-desktop-database", str(applications_dir())],
    ]
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        subprocess.run(command, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    if not BUNDLE.exists():
        raise SystemExit(
            f"bundle not found: {BUNDLE}\n"
            "Run first: uv run python scripts/build_linux_bundle.py"
        )

    target = install_dir()
    app_bin = target / "LLM-Cockpit"
    target.mkdir(parents=True, exist_ok=True)
    applications_dir().mkdir(parents=True, exist_ok=True)
    for size in ICON_SIZES:
        icons_dir(size).mkdir(parents=True, exist_ok=True)
    bin_dir().mkdir(parents=True, exist_ok=True)

    if app_bin.exists():
        if app_bin.is_dir():
            shutil.rmtree(app_bin)
        else:
            app_bin.unlink()
    shutil.copytree(BUNDLE, app_bin, symlinks=True)

    main_exe = app_bin / "LLM-Cockpit"
    if main_exe.exists():
        main_exe.chmod(main_exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    launcher = bin_dir() / "llm-cockpit"
    launcher.write_text(
        "#!/usr/bin/env sh\nexec \"{}\" \"$@\"\n".format(main_exe),
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    for size in ICON_SIZES:
        shutil.copy2(
            ROOT / "app" / "static" / "icons" / f"{size}.png",
            icons_dir(size) / f"{APP_NAME}.png",
        )

    desktop_file = applications_dir() / "llm-cockpit.desktop"
    desktop_file.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Version=1.0",
                "Type=Application",
                "Name=LLM Cockpit",
                "Comment=Local-first LLM cockpit",
                f"Exec={launcher}",
                "Icon=llm-cockpit",
                "Terminal=false",
                "Categories=Development;",
                "StartupWMClass=LLM-Cockpit",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    refresh_desktop_caches()

    print(f"installed in {target}")
    print(f"desktop file: {desktop_file}")
    print(f"launcher: {launcher}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
