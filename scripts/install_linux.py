#!/usr/bin/env python3
"""Install the Linux desktop bundle into the current user profile."""

from __future__ import annotations

import os
import shutil
import stat
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


def icons_dir() -> Path:
    base = user_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return base / "icons" / "hicolor" / "scalable" / "apps"


def bin_dir() -> Path:
    base = user_dir("XDG_BIN_HOME", Path.home() / ".local" / "bin")
    return base


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
    icons_dir().mkdir(parents=True, exist_ok=True)
    bin_dir().mkdir(parents=True, exist_ok=True)

    if app_bin.exists():
        if app_bin.is_dir():
            shutil.rmtree(app_bin)
        else:
            app_bin.unlink()
    shutil.copytree(BUNDLE, app_bin)

    main_exe = app_bin / "LLM-Cockpit"
    if main_exe.exists():
        main_exe.chmod(main_exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    launcher = bin_dir() / "llm-cockpit"
    launcher.write_text(
        "#!/usr/bin/env sh\nexec \"{}\" \"$@\"\n".format(main_exe),
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    icon_src = ROOT / "app" / "static" / "llm-cockpit-favicon.svg"
    icon_dst = icons_dir() / "llm-cockpit.svg"
    shutil.copy2(icon_src, icon_dst)

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
                "Categories=Development;Utility;",
                "StartupWMClass=LLM Cockpit V8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"installed in {target}")
    print(f"desktop file: {desktop_file}")
    print(f"launcher: {launcher}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
