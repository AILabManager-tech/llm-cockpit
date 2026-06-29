"""Embeddings via Ollama (`POST /api/embeddings`), passant par l'adapter.

Le modèle d'embedding doit être réellement installé : sinon erreur claire,
jamais de fallback inventé. L'appel HTTP reste dans l'adapter Ollama.
"""

import httpx

from app import config
from app.providers.ollama import OllamaAdapter
from app.services.inventory import normalize_name


class EmbeddingModelMissing(Exception):
    """RAG_EMBED_MODEL absent de l'inventaire installé."""


class EmbeddingError(Exception):
    """Échec d'appel au backend d'embeddings."""


def _adapter() -> OllamaAdapter:
    return OllamaAdapter(base_url=config.OLLAMA_BASE_URL)


async def ensure_model_installed() -> str:
    """Vérifie que RAG_EMBED_MODEL est installé ; renvoie son nom normalisé."""
    model = normalize_name({"model": config.RAG_EMBED_MODEL})
    installed = {m.normalized_name for m in await _adapter().list_installed()}
    if model not in installed:
        raise EmbeddingModelMissing(
            f"modèle d'embedding non installé : {config.RAG_EMBED_MODEL}"
        )
    return model


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeddings de plusieurs textes. Lève si le modèle manque ou échoue."""
    model = await ensure_model_installed()
    adapter = _adapter()
    vectors: list[list[float]] = []
    try:
        for text in texts:
            vectors.append(await adapter.embed(model, text))
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"backend d'embeddings injoignable : {exc}") from exc
    return vectors
