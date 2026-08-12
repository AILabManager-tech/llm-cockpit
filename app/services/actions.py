"""Orchestration des actions de contrôle : validation → adapter → journal.

Ce service DÉCIDE (allowlist, présence du modèle, actions activées).
L'adapter EXÉCUTE. Ce service ne parle jamais à Ollama directement.
"""

from app import config
from app.providers.base import ProviderAdapter
from app.schemas import ActionResult, GenerateRequest
from app.services import action_log
from app.services.inventory import InventoryService, normalize_name

DEFAULT_TEST_PROMPT = "Reply with OK."


class ActionService:
    def __init__(
        self, adapter: ProviderAdapter, inventory: InventoryService
    ) -> None:
        self.adapter = adapter
        self.inventory = inventory

    async def _installed_and_loaded_names(self) -> tuple[set[str], set[str]]:
        models = await self.inventory.get_inventory()  # réutilise la fusion V0
        installed = {m.normalized_name for m in models if m.installed}
        loaded = {m.normalized_name for m in models if m.loaded}
        return installed, loaded

    async def run(
        self, action: str, model: str, prompt: str | None = None
    ) -> tuple[ActionResult, int]:
        """Retourne (ActionResult, http_status). Journalise chaque tentative."""
        # 1. Actions globalement désactivées.
        if not config.ACTIONS_ENABLED:
            action_log.append_entry(
                action=action, model=model, status="refused",
                detail="actions disabled",
            )
            return (
                ActionResult(
                    action=action, model=model, status="unsupported",
                    detail="actions disabled",
                ),
                403,
            )

        # 2. Hors allowlist → refus, AUCUN appel Ollama.
        if action not in config.ACTION_ALLOWLIST:
            action_log.append_entry(
                action=action, model=model, status="refused",
                detail="action not in allowlist",
            )
            return (
                ActionResult(
                    action=action, model=model, status="unsupported",
                    detail="action not in allowlist",
                ),
                400,
            )

        # 3. Nom de modèle exploitable (comparaison sur nom normalisé).
        norm = normalize_name({"model": model})
        if not norm:
            action_log.append_entry(
                action=action, model=model, status="refused",
                detail="empty model name",
            )
            return (
                ActionResult(
                    action=action, model=model, status="error",
                    detail="empty model name",
                ),
                400,
            )

        # 4. Le modèle doit réellement exister dans l'inventaire.
        installed, loaded = await self._installed_and_loaded_names()
        if action in {"load", "test"} and norm not in installed:
            action_log.append_entry(
                action=action, model=norm, status="refused",
                detail="model not installed",
            )
            return (
                ActionResult(
                    action=action, model=norm, status="error",
                    detail="model not installed",
                ),
                400,
            )
        if action == "unload" and norm not in loaded:
            action_log.append_entry(
                action=action, model=norm, status="refused",
                detail="model not loaded",
            )
            return (
                ActionResult(
                    action=action, model=norm, status="error",
                    detail="model not loaded",
                ),
                400,
            )

        # 5. Exécution via l'adapter.
        if action == "load":
            result = await self.adapter.load(norm)
        elif action == "unload":
            result = await self.adapter.unload(norm)
        else:  # test
            gen = await self.adapter.generate(
                GenerateRequest(model=norm, prompt=prompt or DEFAULT_TEST_PROMPT)
            )
            if gen.error:
                result = ActionResult(
                    action="test", model=norm, status="error",
                    detail=gen.error, duration_ms=gen.total_duration_ms,
                )
            else:
                result = ActionResult(
                    action="test", model=norm, status="ok",
                    detail=gen.response, duration_ms=gen.total_duration_ms,
                )

        # 6. Journalisation du résultat d'exécution.
        action_log.append_entry(
            action=result.action, model=result.model,
            status=result.status, detail=result.detail,
        )
        # Erreur d'exécution (ex. Ollama injoignable) → 200 + corps d'erreur.
        return result, 200
