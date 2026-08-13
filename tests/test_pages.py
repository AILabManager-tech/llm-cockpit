"""The four sections: each one owns its panels, and only its panels.

The point of the split is that a tab does not poll what it does not show, so
these tests check the boundaries, not just that pages answer 200.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "http://127.0.0.1:11434"

TABS = ["/", "/routing", "/traffic", "/lab"]


@pytest.fixture(autouse=True)
def _ollama_unreachable():
    """Pages must render without Ollama; content, not inventory, is under test."""
    with respx.mock:
        respx.get(f"{BASE}/api/tags").mock(side_effect=httpx.ConnectError("down"))
        respx.get(f"{BASE}/api/ps").mock(side_effect=httpx.ConnectError("down"))
        yield


@pytest.mark.parametrize("path", TABS)
def test_every_tab_renders(path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", TABS)
def test_every_tab_marks_itself_as_current(path):
    body = client.get(path).text
    assert body.count('aria-current="page"') == 1
    assert body.count("is-active") == 1


@pytest.mark.parametrize("path", TABS)
def test_every_tab_offers_the_whole_navigation(path):
    body = client.get(path).text
    for label in ("Models", "Routing", "Traffic", "Lab"):
        assert f">{label}</a>" in body


PANELS = {
    "/": ["models-panel", "actions-panel"],
    "/routing": ["roles-panel", "gateway-panel", "providers-panel"],
    "/traffic": ["dashboard-panel"],
    "/lab": ["scoreboard-panel", "rag-panel", "training-panel"],
}


@pytest.mark.parametrize("path,expected", PANELS.items())
def test_each_tab_carries_exactly_its_own_panels(path, expected):
    body = client.get(path).text
    for panel in expected:
        assert f'id="{panel}"' in body
    foreign = {p for panels in PANELS.values() for p in panels} - set(expected)
    for panel in foreign:
        assert f'id="{panel}"' not in body, f"{panel} leaked into {path}"


def test_a_tab_polls_only_what_it_displays():
    # The whole point of splitting: no background refresh for hidden panels.
    body = client.get("/traffic").text
    assert body.count("hx-trigger=") == 1


def test_the_old_dashboard_url_still_works():
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "/traffic"
