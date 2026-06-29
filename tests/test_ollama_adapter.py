"""Tests #3 et #4 : parsing réel des shapes /api/tags et /api/ps.

Les mocks interceptent le transport HTTP brut ; on teste le parsing réel
dans OllamaAdapter (via les endpoints qui l'exercent), pas un mock d'interface.
"""

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "http://127.0.0.1:11434"

# Shape RÉEL de GET /api/tags (cf. Référence API du mandat).
TAGS_REAL = {
    "models": [
        {
            "name": "llama3.2:latest",
            "model": "llama3.2:latest",
            "modified_at": "2025-05-04T17:37:44.706015396-07:00",
            "size": 2019393189,
            "digest": "a80c4f17acd5dc6b8e9ad5e4c2f1b0a9",
            "details": {
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "3.2B",
                "quantization_level": "Q4_K_M",
            },
        }
    ]
}

# Shape RÉEL de GET /api/ps (cf. Référence API du mandat).
PS_REAL = {
    "models": [
        {
            "name": "mistral:latest",
            "model": "mistral:latest",
            "size": 5137025024,
            "digest": "2ae6f6dd7a3dffa8b91b1f1e2c3d4e5f",
            "details": {
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7.2B",
                "quantization_level": "Q4_0",
            },
            "expires_at": "2024-06-04T14:38:31.83753-07:00",
            "size_vram": 5137025024,
        }
    ]
}


@respx.mock
def test_installed_parses_real_tags_shape():
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_REAL)
    )
    resp = client.get("/api/models/installed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    m = data[0]
    assert m["name"] == "llama3.2:latest"
    assert m["normalized_name"] == "llama3.2:latest"
    assert m["source"] == "tags"
    assert m["loaded"] is False
    assert m["installed"] is True
    assert m["size"] == 2019393189
    assert m["digest"].startswith("a80c4f17")
    assert m["family"] == "llama"
    assert m["quantization"] == "Q4_K_M"
    assert m["modified_at"].startswith("2025-05-04")
    assert m["size_vram"] is None
    assert m["expires_at"] is None
    # détails bruts conservés
    assert m["raw"]["details"]["parameter_size"] == "3.2B"


@respx.mock
def test_loaded_parses_real_ps_shape():
    respx.get(f"{BASE}/api/ps").mock(return_value=httpx.Response(200, json=PS_REAL))
    resp = client.get("/api/models/loaded")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    m = data[0]
    assert m["name"] == "mistral:latest"
    assert m["normalized_name"] == "mistral:latest"
    assert m["source"] == "ps"
    assert m["loaded"] is True
    assert m["size_vram"] == 5137025024
    assert m["expires_at"].startswith("2024-06-04")
    assert m["family"] == "llama"
    assert m["quantization"] == "Q4_0"
    assert m["raw"]["size_vram"] == 5137025024
