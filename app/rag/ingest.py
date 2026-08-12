"""Ingestion locale de documents (txt / md / pdf) → chunks déterministes.

Étapes explicites et testables, aucun framework RAG opaque. Aucun contenu de
document n'est jamais exécuté. L'ingestion est restreinte à RAG_DOCS_DIR.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.rag import embed
from app.rag import store as rag_store
from app.schemas import RagDocument

logger = logging.getLogger("llm_cockpit.rag.ingest")


class IngestError(Exception):
    """Chemin hors périmètre, fichier absent ou non parsable."""


def _docs_root() -> Path:
    return Path(config.RAG_DOCS_DIR).resolve()


def resolve_in_docs_dir(path: str) -> Path:
    """Résout `path` (relatif à RAG_DOCS_DIR ou absolu) en restant DANS le dossier.

    Bloque toute ingestion hors du dossier autorisé (pas de traversée `..`).
    """
    root = _docs_root()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise IngestError(f"path outside the allowed directory: {path}")
    if not resolved.is_file():
        raise IngestError(f"file not found: {path}")
    return resolved


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dépendance présente
            raise IngestError("pypdf is unavailable to read the PDF") from exc
        try:
            reader = PdfReader(str(path))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # noqa: BLE001 - pdf illisible
            raise IngestError(f"unparsable PDF: {path.name} ({exc})") from exc
    raise IngestError(f"unsupported file type: {suffix}")


def chunk_text(
    text: str,
    size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Découpage déterministe par fenêtre glissante sur les caractères.

    Normalise les espaces, fenêtres de `size` avec recouvrement `overlap`.
    """
    size = size or config.RAG_CHUNK_SIZE
    overlap = config.RAG_CHUNK_OVERLAP if overlap is None else overlap
    if size <= 0:
        raise IngestError("invalid chunk size")
    overlap = max(0, min(overlap, size - 1))

    normalized = " ".join(text.split())
    if not normalized:
        return []

    step = size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        chunks.append(normalized[start : start + size])
        start += step
    return chunks


async def ingest_document(path_str: str) -> RagDocument:
    """parse → chunk → embed → store. Renvoie le RagDocument créé.

    Lève IngestError (chemin/parse) ou EmbeddingModelMissing (modèle absent).
    """
    path = resolve_in_docs_dir(path_str)
    text = read_document(path)
    chunks = chunk_text(text)
    if not chunks:
        raise IngestError(f"empty document after extraction: {path.name}")

    vectors = await embed.embed_texts(chunks)
    dim = len(vectors[0]) if vectors and vectors[0] else None
    ts = datetime.now(timezone.utc).isoformat()

    doc_id = rag_store.insert_document(
        ts=ts, path=str(path), name=path.name, chunks=len(chunks),
        embed_model=config.RAG_EMBED_MODEL, dim=dim,
    )
    for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors)):
        rag_store.insert_chunk(doc_id, ordinal, chunk, vector)

    return RagDocument(
        id=doc_id, ts=ts, path=str(path), name=path.name, chunks=len(chunks),
        embed_model=config.RAG_EMBED_MODEL, dim=dim,
    )
