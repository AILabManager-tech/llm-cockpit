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
    assert "falling back to the browser" in capsys.readouterr().out


def test_native_window_returns_true_when_it_opens(monkeypatch):
    fake = types.SimpleNamespace(
        create_window=lambda *a, **k: None, start=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "webview", fake)
    assert desktop._open_native_window("http://127.0.0.1:1/") is True
