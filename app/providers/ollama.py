import logging

import httpx

from app import config
from app.providers.base import ProviderAdapter
from app.schemas import (
    ActionResult,
    GenerateRequest,
    GenerateResult,
    ModelInfo,
    ProviderHealth,
)
from app.services.inventory import normalize_name

logger = logging.getLogger("llm_cockpit.ollama")

_TIMEOUT = httpx.Timeout(3.0)


def _ns_to_ms(value: int | None) -> float | None:
    """Convertit une durée Ollama (nanosecondes) en millisecondes."""
    if value is None:
        return None
    return value / 1_000_000


def _action_error_detail(exc: httpx.HTTPError) -> str:
    """Message d'erreur contrôlé, jamais de stacktrace brute exposée."""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"erreur Ollama HTTP {exc.response.status_code}"
    return "provider injoignable"


def _parse_entry(entry: dict, *, source: str, loaded: bool) -> ModelInfo | None:
    """Construit un ModelInfo depuis une entrée brute Ollama.

    Retourne None si l'entrée n'a aucun identifiant exploitable
    (ni `name` ni `model`) : elle est exclue, jamais inventée.
    """
    normalized = normalize_name(entry)
    if not normalized:
        logger.warning(
            "Entrée Ollama sans identifiant (ni name ni model), exclue : %r",
            entry,
        )
        return None

    details = entry.get("details") or {}
    return ModelInfo(
        name=(entry.get("model") or entry.get("name") or "").strip(),
        normalized_name=normalized,
        loaded=loaded,
        source=source,
        size=entry.get("size"),
        size_vram=entry.get("size_vram"),
        digest=entry.get("digest"),
        modified_at=entry.get("modified_at"),
        expires_at=entry.get("expires_at"),
        family=details.get("family"),
        quantization=details.get("quantization_level"),
        raw=entry,
    )


class OllamaAdapter(ProviderAdapter):
    """Seul fichier autorisé à parler à Ollama (GET /api/tags, GET /api/ps)."""

    provider = "ollama"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)

    def _action_client(self) -> httpx.AsyncClient:
        # Les actions (load/unload/test) peuvent être lentes : timeout dédié.
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=httpx.Timeout(config.ACTION_TIMEOUT_S)
        )

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with self._client() as client:
                resp = await client.get("/api/tags")
                resp.raise_for_status()
            return ProviderHealth(
                provider=self.provider, base_url=self.base_url, reachable=True
            )
        except httpx.HTTPError as exc:
            return ProviderHealth(
                provider=self.provider,
                base_url=self.base_url,
                reachable=False,
                error=str(exc) or exc.__class__.__name__,
            )

    async def _fetch_models(self, path: str) -> list[dict]:
        async with self._client() as client:
            resp = await client.get(path)
            resp.raise_for_status()
            data = resp.json()
        models = data.get("models")
        if not isinstance(models, list):
            return []
        return models

    async def list_installed(self) -> list[ModelInfo]:
        try:
            raw_models = await self._fetch_models("/api/tags")
        except httpx.HTTPError as exc:
            logger.warning("Ollama injoignable (/api/tags) : %s", exc)
            return []
        parsed = [_parse_entry(m, source="tags", loaded=False) for m in raw_models]
        return [m for m in parsed if m is not None]

    async def list_loaded(self) -> list[ModelInfo]:
        try:
            raw_models = await self._fetch_models("/api/ps")
        except httpx.HTTPError as exc:
            logger.warning("Ollama injoignable (/api/ps) : %s", exc)
            return []
        parsed = [_parse_entry(m, source="ps", loaded=True) for m in raw_models]
        return [m for m in parsed if m is not None]

    # --- V1 : contrôle via POST /api/generate (API native) --------------

    async def load(self, model: str, keep_alive: str = "5m") -> ActionResult:
        body = {"model": model, "keep_alive": keep_alive}
        try:
            async with self._action_client() as client:
                resp = await client.post("/api/generate", json=body)
                resp.raise_for_status()
                data = resp.json()
            return ActionResult(
                action="load",
                model=model,
                status="ok",
                detail="modèle chargé",
                duration_ms=_ns_to_ms(data.get("total_duration")),
            )
        except httpx.HTTPError as exc:
            logger.warning("load(%s) a échoué : %s", model, exc)
            return ActionResult(
                action="load",
                model=model,
                status="error",
                detail=_action_error_detail(exc),
            )

    async def unload(self, model: str) -> ActionResult:
        body = {"model": model, "keep_alive": 0}
        try:
            async with self._action_client() as client:
                resp = await client.post("/api/generate", json=body)
                resp.raise_for_status()
                data = resp.json()
            return ActionResult(
                action="unload",
                model=model,
                status="ok",
                detail="modèle déchargé",
                duration_ms=_ns_to_ms(data.get("total_duration")),
            )
        except httpx.HTTPError as exc:
            logger.warning("unload(%s) a échoué : %s", model, exc)
            return ActionResult(
                action="unload",
                model=model,
                status="error",
                detail=_action_error_detail(exc),
            )

    async def generate(self, req: GenerateRequest) -> GenerateResult:
        body: dict = {"model": req.model, "prompt": req.prompt, "stream": False}
        if req.options:
            body["options"] = req.options
        try:
            async with self._action_client() as client:
                resp = await client.post("/api/generate", json=body)
                resp.raise_for_status()
                data = resp.json()
            return GenerateResult(
                model=data.get("model", req.model),
                response=data.get("response", ""),
                done=bool(data.get("done", False)),
                total_duration_ms=_ns_to_ms(data.get("total_duration")),
                eval_count=data.get("eval_count"),
            )
        except httpx.HTTPError as exc:
            logger.warning("generate(%s) a échoué : %s", req.model, exc)
            return GenerateResult(
                model=req.model,
                response="",
                done=False,
                error=_action_error_detail(exc),
            )
