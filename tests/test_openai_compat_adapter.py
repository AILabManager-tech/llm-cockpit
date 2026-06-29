"""Tests V3 : adapter OpenAI-compatible (parsing réel, transport mocké)."""

import asyncio

import httpx
import respx

from app.providers.openai_compat import OpenAICompatAdapter
from app.schemas import GenerateRequest

OPENAI_BASE = "http://127.0.0.1:1234"

MODELS_REAL = {
    "object": "list",
    "data": [
        {"id": "qwen2.5-coder", "object": "model"},
        {"id": "phi-3", "object": "model"},
    ],
}
CHAT_REAL = {
    "id": "chatcmpl-1",
    "model": "qwen2.5-coder",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 5, "completion_tokens": 2},
}


def _adapter() -> OpenAICompatAdapter:
    return OpenAICompatAdapter(base_url=OPENAI_BASE, provider_id="lmstudio")


@respx.mock
def test_list_installed_parses_v1_models():
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        return_value=httpx.Response(200, json=MODELS_REAL)
    )
    models = asyncio.run(_adapter().list_installed())
    assert [m.normalized_name for m in models] == ["qwen2.5-coder", "phi-3"]
    assert all(m.provider == "lmstudio" for m in models)
    assert all(m.source == "openai" for m in models)
    assert models[0].name == "qwen2.5-coder"  # pas de :latest hors Ollama
    assert models[0].installed is True
    assert models[0].loaded is False


def test_list_loaded_always_empty():
    # Pas d'équivalent /v1 : jamais de faux positif, aucun appel réseau.
    assert asyncio.run(_adapter().list_loaded()) == []


@respx.mock
def test_healthcheck_reachable():
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        return_value=httpx.Response(200, json=MODELS_REAL)
    )
    health = asyncio.run(_adapter().healthcheck())
    assert health.reachable is True
    assert health.provider == "lmstudio"


@respx.mock
def test_healthcheck_unreachable():
    respx.get(f"{OPENAI_BASE}/v1/models").mock(
        side_effect=httpx.ConnectError("refused")
    )
    health = asyncio.run(_adapter().healthcheck())
    assert health.reachable is False
    assert health.error


def test_load_unload_unsupported():
    load = asyncio.run(_adapter().load("phi-3"))
    unload = asyncio.run(_adapter().unload("phi-3"))
    assert load.status == "unsupported"
    assert unload.status == "unsupported"
    assert load.provider == "lmstudio"


@respx.mock
def test_generate_parses_chat_completion():
    respx.post(f"{OPENAI_BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CHAT_REAL)
    )
    res = asyncio.run(
        _adapter().generate(GenerateRequest(model="qwen2.5-coder", prompt="ping"))
    )
    assert res.response == "OK"
    assert res.done is True
    assert res.eval_count == 2
    assert res.error is None


@respx.mock
def test_generate_unreachable_controlled_error():
    respx.post(f"{OPENAI_BASE}/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("refused")
    )
    res = asyncio.run(
        _adapter().generate(GenerateRequest(model="phi-3", prompt="ping"))
    )
    assert res.done is False
    assert res.error  # message contrôlé, pas de stacktrace


def test_capabilities_flags():
    caps = _adapter().capabilities()
    assert caps.list_installed is True
    assert caps.list_loaded is False
    assert caps.load is False
    assert caps.unload is False
    assert caps.generate is True
