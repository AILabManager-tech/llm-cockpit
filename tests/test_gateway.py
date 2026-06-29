"""Tests V4 : gateway OpenAI-compatible (/v1/chat/completions, /v1/models)."""

import json

import httpx
import respx
from fastapi.testclient import TestClient

from app import config
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
CHAT_OLLAMA = {
    "model": "llama3.2:latest",
    "message": {"role": "assistant", "content": "Bonjour"},
    "done": True,
    "total_duration": 5_000_000,
    "eval_count": 3,
    "prompt_eval_count": 7,
}


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )


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


# --- chat routé par rôle → format OpenAI --------------------------------


@respx.mock
def test_chat_completions_routed_by_role(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    chat = respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OLLAMA)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "salut"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Bonjour"
    assert body["model"] == "llama3.2:latest"  # rôle résolu vers le modèle réel
    assert body["x_cockpit_route"]["resolved_role"] == "chat"
    assert body["x_cockpit_route"]["provider"] == "ollama"
    assert chat.called


# --- chat routé par modèle réel -----------------------------------------


@respx.mock
def test_chat_completions_routed_by_real_model(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OLLAMA)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3.2:latest",
            "messages": [{"role": "user", "content": "salut"}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["x_cockpit_route"]["resolved_role"] is None


# --- rôle non assigné → erreur OpenAI -----------------------------------


@respx.mock
def test_chat_unassigned_role_openai_error(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    # /api/chat NON enregistré : aucune génération ne doit partir.
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "embedding", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert "non assigné" in body["error"]["message"]


# --- provider injoignable pendant le chat → 502 OpenAI ------------------


@respx.mock
def test_chat_provider_down_502(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        side_effect=httpx.ConnectError("refused")
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 502
    assert "error" in resp.json()


# --- /v1/models : modèles réels + alias de rôles ------------------------


@respx.mock
def test_v1_models_lists_models_and_role_aliases(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["data"]}
    assert "llama3.2:latest" in ids
    assert "role:chat" in ids
    assert "role:experimental" in ids


# --- GATEWAY_ENABLED=0 → /v1/* en 404 -----------------------------------


def test_gateway_disabled_404(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "GATEWAY_ENABLED", False)
    chat = client.post(
        "/v1/chat/completions",
        json={"model": "chat", "messages": [{"role": "user", "content": "x"}]},
    )
    models = client.get("/v1/models")
    assert chat.status_code == 404
    assert models.status_code == 404


# --- /api/routes : table de routage -------------------------------------


@respx.mock
def test_api_routes_table(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_inventory()
    resp = client.get("/api/routes")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["requested"] for r in data] == list(config.ROLES)
    chat = next(r for r in data if r["requested"] == "chat")
    assert chat["ok"] is True
    assert chat["model"] == "llama3.2:latest"
