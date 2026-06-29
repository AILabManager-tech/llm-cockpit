"""Tests V5 : couche SQLite (store)."""

import sqlite3

from app import config
from app.db import store


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))


def _row(**over) -> dict:
    base = {
        "ts": "2026-06-28T10:00:00+00:00",
        "route": "/v1/chat/completions",
        "app": "appA",
        "requested": "chat",
        "resolved_role": "chat",
        "provider": "ollama",
        "model": "llama3.2:latest",
        "status": "ok",
        "http_status": 200,
        "latency_ms": 12.5,
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "error": None,
        "prompt": None,
    }
    base.update(over)
    return base


def test_insert_and_query(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    store.insert_request_log(_row())
    logs = store.query_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["model"] == "llama3.2:latest"
    assert logs[0]["status"] == "ok"
    assert (tmp_path / "cockpit.db").exists()


def test_query_filters(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    store.insert_request_log(_row(model="llama3.2:latest", provider="ollama"))
    store.insert_request_log(
        _row(model="phi-3", provider="lmstudio", app="appB", status="error")
    )
    assert len(store.query_logs(model="phi-3")) == 1
    assert len(store.query_logs(provider="ollama")) == 1
    assert len(store.query_logs(app="appB")) == 1
    assert len(store.query_logs(status="error")) == 1
    assert len(store.query_logs()) == 2


def test_insert_is_best_effort_on_db_error(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)

    def _boom():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "connect", _boom)
    # Ne doit pas lever : best-effort.
    store.insert_request_log(_row())


def test_query_order_newest_first(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    store.insert_request_log(_row(model="m1"))
    store.insert_request_log(_row(model="m2"))
    logs = store.query_logs()
    assert logs[0]["model"] == "m2"  # id DESC
