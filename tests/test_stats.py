"""Tests V5 : agrégations de stats (percentiles, taux d'erreur, buckets)."""

from app import config
from app.db import store
from app.services import stats


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
        "latency_ms": 10.0,
        "prompt_tokens": None,
        "completion_tokens": None,
        "error": None,
        "prompt": None,
    }
    base.update(over)
    return base


def test_empty_window_is_zeros(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    summary = stats.compute_stats()
    assert summary.total == 0
    assert summary.errors == 0
    assert summary.error_rate == 0.0
    assert summary.latency_p50_ms is None
    assert summary.latency_p95_ms is None
    assert summary.by_model == []


def test_percentiles_and_error_rate(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    # Latences 10,20,30,40 ; 1 erreur sur 4.
    for lat in (10.0, 20.0, 30.0):
        store.insert_request_log(_row(latency_ms=lat))
    store.insert_request_log(_row(latency_ms=40.0, status="error"))

    summary = stats.compute_stats()
    assert summary.total == 4
    assert summary.errors == 1
    assert summary.error_rate == 0.25
    # nearest-rank : p50 → 20, p95 → 40
    assert summary.latency_p50_ms == 20.0
    assert summary.latency_p95_ms == 40.0


def test_buckets_by_model_and_app(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    store.insert_request_log(_row(model="a", app="appA"))
    store.insert_request_log(_row(model="a", app="appB", status="error"))
    store.insert_request_log(_row(model="b", app="appA"))

    summary = stats.compute_stats()
    by_model = {b.key: b for b in summary.by_model}
    assert by_model["a"].count == 2
    assert by_model["a"].error_count == 1
    assert by_model["b"].count == 1
    by_app = {b.key: b for b in summary.by_app}
    assert by_app["appA"].count == 2
    assert by_app["appA"].error_count == 0


def test_tokens_absent_stay_none(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    store.insert_request_log(_row(prompt_tokens=None, completion_tokens=None))
    logs = store.query_logs()
    assert logs[0]["prompt_tokens"] is None
    assert logs[0]["completion_tokens"] is None
