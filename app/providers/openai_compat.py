"""Adapter OpenAI-compatible minimal (HTTP brut via httpx, pas le SDK openai).

Cibles : LM Studio, llama.cpp server, tout endpoint OpenAI-compatible.
Endpoints utilisés :
    GET  /v1/models            → inventaire des modèles
    POST /v1/chat/completions  → génération (test)

`list_loaded`, `load`, `unload` ne sont pas exprimables en OpenAI-compatible :
déclarés non supportés via `capabilities()`, et renvoient un résultat
`unsupported` plutôt qu'une exception. Seul fichier autorisé à parler à ce
type de provider.
"""

import logging

import httpx

from app import config
from app.providers.base import ProviderAdapter
from app.schemas import (
    ActionResult,
    ChatMessage,
    ChatRequest,
    ChatResult,
    GenerateRequest,
    GenerateResult,
    ModelInfo,
    ProviderCapabilities,
    ProviderHealth,
)

logger = logging.getLogger("llm_cockpit.openai_compat")

_TIMEOUT = httpx.Timeout(3.0)


def _error_detail(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"erreur HTTP {exc.response.status_code}"
    return "provider injoignable"


class OpenAICompatAdapter(ProviderAdapter):
    """Provider OpenAI-compatible. base_url explicite, jamais deviné."""

    def __init__(self, base_url: str, provider_id: str = "openai_compat") -> None:
        self.base_url = base_url
        self.provider_id = provider_id

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            list_installed=True,
            list_loaded=False,   # pas d'équivalent /v1 pour les modèles chargés
            load=False,
            unload=False,
            generate=True,
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)

    def _action_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=httpx.Timeout(config.ACTION_TIMEOUT_S)
        )

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with self._client() as client:
                resp = await client.get("/v1/models")
                resp.raise_for_status()
            return ProviderHealth(
                provider=self.provider_id, base_url=self.base_url, reachable=True
            )
        except httpx.HTTPError as exc:
            return ProviderHealth(
                provider=self.provider_id,
                base_url=self.base_url,
                reachable=False,
                error=str(exc) or exc.__class__.__name__,
            )

    async def list_installed(self) -> list[ModelInfo]:
        try:
            async with self._client() as client:
                resp = await client.get("/v1/models")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("openai_compat injoignable (/v1/models) : %s", exc)
            return []

        entries = data.get("data")
        if not isinstance(entries, list):
            return []
        models: list[ModelInfo] = []
        for entry in entries:
            mid = (entry.get("id") or "").strip()
            if not mid:
                logger.warning("Modèle /v1/models sans 'id', exclu : %r", entry)
                continue
            models.append(
                ModelInfo(
                    name=mid,
                    normalized_name=mid,   # pas de convention :latest hors Ollama
                    provider=self.provider_id,
                    installed=True,
                    loaded=False,
                    source="openai",
                    raw=entry,
                )
            )
        return models

    async def list_loaded(self) -> list[ModelInfo]:
        # Non exprimable en OpenAI-compatible : jamais de faux positif.
        return []

    async def load(self, model: str, keep_alive: str = "5m") -> ActionResult:
        return ActionResult(
            action="load",
            model=model,
            provider=self.provider_id,
            status="unsupported",
            detail="load non supporté par un provider OpenAI-compatible",
        )

    async def unload(self, model: str) -> ActionResult:
        return ActionResult(
            action="unload",
            model=model,
            provider=self.provider_id,
            status="unsupported",
            detail="unload non supporté par un provider OpenAI-compatible",
        )

    async def generate(self, req: GenerateRequest) -> GenerateResult:
        body = {
            "model": req.model,
            "messages": [{"role": "user", "content": req.prompt}],
            "stream": False,
        }
        try:
            async with self._action_client() as client:
                resp = await client.post("/v1/chat/completions", json=body)
                resp.raise_for_status()
                data = resp.json()
            choices = data.get("choices") or []
            content = ""
            if choices:
                content = (choices[0].get("message") or {}).get("content", "") or ""
            usage = data.get("usage") or {}
            return GenerateResult(
                model=data.get("model", req.model),
                response=content,
                done=True,
                total_duration_ms=None,   # non fourni par le standard OpenAI
                eval_count=usage.get("completion_tokens"),
            )
        except httpx.HTTPError as exc:
            logger.warning("generate(%s) a échoué : %s", req.model, exc)
            return GenerateResult(
                model=req.model, response="", done=False, error=_error_detail(exc)
            )

    # --- V4 : chat via POST /v1/chat/completions ------------------------

    async def chat(self, req: ChatRequest) -> ChatResult:
        body = {
            "model": req.model,
            "messages": [m.model_dump() for m in req.messages],
            "stream": False,
        }
        try:
            async with self._action_client() as client:
                resp = await client.post("/v1/chat/completions", json=body)
                resp.raise_for_status()
                data = resp.json()
            choices = data.get("choices") or []
            choice = choices[0] if choices else {}
            msg = choice.get("message") or {}
            return ChatResult(
                model=data.get("model", req.model),
                message=ChatMessage(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", "") or "",
                ),
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage"),
            )
        except httpx.HTTPError as exc:
            logger.warning("chat(%s) a échoué : %s", req.model, exc)
            return ChatResult(
                model=req.model,
                message=ChatMessage(role="assistant", content=""),
                error=_error_detail(exc),
            )
