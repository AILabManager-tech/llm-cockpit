"""Tests V6 : runner d'évaluations (routage réel mocké, persistance SQLite)."""

import asyncio

import httpx
import pytest
import respx

from app import config
from app.db import store
from app.evals.runner import EvalRunner, EvalValidationError, SuiteError, list_suites
from app.services.registry import RegistryService
from app.services.routing import RoutingService

OLLAMA_BASE = "http://127.0.0.1:11434"

TAGS_LLAMA = {
    "models": [
        {
            "name": "llama3.2:latest",
            "model": "llama3.2:latest",
            "size": 1,
            "digest": "d1",
            "details": {"family": "llama", "quantization_level": "Q4_K_M"},
        }
    ]
}
PS_EMPTY = {"models": []}
CHAT_OK = {
    "model": "llama3.2:latest",
    "message": {"role": "assistant", "content": "OK"},
    "done": True,
    "total_duration": 5_000_000,
    "eval_count": 1,
    "prompt_eval_count": 4,
}

SUITE_YAML = """
name: tmp_suite
role: chat
cases:
  - name: says_ok
    prompt: "Réponds OK"
    checks:
      - non_empty
      - contains:OK
"""


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    monkeypatch.setattr(config, "EVALS_DIR", str(tmp_path / "evals"))
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))
    (tmp_path / "evals").mkdir()


def _write_suite(tmp_path, name, content):
    (tmp_path / "evals" / f"{name}.yaml").write_text(content, encoding="utf-8")


def _runner() -> EvalRunner:
    registry = RegistryService()
    return EvalRunner(registry, RoutingService(registry))


def _mock_inventory():
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )


@respx.mock
def test_run_two_models_one_ok_one_error(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_suite(tmp_path, "tmp_suite", SUITE_YAML)
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )

    summary = asyncio.run(
        _runner().run("tmp_suite", ["llama3.2:latest", "ghost:404"])
    )
    assert summary.status == "completed"
    assert summary.total_cases == 1
    assert len(summary.results) == 2  # 1 cas × 2 modèles

    by_model = {r.model: r for r in summary.results}
    ok = by_model["llama3.2:latest"]
    assert ok.status == "ok"
    assert ok.passed == 2 and ok.total == 2
    assert ok.score == 1.0
    assert ok.latency_ms is not None

    # Modèle introuvable → cas error, run non cassé.
    ghost = by_model["ghost:404"]
    assert ghost.status == "error"
    assert ghost.error


@respx.mock
def test_run_persists_to_sqlite(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_suite(tmp_path, "tmp_suite", SUITE_YAML)
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )
    summary = asyncio.run(_runner().run("tmp_suite", ["llama3.2:latest"]))

    runs = store.query_eval_runs()
    assert len(runs) == 1
    assert runs[0]["suite"] == "tmp_suite"
    assert runs[0]["models"] == ["llama3.2:latest"]

    results = store.get_eval_results(summary.id)
    assert len(results) == 1
    assert results[0]["case"] == "says_ok"
    assert results[0]["passed"] == 2
    assert len(results[0]["checks"]) == 2


def test_unknown_suite_raises(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    with pytest.raises(SuiteError):
        asyncio.run(_runner().run("does_not_exist", ["m"]))


def test_unknown_check_in_suite_raises(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_suite(
        tmp_path, "bad",
        "name: bad\ncases:\n  - name: c\n    prompt: x\n    checks:\n      - bogus\n",
    )
    with pytest.raises(EvalValidationError):
        asyncio.run(_runner().run("bad", ["m"]))


def test_no_models_raises(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_suite(tmp_path, "tmp_suite", SUITE_YAML)
    with pytest.raises(EvalValidationError):
        asyncio.run(_runner().run("tmp_suite", []))


def test_bundled_suites_listed():
    # Les suites livrées dans le paquet sont valides et listables.
    names = list_suites()
    assert "json_strict" in names
    assert "code_python" in names
