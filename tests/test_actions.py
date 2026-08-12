"""Tests V1 : validation, exécution, journalisation des actions.

Les mocks interceptent le transport HTTP (/api/tags, /api/ps, /api/generate).
On teste la vraie logique de validation/journal et la conversion ns→ms réelle,
jamais des méthodes d'adapter mockées.
"""

import asyncio

import httpx
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.providers.ollama import OllamaAdapter
from app.services import action_log
from app.services.actions import ActionService
from app.services.inventory import InventoryService

client = TestClient(app)
BASE = "http://127.0.0.1:11434"

# Inventaire de référence : llama installé non chargé ; mistral chargé (ps).
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
PS_MISTRAL = {
    "models": [
        {
            "name": "mistral:latest",
            "model": "mistral:latest",
            "size": 2,
            "size_vram": 2,
            "digest": "d2",
            "details": {"family": "llama", "quantization_level": "Q4_0"},
        }
    ]
}
PS_EMPTY = {"models": []}
TAGS_EMPTY = {"models": []}


def _use_tmp_log(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "ACTION_LOG_PATH", str(tmp_path / "actions.jsonl")
    )


# --- #1 load OK ----------------------------------------------------------


@respx.mock
def test_load_installed_ok(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_LLAMA))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))
    gen = respx.post(f"{BASE}/api/generate").mock(
        return_value=httpx.Response(
            200, json={"model": "llama3.2:latest", "done": True,
                       "total_duration": 2_000_000}
        )
    )
    resp = client.post("/api/actions/load", json={"model": "llama3.2:latest"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "load"
    assert body["status"] == "ok"
    assert body["duration_ms"] == 2.0  # 2_000_000 ns → 2 ms
    assert gen.called
    last = action_log.read_entries(limit=1)[0]
    assert last.action == "load"
    assert last.status == "ok"


# --- #2 unload OK --------------------------------------------------------


@respx.mock
def test_unload_loaded_ok(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_EMPTY))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_MISTRAL))
    gen = respx.post(f"{BASE}/api/generate").mock(
        return_value=httpx.Response(
            200, json={"model": "mistral:latest", "done": True,
                       "total_duration": 1_000_000}
        )
    )
    resp = client.post("/api/actions/unload", json={"model": "mistral:latest"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert gen.called
    assert action_log.read_entries(limit=1)[0].action == "unload"


# --- #3 test : parsing + conversion ns→ms --------------------------------


@respx.mock
def test_test_installed_parses_duration(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_LLAMA))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))
    respx.post(f"{BASE}/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "llama3.2:latest",
                "response": "OK",
                "done": True,
                "total_duration": 3_500_000,
                "eval_count": 3,
            },
        )
    )
    resp = client.post(
        "/api/actions/test",
        json={"model": "llama3.2:latest", "prompt": "Réponds OK."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["detail"] == "OK"
    assert body["duration_ms"] == 3.5  # 3_500_000 ns → 3.5 ms


# --- #4 load non installé → refus, AUCUN appel /api/generate -------------


@respx.mock
def test_load_not_installed_refused_no_http(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_EMPTY))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))
    # /api/generate NON enregistré : tout appel ferait échouer respx.
    resp = client.post("/api/actions/load", json={"model": "ghost:latest"})
    assert resp.status_code == 400
    last = action_log.read_entries(limit=1)[0]
    assert last.status == "refused"
    assert "not installed" in (last.detail or "")


# --- #5 unload non chargé → refus ---------------------------------------


@respx.mock
def test_unload_not_loaded_refused(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_LLAMA))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))
    resp = client.post("/api/actions/unload", json={"model": "llama3.2:latest"})
    assert resp.status_code == 400
    last = action_log.read_entries(limit=1)[0]
    assert last.status == "refused"
    assert "not loaded" in (last.detail or "")


# --- #6 action hors allowlist → refus (niveau service, pas d'endpoint) --


def test_action_outside_allowlist_refused(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    adapter = OllamaAdapter(BASE)
    service = ActionService(adapter, InventoryService(adapter))
    # "delete" hors allowlist : refus immédiat, aucun appel réseau.
    result, code = asyncio.run(service.run("delete", "llama3.2:latest"))
    assert code == 400
    assert result.status == "unsupported"
    last = action_log.read_entries(limit=1)[0]
    assert last.status == "refused"
    assert last.action == "delete"


# --- #7 Ollama injoignable pendant test → error, pas de stacktrace ------


@respx.mock
def test_test_provider_unreachable(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_LLAMA))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))
    respx.post(f"{BASE}/api/generate").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = client.post("/api/actions/test", json={"model": "llama3.2:latest"})
    assert resp.status_code == 200  # corps d'erreur contrôlé, pas 5xx
    body = resp.json()
    assert body["status"] == "error"
    assert body["detail"]  # message clair, pas de stacktrace
    assert action_log.read_entries(limit=1)[0].status == "error"


# --- #8 GET /api/actions/log?limit=N ------------------------------------


def test_actions_log_endpoint_limit(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    for i in range(3):
        action_log.append_entry(action="test", model=f"m{i}", status="ok")
    resp = client.get("/api/actions/log?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["model"] == "m2"  # plus récent d'abord


# --- #9 ACTIONS_ENABLED=0 → 403 -----------------------------------------


def test_actions_disabled_returns_403(tmp_path, monkeypatch):
    _use_tmp_log(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "ACTIONS_ENABLED", False)
    resp = client.post("/api/actions/load", json={"model": "llama3.2:latest"})
    assert resp.status_code == 403
    assert action_log.read_entries(limit=1)[0].status == "refused"
