"""Tests V2 : rôles locaux (assignation, persistance, test de rôle).

Les mocks interceptent le transport HTTP (/api/tags, /api/ps, /api/generate).
On teste la vraie validation (modèle installé), la persistance JSON réelle, et
la réutilisation du chemin `test` V1 — pas de mock d'interface.
"""

import asyncio
import json

import httpx
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.providers.ollama import OllamaAdapter
from app.services import action_log, roles
from app.services.actions import ActionService
from app.services.inventory import InventoryService
from app.services.roles import RoleService

client = TestClient(app)
BASE = "http://127.0.0.1:11434"

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
    monkeypatch.setattr(config, "ACTION_LOG_PATH", str(tmp_path / "actions.jsonl"))


def _mock_inventory():
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json=TAGS_LLAMA))
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_EMPTY))


# --- état initial : 7 rôles figés, aucun assigné ------------------------


def test_roles_initial_state_all_unassigned(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    resp = client.get("/api/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["role"] for r in data] == list(config.ROLES)
    assert all(r["model"] is None for r in data)


# --- assignation d'un modèle installé → persisté + relu -----------------


@respx.mock
def test_assign_installed_model_persists(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    resp = client.put("/api/roles/chat", json={"model": "llama3.2:latest"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "chat"
    assert body["model"] == "llama3.2:latest"
    assert body["updated_at"]

    # Persisté sur disque (JSON local, pas de base).
    path = tmp_path / "roles.json"
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["assignments"]["chat"]["model"] == "llama3.2:latest"

    # Relu par l'API.
    again = client.get("/api/roles")
    chat = next(r for r in again.json() if r["role"] == "chat")
    assert chat["model"] == "llama3.2:latest"


# --- assignation d'un nom sans tag → normalisé en :latest ---------------


@respx.mock
def test_assign_normalizes_name(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    # /api/tags renvoie le nom taggé ; on envoie "llama3.2" sans tag.
    _mock_inventory()
    resp = client.put("/api/roles/code", json={"model": "llama3.2"})
    assert resp.status_code == 200
    assert resp.json()["model"] == "llama3.2:latest"


# --- assignation d'un modèle non installé → refus 400 -------------------


@respx.mock
def test_assign_not_installed_refused(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    resp = client.put("/api/roles/chat", json={"model": "ghost:latest"})
    assert resp.status_code == 400
    assert "not installed" in resp.json()["detail"]
    # Rien n'a été persisté.
    assert not (tmp_path / "roles.json").exists()


# --- rôle inconnu → 400 -------------------------------------------------


@respx.mock
def test_assign_unknown_role_400(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    resp = client.put("/api/roles/wizard", json={"model": "llama3.2:latest"})
    assert resp.status_code == 400
    assert "unknown role" in resp.json()["detail"]


# --- test d'un rôle → réutilise le chemin test V1 + journal -------------


@respx.mock
def test_role_test_reuses_v1_test(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    respx.post(f"{BASE}/api/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "llama3.2:latest",
                "response": "OK",
                "done": True,
                "total_duration": 4_000_000,
                "eval_count": 2,
            },
        )
    )
    # Assigner d'abord.
    assert client.put("/api/roles/chat", json={"model": "llama3.2:latest"}).status_code == 200
    # Tester le rôle.
    resp = client.post("/api/roles/chat/test", json={"prompt": "Réponds OK."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "test"
    assert body["status"] == "ok"
    assert body["detail"] == "OK"
    assert body["duration_ms"] == 4.0  # ns→ms via le chemin V1
    # Le test de rôle est journalisé via le journal d'actions V1.
    assert action_log.read_entries(limit=1)[0].action == "test"


# --- test d'un rôle non assigné → 400 -----------------------------------


def test_role_test_unassigned_400(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    resp = client.post("/api/roles/embedding/test")
    assert resp.status_code == 400
    assert "not assigned" in resp.json()["detail"]


# --- roles.json corrompu → erreur claire, pas d'écrasement --------------


def test_corrupt_roles_file_clear_error(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    path = tmp_path / "roles.json"
    path.write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    resp = client.get("/api/roles")
    assert resp.status_code == 400
    assert "roles.json" in resp.json()["detail"]
    # Le fichier corrompu n'a pas été écrasé.
    assert path.read_text(encoding="utf-8").startswith("{ ceci")


# --- persistance rechargée par une nouvelle instance de service ---------


@respx.mock
def test_assignment_reloaded_by_fresh_service(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_inventory()
    adapter = OllamaAdapter(BASE)
    inventory = InventoryService(adapter)
    svc = RoleService(inventory, ActionService(adapter, inventory))
    asyncio.run(svc.set_role("quality", "llama3.2:latest"))

    # Nouvelle instance, même fichier → assignation relue.
    svc2 = RoleService(inventory, ActionService(adapter, inventory))
    roles_list = asyncio.run(svc2.list_roles())
    quality = next(r for r in roles_list if r.role == "quality")
    assert quality.model == "llama3.2:latest"


# --- garde-fou : aucune assignation inventée si jamais écrite -----------


def test_read_assignments_empty_when_absent(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    assert roles._read_assignments() == {}
