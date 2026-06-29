"""Tests V6 : agrégation du scoreboard par (rôle, modèle)."""

from app import config
from app.db import store
from app.evals import scoreboard


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))


def _result(**over) -> dict:
    base = {
        "case": "c", "model": "m", "status": "ok", "latency_ms": 100.0,
        "passed": 2, "total": 2, "score": 1.0, "checks": [],
        "error": None, "response_preview": None,
    }
    base.update(over)
    return base


def test_scoreboard_aggregates_by_role_model(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    run_id = store.insert_eval_run(
        ts="2026-06-28T10:00:00+00:00", suite="s", role="code",
        models=["A", "B"], status="completed", total_cases=2,
    )
    # Modèle A : 2 cas, 4/4 checks, latence 100/200.
    store.insert_eval_result(run_id, "s", "code", _result(model="A", latency_ms=100.0))
    store.insert_eval_result(run_id, "s", "code", _result(model="A", latency_ms=200.0))
    # Modèle B : 2 cas, 2/4 checks, 1 erreur.
    store.insert_eval_result(
        run_id, "s", "code", _result(model="B", passed=2, total=2)
    )
    store.insert_eval_result(
        run_id, "s", "code",
        _result(model="B", status="error", passed=0, total=2, latency_ms=None),
    )

    board = scoreboard.compute_scoreboard()
    by_model = {r.model: r for r in board}

    a = by_model["A"]
    assert a.role == "code"
    assert a.cases == 2
    assert a.checks_passed == 4 and a.checks_total == 4
    assert a.pass_rate == 1.0
    assert a.avg_latency_ms == 150.0
    assert a.errors == 0
    assert a.runs == 1

    b = by_model["B"]
    assert b.checks_passed == 2 and b.checks_total == 4
    assert b.pass_rate == 0.5
    assert b.errors == 1

    # Trié par rôle puis taux de réussite décroissant : A (1.0) avant B (0.5).
    assert [r.model for r in board] == ["A", "B"]


def test_scoreboard_role_filter(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    run_id = store.insert_eval_run(
        ts="2026-06-28T10:00:00+00:00", suite="s", role="code",
        models=["A"], status="completed", total_cases=1,
    )
    store.insert_eval_result(run_id, "s", "code", _result(model="A"))
    store.insert_eval_result(run_id, "s", "json", _result(model="A", role="json"))

    code_board = scoreboard.compute_scoreboard(role="code")
    assert all(r.role == "code" for r in code_board)
    assert len(code_board) == 1


def test_empty_scoreboard(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    assert scoreboard.compute_scoreboard() == []
