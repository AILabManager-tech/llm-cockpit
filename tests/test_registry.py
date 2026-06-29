"""Tests V3 : registry multi-provider (agrégation, drift, persistance)."""

import json

import httpx
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)
OLLAMA_BASE = "http://127.0.0.1:11434"
OPENAI_BASE = "http://127.0.0.1:1234"

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
OPENAI_MODELS = {"data": [{"id": "qwen2.5-coder"}, {"id": "phi-3"}]}


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )


def _write_providers(tmp_path, providers):
    (tmp_path / "providers.json").write_text(
        json.dumps({"providers": providers}), encoding="utf-8"
    )


# --- provider Ollama par défaut quand aucun fichier ---------------------


@respx.mock
def test_default_provider_is_ollama(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "ollama"
    assert data[0]["kind"] == "ollama"
    assert data[0]["reachable"] is True
    assert data[0]["capabilities"]["load"] is True


# --- enregistrement + refus des doublons --------------------------------


def test_register_and_duplicates(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    body = {"id": "lmstudio", "kind": "openai_compat", "base_url": OPENAI_BASE}
    resp = client.post("/api/providers", json=body)
    assert resp.status_code == 201
    assert (tmp_path / "providers.json").exists()

    # id dupliqué (l'ollama par défaut n'est plus là car fichier écrit ;
    # on re-poste le même id) → 409
    dup_id = client.post("/api/providers", json=body)
    assert dup_id.status_code == 409

    # base_url dupliqué, id différent → 409
    dup_url = client.post(
        "/api/providers",
        json={"id": "autre", "kind": "openai_compat", "base_url": OPENAI_BASE},
    )
    assert dup_url.status_code == 409


def test_register_unknown_kind_400(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    resp = client.post(
        "/api/providers",
        json={"id": "x", "kind": "anthropic", "base_url": "http://127.0.0.1:9"},
    )
    assert resp.status_code == 400


# --- agrégation multi-provider ------------------------------------------


@respx.mock
def test_aggregate_multi_provider(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_providers(
        tmp_path,
        [
            {"id": "ollama", "kind": "ollama", "base_url": OLLAMA_BASE, "enabled": True},
            {"id": "lmstudio", "kind": "openai_compat", "base_url": OPENAI_BASE,
             "enabled": True},
        ],
    )
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    by_provider = {}
    for m in data:
        by_provider.setdefault(m["provider"], []).append(m["normalized_name"])
    assert by_provider["ollama"] == ["llama3.2:latest"]
    assert sorted(by_provider["lmstudio"]) == ["phi-3", "qwen2.5-coder"]


# --- provider injoignable isolé -----------------------------------------


@respx.mock
def test_unreachable_provider_isolated(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_providers(
        tmp_path,
        [
            {"id": "ollama", "kind": "ollama", "base_url": OLLAMA_BASE, "enabled": True},
            {"id": "lmstudio", "kind": "openai_compat", "base_url": OPENAI_BASE,
             "enabled": True},
        ],
    )
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        side_effect=httpx.ConnectError("refused")
    )
    resp = client.get("/api/models")
    data = resp.json()
    # L'openai injoignable contribue [] ; l'ollama reste présent.
    assert {m["provider"] for m in data} == {"ollama"}


# --- drift registry ↔ réalité -------------------------------------------


@respx.mock
def test_drift_enabled_unreachable_and_disabled_reachable(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_providers(
        tmp_path,
        [
            # déclaré actif mais injoignable → drift
            {"id": "ollama", "kind": "ollama", "base_url": OLLAMA_BASE, "enabled": True},
            # déclaré désactivé mais répond → drift (présent inattendu)
            {"id": "lmstudio", "kind": "openai_compat", "base_url": OPENAI_BASE,
             "enabled": False},
        ],
    )
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        side_effect=httpx.ConnectError("down")
    )
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    resp = client.get("/api/registry/drift")
    assert resp.status_code == 200
    drift = {d["provider_id"]: d for d in resp.json()}
    assert drift["ollama"]["drift"] is True
    assert "injoignable" in drift["ollama"]["detail"]
    assert drift["lmstudio"]["drift"] is True
    assert "répond" in drift["lmstudio"]["detail"]


@respx.mock
def test_no_drift_when_enabled_and_reachable(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    resp = client.get("/api/registry/drift")
    drift = resp.json()
    assert len(drift) == 1
    assert drift[0]["provider_id"] == "ollama"
    assert drift[0]["drift"] is False


# --- suppression d'un provider ------------------------------------------


def test_remove_provider(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_providers(
        tmp_path,
        [
            {"id": "ollama", "kind": "ollama", "base_url": OLLAMA_BASE, "enabled": True},
            {"id": "lmstudio", "kind": "openai_compat", "base_url": OPENAI_BASE,
             "enabled": True},
        ],
    )
    resp = client.delete("/api/providers/lmstudio")
    assert resp.status_code == 200
    assert resp.json() == {"removed": "lmstudio"}
    stored = json.loads((tmp_path / "providers.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in stored["providers"]] == ["ollama"]


def test_remove_unknown_provider_404(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _write_providers(
        tmp_path,
        [{"id": "ollama", "kind": "ollama", "base_url": OLLAMA_BASE, "enabled": True}],
    )
    resp = client.delete("/api/providers/ghost")
    assert resp.status_code == 404


# --- providers.json corrompu --------------------------------------------


def test_corrupt_providers_file_clear_error(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    path = tmp_path / "providers.json"
    path.write_text("{ pas du JSON", encoding="utf-8")
    resp = client.get("/api/providers")
    assert resp.status_code == 400
    assert "providers.json" in resp.json()["detail"]
    # Non écrasé.
    assert path.read_text(encoding="utf-8").startswith("{ pas")
