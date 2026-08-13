import socket
import sys
import types

import pytest

from app import desktop


def test_find_free_port_stays_in_allocated_range():
    port = desktop._find_free_port()
    assert desktop.PORT_START <= port <= desktop.PORT_END


def test_find_free_port_skips_a_busy_port():
    first = desktop._find_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", first))
        busy.listen(1)
        assert desktop._find_free_port() != first


def test_find_free_port_raises_when_range_is_exhausted():
    taken = desktop._find_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", taken))
        busy.listen(1)
        with pytest.raises(RuntimeError):
            desktop._find_free_port(taken, taken)


def test_parser_defaults():
    args = desktop.build_parser().parse_args([])
    assert args.port == 0
    assert args.data_dir is None


def test_native_window_falls_back_when_pywebview_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", None)
    assert desktop._open_native_window("http://127.0.0.1:1/") is False


def test_native_window_falls_back_when_gui_backend_missing(monkeypatch, capsys):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("no GTK/QT backend")

    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=_boom)
    monkeypatch.setitem(sys.modules, "webview", fake)
    assert desktop._open_native_window("http://127.0.0.1:1/") is False
    assert "using the application window" in capsys.readouterr().out


def test_app_mode_argv_asks_for_a_windowed_app(tmp_path):
    argv = desktop._app_mode_argv("/usr/bin/brave-browser", "http://x/", tmp_path)
    assert argv[0] == "/usr/bin/brave-browser"
    assert "--app=http://x/" in argv
    assert f"--user-data-dir={tmp_path}" in argv
    assert f"--class={desktop.WM_CLASS}" in argv


def test_app_window_returns_false_without_a_chromium_browser(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.shutil, "which", lambda _name: None)
    assert desktop._open_app_window("http://x/", tmp_path) is False


def test_app_window_waits_for_the_window_to_close(monkeypatch, tmp_path):
    seen = {}

    class _Process:
        def wait(self):
            seen["waited"] = True

    def _popen(argv, **_kwargs):
        seen["argv"] = argv
        return _Process()

    monkeypatch.setattr(desktop.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(desktop.subprocess, "Popen", _popen)
    assert desktop._open_app_window("http://x/", tmp_path) is True
    assert seen["waited"] is True
    assert "--app=http://x/" in seen["argv"]
    assert (tmp_path / "window-profile").is_dir()


def test_native_window_returns_true_when_it_opens(monkeypatch):
    fake = types.SimpleNamespace(
        create_window=lambda *a, **k: None, start=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "webview", fake)
    assert desktop._open_native_window("http://127.0.0.1:1/") is True


def test_native_window_pins_the_qt_backend_when_available(monkeypatch):
    started = {}
    fake = types.SimpleNamespace(
        create_window=lambda *a, **k: None,
        start=lambda *a, **k: started.update(k),
    )
    monkeypatch.setitem(sys.modules, "webview", fake)
    monkeypatch.setattr(desktop, "_qt_backend_available", lambda: True)
    assert desktop._open_native_window("http://127.0.0.1:1/") is True
    assert started["gui"] == "qt"


def test_native_window_lets_pywebview_choose_without_qt(monkeypatch):
    started = {}
    fake = types.SimpleNamespace(
        create_window=lambda *a, **k: None,
        start=lambda *a, **k: started.update(k),
    )
    monkeypatch.setitem(sys.modules, "webview", fake)
    monkeypatch.setattr(desktop, "_qt_backend_available", lambda: False)
    assert desktop._open_native_window("http://127.0.0.1:1/") is True
    assert started["gui"] is None


def test_window_icon_found_next_to_the_module():
    icon = desktop._window_icon()
    assert icon is not None
    assert icon.is_file()
    assert icon.parent.name == "icons"


def test_window_icon_found_one_level_up_like_the_frozen_bundle(
    monkeypatch, tmp_path
):
    # Frozen layout: desktop.py at the root, assets under app/static/.
    bundled = tmp_path / "app" / "static" / "icons"
    bundled.mkdir(parents=True)
    (bundled / "256.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(desktop, "__file__", str(tmp_path / "desktop.py"))
    assert desktop._window_icon() == bundled / "256.png"


def test_window_icon_is_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop, "__file__", str(tmp_path / "desktop.py"))
    assert desktop._window_icon() is None


def test_qt_backend_detection_is_import_based(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview.platforms.qt", None)
    assert desktop._qt_backend_available() is False
