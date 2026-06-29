import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "http://127.0.0.1:11434"


@respx.mock
def test_health_reachable_returns_200_true():
    respx.get(f"{BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "ollama"
    assert body["base_url"] == BASE
    assert body["reachable"] is True
    assert body["error"] is None


@respx.mock
def test_health_unreachable_returns_200_false():
    respx.get(f"{BASE}/api/tags").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    resp = client.get("/api/health")
    # Convention V0 : /api/health renvoie TOUJOURS 200, jamais 503.
    assert resp.status_code == 200
    body = resp.json()
    assert body["reachable"] is False
    assert body["error"]
