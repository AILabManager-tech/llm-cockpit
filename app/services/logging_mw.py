"""Écriture best-effort d'un log de requête gateway dans SQLite.

Applique la politique PII : le contenu du prompt n'est stocké que si
`LOG_PROMPTS=1`, et tronqué à `LOG_PROMPT_MAX_CHARS`. Toute erreur est avalée
en amont par `store.insert_request_log` : le logging n'échoue jamais la requête.
"""

import logging
from datetime import datetime, timezone

from app import config
from app.db import store

logger = logging.getLogger("llm_cockpit.logging_mw")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prompt_field(prompt: str | None) -> str | None:
    if not config.LOG_PROMPTS or not prompt:
        return None
    return prompt[: config.LOG_PROMPT_MAX_CHARS]


def log_request(
    *,
    route: str,
    app: str | None,
    requested: str | None,
    resolved_role: str | None,
    provider: str | None,
    model: str | None,
    status: str,
    http_status: int,
    latency_ms: float | None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error: str | None = None,
    prompt: str | None = None,
) -> None:
    # Best-effort absolu : aucune erreur de logging ne remonte au gateway.
    try:
        store.insert_request_log(
            {
                "ts": _now_iso(),
                "route": route,
                "app": app,
                "requested": requested,
                "resolved_role": resolved_role,
                "provider": provider,
                "model": model,
                "status": status,
                "http_status": http_status,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "error": error,
                "prompt": _prompt_field(prompt),
            }
        )
    except Exception as exc:  # noqa: BLE001 — garantie best-effort
        logger.warning("log gateway ignoré (best-effort) : %s", exc)
