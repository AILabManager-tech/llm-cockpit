"""The version shown in the UI must be the version that ships.

The header used to read "V8" — the last roadmap milestone — while the package
was 0.1.0. A badge that contradicts the package is a small lie displayed
permanently, and nothing caught it.
"""

import tomllib
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)
BASE = "http://127.0.0.1:11434"


def test_module_version_matches_the_package():
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert __version__ == pyproject["project"]["version"]


@respx.mock
def test_the_header_shows_the_real_version():
    respx.get(f"{BASE}/api/tags").mock(side_effect=httpx.ConnectError("down"))
    respx.get(f"{BASE}/api/ps").mock(side_effect=httpx.ConnectError("down"))
    body = client.get("/").text
    assert f"v{__version__}" in body
    assert ">V8<" not in body
