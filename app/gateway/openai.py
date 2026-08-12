"""Gateway OpenAI-compatible minimal (local uniquement).

Expose `/v1/chat/completions` et `/v1/models`. Une requête `model` peut être un
nom de rôle ("code", "role:code") ou un modèle réel : le routeur résout vers
(provider, modèle), le provider réel reste derrière. Erreurs au format OpenAI
(objet `error`), jamais de stacktrace.

V5 : chaque requête `/v1/chat/completions` (succès, refus ou erreur) est
journalisée best-effort dans SQLite (latence, provider, modèle, rôle, statut,
app appelante, tokens si fournis). Le logging n'échoue jamais la requête.
"""

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import config
from app.schemas import ChatRequest
from app.services import logging_mw
from app.services.registry import RegistryConfigError, RegistryService
from app.services.roles import RolesConfigError
from app.services.routing import RoutingService

router = APIRouter()

_CHAT_ROUTE = "/v1/chat/completions"


def _openai_error(status: int, message: str, err_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": err_type, "code": err_type}},
    )


def _last_user_prompt(messages) -> str | None:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return None


@router.post(_CHAT_ROUTE)
async def chat_completions(req: ChatRequest, request: Request):
    if not config.GATEWAY_ENABLED:
        return _openai_error(404, "gateway disabled", "not_found")

    app_name = request.headers.get("x-cockpit-app") or None
    started = time.perf_counter()

    def _latency_ms() -> float:
        return (time.perf_counter() - started) * 1000.0

    registry = RegistryService()
    routing = RoutingService(registry)
    requested = req.model or config.GATEWAY_DEFAULT_ROLE

    try:
        decision = await routing.resolve(requested)
    except (RegistryConfigError, RolesConfigError) as exc:
        logging_mw.log_request(
            route=_CHAT_ROUTE, app=app_name, requested=requested,
            resolved_role=None, provider=None, model=None, status="error",
            http_status=400, latency_ms=_latency_ms(), error=str(exc),
        )
        return _openai_error(400, str(exc), "configuration_error")

    if not decision.ok:
        logging_mw.log_request(
            route=_CHAT_ROUTE, app=app_name, requested=requested,
            resolved_role=decision.resolved_role, provider=decision.provider,
            model=decision.model, status="refused", http_status=400,
            latency_ms=_latency_ms(), error=decision.reason,
        )
        return _openai_error(400, decision.reason, "invalid_request_error")

    adapter = registry.adapter_for(decision.provider)
    if adapter is None:
        logging_mw.log_request(
            route=_CHAT_ROUTE, app=app_name, requested=requested,
            resolved_role=decision.resolved_role, provider=decision.provider,
            model=decision.model, status="error", http_status=400,
            latency_ms=_latency_ms(), error="provider indisponible",
        )
        return _openai_error(
            400, f"provider indisponible : {decision.provider}",
            "invalid_request_error",
        )

    result = await adapter.chat(
        ChatRequest(model=decision.model, messages=req.messages)
    )
    latency_ms = _latency_ms()
    usage = result.usage or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")

    if result.error:
        logging_mw.log_request(
            route=_CHAT_ROUTE, app=app_name, requested=requested,
            resolved_role=decision.resolved_role, provider=decision.provider,
            model=decision.model, status="error", http_status=502,
            latency_ms=latency_ms, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, error=result.error,
        )
        return _openai_error(502, result.error, "upstream_error")

    logging_mw.log_request(
        route=_CHAT_ROUTE, app=app_name, requested=requested,
        resolved_role=decision.resolved_role, provider=decision.provider,
        model=decision.model, status="ok", http_status=200,
        latency_ms=latency_ms, prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt=_last_user_prompt(req.messages),
    )

    return {
        "id": "chatcmpl-cockpit",
        "object": "chat.completion",
        "model": decision.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": result.message.role,
                    "content": result.message.content,
                },
                "finish_reason": result.finish_reason or "stop",
            }
        ],
        "usage": result.usage or {},
        # Métadonnée de routage (non standard OpenAI, préfixée x_).
        "x_cockpit_route": {
            "requested": decision.requested,
            "resolved_role": decision.resolved_role,
            "provider": decision.provider,
            "model": decision.model,
        },
    }


@router.get("/v1/models")
async def list_models():
    if not config.GATEWAY_ENABLED:
        return _openai_error(404, "gateway disabled", "not_found")

    registry = RegistryService()
    try:
        aggregate = await registry.aggregate_inventory()
    except RegistryConfigError as exc:
        return _openai_error(400, str(exc), "configuration_error")

    data = [
        {"id": m.normalized_name, "object": "model", "owned_by": m.provider}
        for m in aggregate
    ]
    # Alias de rôles exposés à côté des modèles réels.
    data.extend(
        {"id": f"role:{role}", "object": "model", "owned_by": "cockpit-role"}
        for role in config.ROLES
    )
    return {"object": "list", "data": data}
