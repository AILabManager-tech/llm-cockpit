"""Tests V7 : cosinus, retrieval top-K, génération RAG avec sources."""

import asyncio

import httpx
import respx

from app import config
from app.rag import query as rag_query
from app.rag import store as rag_store

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
    "message": {"role": "assistant", "content": "Selon [doc#0], la réponse est X."},
    "done": True,
}


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    monkeypatch.setattr(config, "RAG_EMBED_MODEL", "nomic-embed-text")
    monkeypatch.setattr(
        config, "PROVIDERS_CONFIG_PATH", str(tmp_path / "providers.json")
    )
    monkeypatch.setattr(config, "ROLES_CONFIG_PATH", str(tmp_path / "roles.json"))


def _seed_chunks():
    doc_id = rag_store.insert_document(
        ts="2026-06-28T10:00:00+00:00", path="/x/doc.md", name="doc.md",
        chunks=2, embed_model="nomic-embed-text", dim=3,
    )
    # Chunk 0 aligné avec [1,0,0] ; chunk 1 avec [0,1,0].
    rag_store.insert_chunk(doc_id, 0, "le chat dort", [1.0, 0.0, 0.0])
    rag_store.insert_chunk(doc_id, 1, "le chien court", [0.0, 1.0, 0.0])


def test_cosine():
    assert rag_query._cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert rag_query._cosine([1, 0, 0], [0, 1, 0]) == 0.0
    assert rag_query._cosine([], [1]) == 0.0


@respx.mock
def test_retrieve_top_k_orders_by_similarity(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _seed_chunks()
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS)
    )
    # Requête alignée avec le chunk 0.
    respx.post(f"{OLLAMA_BASE}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [1.0, 0.0, 0.0]})
    )
    sources = asyncio.run(rag_query.retrieve("où est le chat ?", top_k=2))
    assert len(sources) == 2
    assert sources[0].ordinal == 0           # chunk le plus proche d'abord
    assert sources[0].score > sources[1].score
    assert sources[0].doc_name == "doc.md"


@respx.mock
def test_answer_with_sources(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    _seed_chunks()
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS)
    )
    respx.get(f"{OLLAMA_BASE}/api/ps").mock(
        return_value=httpx.Response(200, json=PS_EMPTY)
    )
    respx.post(f"{OLLAMA_BASE}/api/embeddings").mock(
        return_value=httpx.Response(200, json={"embedding": [1.0, 0.0, 0.0]})
    )
    chat = respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, json=CHAT_OK)
    )
    # role = modèle réel (résolu directement par le routage).
    ans = asyncio.run(rag_query.answer("où est le chat ?", role="llama3.2:latest"))
    assert ans.used_rag is True
    assert ans.error is None
    assert ans.model == "llama3.2:latest"
    assert ans.answer.startswith("Selon [doc#0]")
    assert len(ans.sources) == 2
    assert chat.called


def test_answer_empty_store_is_honest(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    # Aucun chunk → réponse honnête, aucun appel modèle.
    ans = asyncio.run(rag_query.answer("question", role="llama3.2:latest"))
    assert ans.used_rag is True
    assert ans.sources == []
    assert "Aucune source" in ans.answer
