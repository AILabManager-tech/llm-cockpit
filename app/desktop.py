"""Desktop launcher for LLM Cockpit.

Starts the existing FastAPI runtime on localhost and shows it in a dedicated
application window — no tab, no address bar. Three strategies, in order:

1. `pywebview` on the Qt/QtWebEngine backend shipped with the desktop build.
   This is the nominal path: the window engine travels inside the bundle, so
   it depends on no browser and no system toolkit.
2. an installed Chromium-family browser in `--app` mode, with its own profile
   and window class — used when the Qt bindings are absent, e.g. a plain
   `uv sync` without the `desktop` extra.
3. the default browser as a last resort, so the cockpit is never unreachable.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx


PORT_START = 22050
PORT_END = 22099

# Matches the WM_CLASS the frozen binary reports, so a single
# StartupWMClass in the .desktop files covers both window paths.
WM_CLASS = "LLM-Cockpit"
WINDOW_TITLE = "LLM Cockpit"
WINDOW_SIZE = (1480, 980)

# Chromium-family executables that support `--app=<url>`, most preferred first.
APP_MODE_BROWSERS = (
    "brave-browser",
    "brave",
    "chromium",
    "chromium-browser",
    "google-chrome-stable",
    "google-chrome",
    "microsoft-edge",
    "vivaldi",
)


def _default_data_dir() -> Path:
    home = Path.home()
    system = platform.system().lower()
    if system == "windows":
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return base / "LLM Cockpit"
    if system == "darwin":
        return home / "Library" / "Application Support" / "LLM Cockpit"
    xdg = os.getenv("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "llm-cockpit"
    return home / ".local" / "share" / "llm-cockpit"


def _find_free_port(start: int = PORT_START, end: int = PORT_END) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free port found in range {start}-{end}")


def _wait_until_ready(port: int, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"the desktop server did not start on {url}")


def _configure_env(data_dir: Path, port: int) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HOST", "127.0.0.1")
    os.environ["PORT"] = str(port)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _start_server(port: int):
    from app.main import app
    import uvicorn

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_until_ready(port)
    return server, thread


def _window_icon() -> Path | None:
    """Path to the window icon, or None when it cannot be located.

    In a checkout this module sits in `app/`, so the icon is a sibling of the
    module. In the frozen bundle `desktop.py` is the entry script and lands at
    the bundle root, one level above `app/` — hence the two candidates.
    """
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "static" / "llm-cockpit-favicon.svg",
        here / "app" / "static" / "llm-cockpit-favicon.svg",
    ):
        if candidate.is_file():
            return candidate
    return None


def _qt_backend_available() -> bool:
    """True when the embedded Qt/QtWebEngine backend can be imported.

    The desktop build ships PySide6, so this holds both in a checkout with the
    `desktop` extra and inside the frozen bundle. Selecting it explicitly keeps
    the window identical everywhere instead of depending on whichever toolkit
    happens to be installed on the machine.
    """
    try:
        import webview.platforms.qt  # noqa: F401
    except Exception:  # noqa: BLE001 - missing bindings, missing Qt libs, ...
        return False
    return True


def _open_native_window(url: str) -> bool:
    """Open the cockpit in a native window.

    Returns False when no native window can be opened (pywebview missing, or
    no GUI backend on this machine) so the caller can fall back to a windowed
    browser instead of failing.
    """
    try:
        import webview
    except ImportError:
        return False

    icon = _window_icon()
    try:
        webview.create_window(
            WINDOW_TITLE,
            url,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=(1200, 780),
            resizable=True,
            confirm_close=True,
        )
        # `icon` belongs to start(), not create_window() (pywebview >= 5).
        # `gui=None` lets pywebview pick; we pin Qt whenever it is available.
        webview.start(
            debug=False,
            icon=str(icon) if icon else None,
            gui="qt" if _qt_backend_available() else None,
        )
    except Exception as exc:  # noqa: BLE001 - any GUI backend failure
        print(f"native window unavailable ({exc}); using the application window")
        return False
    return True


def _find_app_mode_browser() -> str | None:
    """Path to a Chromium-family browser able to open a real app window."""
    for name in APP_MODE_BROWSERS:
        path = shutil.which(name)
        if path:
            return path
    return None


def _app_mode_argv(browser: str, url: str, profile_dir: Path) -> list[str]:
    width, height = WINDOW_SIZE
    return [
        browser,
        f"--app={url}",
        # Dedicated profile: keeps the cockpit out of the user's browsing
        # session AND guarantees a process we can wait on (sharing a running
        # instance would return immediately).
        f"--user-data-dir={profile_dir}",
        f"--class={WM_CLASS}",
        f"--window-size={width},{height}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def _open_app_window(url: str, data_dir: Path) -> bool:
    """Open a dedicated window through a Chromium-family browser.

    Returns False when no such browser is installed. Blocks until the window
    is closed.
    """
    browser = _find_app_mode_browser()
    if browser is None:
        return False

    profile_dir = data_dir / "window-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    argv = _app_mode_argv(browser, url, profile_dir)
    try:
        process = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError as exc:
        print(f"application window unavailable ({exc}); falling back to the browser")
        return False
    process.wait()
    return True


def _open_in_browser(url: str) -> None:
    """Serve until interrupted, with the page opened in the default browser."""
    import webbrowser

    print(f"LLM Cockpit is running on {url} (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM Cockpit desktop launcher")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help=f"Local port (0 = auto in {PORT_START}-{PORT_END})",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Writable directory for local data",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_dir = args.data_dir or _default_data_dir()
    port = args.port if args.port else _find_free_port()
    _configure_env(data_dir, port)

    server, thread = _start_server(port)
    url = f"http://127.0.0.1:{port}/"
    try:
        if not _open_native_window(url) and not _open_app_window(url, data_dir):
            _open_in_browser(url)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main(sys.argv[1:])
