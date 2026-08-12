"""Desktop launcher for LLM Cockpit.

Starts the existing FastAPI runtime on localhost and opens it in a native
window when `pywebview` is available.
"""

from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
import threading
import time
from pathlib import Path

import httpx


PORT_START = 22050
PORT_END = 22099


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


def _open_native_window(url: str) -> bool:
    """Open the cockpit in a native window.

    Returns False when no native window can be opened (pywebview missing, or
    no GTK/QT backend on this machine) so the caller can fall back to the
    default browser instead of failing.
    """
    try:
        import webview
    except ImportError:
        return False

    icon = Path(__file__).resolve().parent / "static" / "llm-cockpit-favicon.svg"
    try:
        webview.create_window(
            "LLM Cockpit V8",
            url,
            width=1480,
            height=980,
            min_size=(1200, 780),
            resizable=True,
            confirm_close=True,
        )
        # `icon` belongs to start(), not create_window() (pywebview >= 5).
        webview.start(debug=False, icon=str(icon))
    except Exception as exc:  # noqa: BLE001 - any GUI backend failure
        print(f"native window unavailable ({exc}); falling back to the browser")
        return False
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
        if not _open_native_window(url):
            _open_in_browser(url)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main(sys.argv[1:])
