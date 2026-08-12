"""Tests V7 : chunking déterministe + ingestion (embeddings mockés)."""

import asyncio

import httpx
import pytest
import respx

from app import config
from app.rag import ingest
from app.rag import store as rag_store
from app.rag.embed import EmbeddingModelMissing
from app.rag.ingest import IngestError, chunk_text

OLLAMA_BASE = "http://127.0.0.1:11434"
TAGS_EMBED = {
    "models": [
        {"name": "nomic-embed-text:latest", "model": "nomic-embed-text:latest",
         "size": 1, "digest": "e1", "details": {}}
    ]
}
TAGS_NO_EMBED = {
    "models": [
        {"name": "llama3.2:latest", "model": "llama3.2:latest", "size": 1,
         "digest": "d1", "details": {}}
    ]
}
EMBEDDING = {"embedding": [0.1, 0.2, 0.3, 0.4]}


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cockpit.db"))
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(config, "RAG_DOCS_DIR", str(docs))
    monkeypatch.setattr(config, "RAG_EMBED_MODEL", "nomic-embed-text")
    return docs


def test_chunk_text_deterministic():
    # size 4, overlap 1 → pas de 3 par chunk, fenêtres glissantes.
    chunks = chunk_text("abcdefghij", size=4, overlap=1)
    assert chunks == ["abcd", "defg", "ghij", "j"]


def test_chunk_text_normalizes_whitespace():
    assert chunk_text("a   b\n\nc", size=100, overlap=0) == ["a b c"]


def test_chunk_text_empty():
    assert chunk_text("   ", size=10, overlap=0) == []


def test_resolve_blocks_traversal(tmp_path, monkeypatch):
    docs = _use_tmp(tmp_path, monkeypatch)
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (docs / "ok.txt").write_text("hello", encoding="utf-8")
    # Fichier dans le dossier autorisé → OK.
    assert ingest.resolve_in_docs_dir("ok.txt").name == "ok.txt"
    # Traversée hors du dossier → refus.
    with pytest.raises(IngestError):
        ingest.resolve_in_docs_dir("../secret.txt")


@respx.mock
def test_ingest_document_stores_chunks(tmp_path, monkeypatch):
    docs = _use_tmp(tmp_path, monkeypatch)
    (docs / "note.md").write_text("a" * 10, encoding="utf-8")
    monkeypatch.setattr(config, "RAG_CHUNK_SIZE", 4)
    monkeypatch.setattr(config, "RAG_CHUNK_OVERLAP", 1)
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_EMBED)
    )
    respx.post(f"{OLLAMA_BASE}/api/embeddings").mock(
        return_value=httpx.Response(200, json=EMBEDDING)
    )

    doc = asyncio.run(ingest.ingest_document("note.md"))
    assert doc.name == "note.md"
    assert doc.chunks >= 2
    assert doc.dim == 4
    assert doc.embed_model == "nomic-embed-text"

    docs_in_db = rag_store.list_documents()
    assert len(docs_in_db) == 1
    chunks = rag_store.all_chunks()
    assert len(chunks) == doc.chunks
    assert chunks[0]["embedding"] == [0.1, 0.2, 0.3, 0.4]


def _minimal_pdf(text: str) -> bytes:
    """Smallest valid PDF carrying extractable text, built without a writer.

    Exercises the real pypdf extraction path, which no test covered.
    """
    content = f"BT /F1 24 Tf 40 120 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(out)


@respx.mock
def test_ingest_pdf_extracts_text(tmp_path, monkeypatch):
    docs = _use_tmp(tmp_path, monkeypatch)
    (docs / "note.pdf").write_bytes(_minimal_pdf("Cockpit PDF ingestion works"))
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_EMBED)
    )
    respx.post(f"{OLLAMA_BASE}/api/embeddings").mock(
        return_value=httpx.Response(200, json=EMBEDDING)
    )

    doc = asyncio.run(ingest.ingest_document("note.pdf"))
    assert doc.name == "note.pdf"
    assert doc.chunks >= 1

    chunks = rag_store.all_chunks()
    assert "Cockpit PDF ingestion works" in chunks[0]["text"]


def test_ingest_pdf_without_text_is_refused(tmp_path, monkeypatch):
    docs = _use_tmp(tmp_path, monkeypatch)
    (docs / "blank.pdf").write_bytes(_minimal_pdf(" "))
    with pytest.raises(IngestError, match="empty document"):
        asyncio.run(ingest.ingest_document("blank.pdf"))


@respx.mock
def test_ingest_missing_embed_model(tmp_path, monkeypatch):
    docs = _use_tmp(tmp_path, monkeypatch)
    (docs / "note.txt").write_text("hello world", encoding="utf-8")
    respx.get(f"{OLLAMA_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json=TAGS_NO_EMBED)
    )
    with pytest.raises(EmbeddingModelMissing):
        asyncio.run(ingest.ingest_document("note.txt"))
