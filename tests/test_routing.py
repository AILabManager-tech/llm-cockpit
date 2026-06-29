"""Tests V4 : résolution de routage rôle/modèle → (provider, modèle)."""

import asyncio
import json

import httpx
import respx

from app import config
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


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )


def _assign(tmp_path, role, model, provider="ollama"):
    (tmp_path / "roles.json").write_text(
        json.dumps(
            {"assignments": {role: {"model": model, "provider": provider}}}
        ),
        encoding="utf-8",
    )


def _service() -> RoutingService:
    return RoutingService(RegistryService())


def _mock_ollama_ok():
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_LLAMA)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )


@respx.mock
def test_resolve_assigned_role(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("chat"))
    assert d.ok is True
    assert d.resolved_role == "chat"
    assert d.provider == "ollama"
    assert d.model == "llama3.2:latest"


@respx.mock
def test_resolve_role_prefix_syntax(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("role:chat"))
    assert d.ok is True
    assert d.model == "llama3.2:latest"


@respx.mock
def test_resolve_unassigned_role(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("embedding"))
    assert d.ok is False
    assert d.resolved_role == "embedding"
    assert "non assigné" in d.reason


@respx.mock
def test_resolve_unknown_role(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("role:wizard"))
    assert d.ok is False
    assert "rôle inconnu" in d.reason


@respx.mock
def test_resolve_real_model_present(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("llama3.2:latest"))
    assert d.ok is True
    assert d.resolved_role is None
    assert d.provider == "ollama"
    assert d.model == "llama3.2:latest"


@respx.mock
def test_resolve_real_model_absent(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_ollama_ok()
    d = asyncio.run(_service().resolve("ghost:latest"))
    assert d.ok is False
    assert "introuvable" in d.reason


@respx.mock
def test_resolve_role_model_unavailable_when_provider_down(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    # Provider injoignable → agrégat vide → le modèle du rôle n'est pas présent.
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        side_effect=httpx.ConnectError("down")
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        side_effect=httpx.ConnectError("down")
    )
    d = asyncio.run(_service().resolve("chat"))
    assert d.ok is False
    assert "indisponible" in d.reason


@respx.mock
def test_routing_table_lists_all_roles(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _assign(tmp_path, "chat", "llama3.2:latest")
    _mock_ollama_ok()
    table = asyncio.run(_service().routing_table())
    assert [r.requested for r in table] == list(config.ROLES)
    chat = next(r for r in table if r.requested == "chat")
    assert chat.ok is True
