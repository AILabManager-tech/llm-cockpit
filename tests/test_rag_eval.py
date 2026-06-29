"""Tests V7 : comparaison RAG vs non-RAG via le harness V6."""

import asyncio

import httpx
import respx

from app import config
from app.db import store
from app.evals.runner import EvalRunner
from app.rag import eval_bridge
from app.rag import store as rag_store
from app.services.registry import RegistryService
from app.services.routing import RoutingService

OLLAMA_BASE = "http://127.0.0.1:11434"
TAGS = {
    "models": [
        {"name": "nomic-embed-text:latest", "model": "nomic-embed-text:latest",
         "size": 1, "digest": "e1", "details": {}},
        {"name": "llama3.2:latest", "model": "llama3.2:latest", "size": 1,
         "digest": "d1", "details": {"family": "llama"}},
    ]
}
PS_EMPTY = {"models": []}
CHAT_OK = {
    "model": "llama3.2:latest",
    "message": {"role": "assistant", "content": "OK"},
    "done": True,
    "total_duration": 4_000_000,
    "eval_count": 1,
    "prompt_eval_count": 4,
}
SUITE_YAML = """
name: rag_suite
role: chat
cases:
  - name: q1
    prompt: "Quelle est la couleur ?"
    checks:
      - non_empty
"""


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    monkeypatch.setattr(config, "EVALS_DIR", str(tmp_path / "evals"))
    monkeypatch.setattr(config, "RAG_EMBED_MODEL", "nomic-embed-text")
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))
    (tmp_path / "evals").mkdir()
    (tmp_path / "evals" / "rag_suite.yaml").write_text(SUITE_YAML, encoding="utf-8")


def _runner() -> EvalRunner:
    registry = RegistryService()
    return EvalRunner(registry, RoutingService(registry))


def _mock_common():
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )


@respx.mock
def test_eval_without_rag_delegates_to_runner(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_common()
    summary = asyncio.run(
        eval_bridge.run_eval(_runner(), "rag_suite", False, ["llama3.2:latest"])
    )
    assert summary.suite == "rag_suite"          # pas de suffixe +rag
    assert summary.role == "chat"
    assert summary.results[0].status == "ok"


@respx.mock
def test_eval_with_rag_augments_and_tags_role(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _mock_common()
    respx.post(f"{OLLAMA_BASE}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [1.0, 0.0, 0.0]})
    )
    # Un chunk en base pour que le contexte RAG soit réellement injecté.
    doc_id = rag_store.insert_document(
        ts="2026-06-28T10:00:00+00:00", path="/x/d.md", name="d.md",
        chunks=1, embed_model="nomic-embed-text", dim=3,
    )
    rag_store.insert_chunk(doc_id, 0, "la couleur est bleue", [1.0, 0.0, 0.0])

    summary = asyncio.run(
        eval_bridge.run_eval(_runner(), "rag_suite", True, ["llama3.2:latest"])
    )
    assert summary.suite == "rag_suite+rag"
    assert summary.role == "chat+rag"            # distinct dans le scoreboard
    assert summary.results[0].status == "ok"

    # Run RAG persisté distinctement.
    runs = store.query_eval_runs()
    assert runs[0]["suite"] == "rag_suite+rag"
    assert runs[0]["role"] == "chat+rag"
