import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ModelInfo
from app.services.inventory import merge_models, normalize_name

client = TestClient(app)
BASE = "http://127.0.0.1:11434"

LLAMA_TAG = {
    "name": "llama3.2:latest",
    "model": "llama3.2:latest",
    "modified_at": "2025-05-04T17:37:44.706015396-07:00",
    "size": 2019393189,
    "digest": "a80c4f17acd5",
    "details": {"family": "llama", "quantization_level": "Q4_K_M"},
}
MISTRAL_TAG = {
    "name": "mistral:latest",
    "model": "mistral:latest",
    "modified_at": "2025-04-01T10:00:00.000000000-07:00",
    "size": 5137025024,
    "digest": "2ae6f6dd7a3d",
    "details": {"family": "llama", "quantization_level": "Q4_0"},
}
MISTRAL_PS = {
    "name": "mistral:latest",
    "model": "mistral:latest",
    "size": 5137025024,
    "digest": "2ae6f6dd7a3d",
    "details": {"family": "llama", "quantization_level": "Q4_0"},
    "expires_at": "2024-06-04T14:38:31.83753-07:00",
    "size_vram": 5137025024,
}


# --- Tests #5, #6, #7 : fusion via l'endpoint /api/models -----------------


@respx.mock
def test_models_merge_installed_and_loaded():
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [MISTRAL_TAG, LLAMA_TAG]})
    )
    respx.get(f"{BASE}/api/ps").mock(
        return_value=httpx.Response(200, json={"models": [MISTRAL_PS]})
    )
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2  # fusion : pas de doublon mistral
    by_name = {m["normalized_name"]: m for m in data}

    # #7 : installé ET chargé → loaded true, size_vram + expires_at repris de ps
    mistral = by_name["mistral:latest"]
    assert mistral["loaded"] is True
    assert mistral["source"] == "tags"  # garde la source tags après fusion
    assert mistral["size_vram"] == 5137025024
    assert mistral["expires_at"].startswith("2024-06-04")

    # #6 : installé non chargé → loaded false
    llama = by_name["llama3.2:latest"]
    assert llama["loaded"] is False
    assert llama["size_vram"] is None


# --- Test #8 (fixture synthétique) : tag implicite → :latest --------------


def test_normalize_name_implicit_latest():
    assert normalize_name({"name": "customnotag"}) == "customnotag:latest"
    assert normalize_name({"model": "foo:7b"}) == "foo:7b"
    assert normalize_name({}) == ""


@respx.mock
def test_installed_implicit_latest_tag():
    # Input fabriqué exprès : nom SANS tag (le vrai Ollama renvoie toujours
    # un nom taggé, donc ce chemin ne se déclenche qu'avec ce fixture.)
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(
            200, json={"models": [{"name": "customnotag", "size": 1}]}
        )
    )
    resp = client.get("/api/models/installed")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["normalized_name"] == "customnotag:latest"


# --- Test #9 (fixture synthétique) : ps_only -----------------------------


@respx.mock
def test_models_ps_only_exposed():
    # Fixture construit exprès : modèle chargé MAIS absent de /api/tags.
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    respx.get(f"{BASE}/api/ps").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"name": "ghost:latest", "size": 10, "size_vram": 10}
                ]
            },
        )
    )
    resp = client.get("/api/models")
    data = resp.json()
    assert len(data) == 1
    ghost = data[0]
    assert ghost["normalized_name"] == "ghost:latest"
    assert ghost["loaded"] is True
    assert ghost["installed"] is True
    assert ghost["source"] == "ps_only"


# --- Fusion unitaire : digest divergent non bloquant ---------------------


def test_merge_digest_mismatch_keeps_tags_entry(caplog):
    installed = [
        ModelInfo(
            name="x:latest",
            normalized_name="x:latest",
            source="tags",
            digest="AAAA",
        )
    ]
    loaded = [
        ModelInfo(
            name="x:latest",
            normalized_name="x:latest",
            source="ps",
            loaded=True,
            digest="BBBB",
            size_vram=42,
        )
    ]
    with caplog.at_level("WARNING"):
        merged = merge_models(installed, loaded)
    assert len(merged) == 1
    m = merged[0]
    assert m.loaded is True
    assert m.source == "tags"  # entrée tags conservée, non masquée
    assert m.size_vram == 42
    assert m.digest == "AAAA"  # digest tags conservé
    assert any("incohérent" in r.message.lower() for r in caplog.records)


# --- Ollama injoignable : /api/models renvoie [] (pas d'enveloppe) -------


@respx.mock
def test_models_empty_list_when_unreachable():
    respx.get(f"{BASE}/api/tags").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{BASE}/api/ps").mock(side_effect=httpx.ConnectError("down"))
    resp = client.get("/api/models")
    assert resp.status_code == 200
    assert resp.json() == []  # liste vide stricte, schéma inchangé


# --- Fragment HTMX : distingue injoignable vs aucun modèle ----------------


@respx.mock
def test_partials_distinguishes_unreachable_from_empty():
    respx.get(f"{BASE}/api/tags").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{BASE}/api/ps").mock(side_effect=httpx.ConnectError("down"))
    resp = client.get("/partials/models")
    assert resp.status_code == 200
    assert "unreachable" in resp.text


@respx.mock
def test_partials_empty_inventory_message():
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    respx.get(f"{BASE}/api/ps").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    resp = client.get("/partials/models")
    assert resp.status_code == 200
    assert "no model is installed" in resp.text.lower()
