"""Retrieval + génération augmentée (RAG). Réponses citant leurs sources.

Similarité = cosinus calculé en Python sur les embeddings stockés (store
vectoriel local). La génération passe par le routage réel V4 (rôles + adapter),
comme le gateway. Aucun chunk pertinent → réponse honnête « pas de source »,
jamais d'hallucination forcée.
"""

import math

from app import config
from app.rag import embed
from app.rag import store as rag_store
from app.schemas import ChatMessage, ChatRequest, RagAnswer, RagSource
from app.services.registry import RegistryService
from app.services.routing import RoutingService

RAG_SYSTEM = (
    "Answer only from the provided CONTEXT. Cite sources as [doc#n]. If the "
    "context does not contain the answer, say so plainly instead of inventing "
    "one. Answer in the language of the question."
)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def _retrieve_scored(query: str, top_k: int) -> list[tuple[float, dict]]:
    chunks = rag_store.all_chunks()
    if not chunks:
        return []
    qvec = (await embed.embed_texts([query]))[0]
    scored = [(_cosine(qvec, c["embedding"]), c) for c in chunks]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def _to_source(score: float, chunk: dict) -> RagSource:
    return RagSource(
        doc_id=chunk["doc_id"],
        doc_name=chunk["doc_name"],
        ordinal=chunk["ordinal"],
        score=score,
        preview=chunk["text"][: config.RAG_SOURCE_PREVIEW_MAX],
    )


def build_context(scored: list[tuple[float, dict]]) -> str:
    return "\n\n".join(
        f"[{c['doc_name']}#{c['ordinal']}] {c['text']}" for _score, c in scored
    )


def build_rag_prompt(query: str, context: str) -> str:
    if not context:
        return (
            "CONTEXT: (no local source available)\n\n"
            f"QUESTION: {query}\n\n"
            "If no local source covers the question, say so honestly."
        )
    return (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {query}\n\n"
        "Answer using the CONTEXT and cite the sources [doc#n]."
    )


async def retrieve(query: str, top_k: int | None = None) -> list[RagSource]:
    scored = await _retrieve_scored(query, top_k or config.RAG_TOP_K)
    return [_to_source(score, c) for score, c in scored]


async def answer(query: str, role: str | None = None) -> RagAnswer:
    scored = await _retrieve_scored(query, config.RAG_TOP_K)
    if not scored:
        return RagAnswer(
            query=query,
            answer="No relevant source found in the local documents.",
            used_rag=True,
            sources=[],
        )

    sources = [_to_source(score, c) for score, c in scored]
    augmented = build_rag_prompt(query, build_context(scored))

    registry = RegistryService()
    routing = RoutingService(registry)
    decision = await routing.resolve(role or config.GATEWAY_DEFAULT_ROLE)
    if not decision.ok:
        return RagAnswer(
            query=query, answer="", used_rag=True, sources=sources,
            error=decision.reason,
        )
    adapter = registry.adapter_for(decision.provider)
    if adapter is None:
        return RagAnswer(
            query=query, answer="", used_rag=True, sources=sources,
            error=f"provider indisponible : {decision.provider}",
        )

    result = await adapter.chat(
        ChatRequest(
            model=decision.model,
            messages=[
                ChatMessage(role="system", content=RAG_SYSTEM),
                ChatMessage(role="user", content=augmented),
            ],
        )
    )
    if result.error:
        return RagAnswer(
            query=query, answer="", used_rag=True, sources=sources,
            model=decision.model, error=result.error,
        )
    return RagAnswer(
        query=query, answer=result.message.content, used_rag=True,
        model=decision.model, sources=sources,
    )
