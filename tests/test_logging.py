"""Tests V5 : intégration logging du gateway (une requête → une ligne)."""

import json

import httpx
import respx
from fastapi.testclient import TestClient

from app import config
from app.db import store
from app.main import app

client = TestClient(app)
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
    "message": {"role": "assistant", "content": "Bonjour"},
    "done": True,
    "total_duration": 5_000_000,
    "eval_count": 3,
    "prompt_eval_count": 7,
}
CHAT_NO_USAGE = {
    "model": "llama3.2:latest",
    "message": {"role": "assistant", "content": "Bonjour"},
    "done": True,
}


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))


def _assign(tmp_path, role, model, provider="ollama"):
    (tmp_path / "roles.json").write_text(
        json.dumps({"assignments": {role: {"model": model, "provider": provider}}}),
        encoding="utf-8",
    )


def _mock_inventory():
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )


@respx.mock
def test_chat_produces_exactly_one_log(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "salut"}]},
        headers={"X-Cockpit-App": "demo-app"},
    )
    assert resp.status_code == 200
    logs = store.query_logs()
    assert len(logs) == 1
    row = logs[0]
    assert row["status"] == "ok"
    assert row["app"] == "demo-app"
    assert row["resolved_role"] == "chat"
    assert row["provider"] == "ollama"
    assert row["model"] == "llama3.2:latest"
    assert row["latency_ms"] is not None
    assert row["prompt_tokens"] == 7
    assert row["completion_tokens"] == 3


@respx.mock
def test_refused_request_is_logged(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()  # rôle "embedding" non assigné
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "embedding", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 400
    logs = store.query_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "refused"
    assert logs[0]["http_status"] == 400


@respx.mock
def test_tokens_absent_logged_as_none(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_NO_USAGE)
    )
    client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "x"}]},
    )
    row = store.query_logs()[0]
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None


@respx.mock
def test_prompt_not_stored_by_default(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )
    client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "secret"}]},
    )
    row = store.query_logs()[0]
    assert row["prompt"] is None  # LOG_PROMPTS=False par défaut


@respx.mock
def test_prompt_stored_truncated_when_enabled(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "LOG_PROMPTS", True)
    monkeypatch.setattr(config, "LOG_PROMPT_MAX_CHARS", 5)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )
    client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "abcdefghij"}]},
    )
    row = store.query_logs()[0]
    assert row["prompt"] == "abcde"  # tronqué à 5 caractères


@respx.mock
def test_logging_failure_does_not_break_request(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )

    def _boom(_row):
        raise RuntimeError("log backend down")

    # Échec au niveau backend ; logging_mw doit l'avaler (best-effort absolu).
    monkeypatch.setattr(store, "insert_request_log", _boom)
    # Le logging casse, mais la requête gateway doit aboutir malgré tout.
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "Bonjour"
