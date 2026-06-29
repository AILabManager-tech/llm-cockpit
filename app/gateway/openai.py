"""Gateway OpenAI-compatible minimal (local uniquement).

Expose `/v1/chat/completions` et `/v1/models`. Une requête `model` peut être un
nom de rôle ("code", "role:code") ou un modèle réel : le routeur résout vers
(provider, modèle), le provider réel reste derrière. Erreurs au format OpenAI
(objet `error`), jamais de stacktrace. Aucune mesure d'observabilité (V5).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import config
from app.schemas import ChatRequest
from app.services.registry import RegistryConfigError, RegistryService
from app.services.roles import RolesConfigError
from app.services.routing import RoutingService

router = APIRouter()


def _openai_error(status: int, message: str, err_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": err_type, "code": err_type}},
    )


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    if not config.GATEWAY_ENABLED:
        return _openai_error(404, "gateway désactivé", "not_found")

    registry = RegistryService()
    routing = RoutingService(registry)
    requested = req.model or config.GATEWAY_DEFAULT_ROLE
    try:
        decision = await routing.resolve(requested)
    except (RegistryConfigError, RolesConfigError) as exc:
        return _openai_error(400, str(exc), "configuration_error")

    if not decision.ok:
        return _openai_error(400, decision.reason, "invalid_request_error")

    adapter = registry.adapter_for(decision.provider)
    if adapter is None:
        return _openai_error(
            400, f"provider indisponible : {decision.provider}",
            "invalid_request_error",
        )

    result = await adapter.chat(
        ChatRequest(model=decision.model, messages=req.messages)
    )
    if result.error:
        return _openai_error(502, result.error, "upstream_error")

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
        return _openai_error(404, "gateway désactivé", "not_found")

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
