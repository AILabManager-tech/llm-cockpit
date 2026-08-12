"""Routage V4 : résout un `model` (rôle OU modèle réel) → (provider, modèle).

Réutilise les rôles (V2, `data/roles.json`) et le registry agrégé (V3). Le
routage ne contourne jamais la validation : il ne résout que vers un modèle
réellement présent chez un provider joignable (présent dans l'inventaire
agrégé). Pas de fallback silencieux : un rôle non assigné ou un modèle absent
donne une décision `ok=False` avec une raison claire.
"""

from app import config
from app.schemas import ModelInfo, RouteDecision
from app.services import roles as roles_module
from app.services.registry import RegistryService

_ROLE_PREFIX = "role:"


class RoutingService:
    def __init__(self, registry: RegistryService) -> None:
        self.registry = registry

    async def resolve(self, requested: str) -> RouteDecision:
        aggregate = await self.registry.aggregate_inventory()
        return self._resolve_with(aggregate, requested)

    async def routing_table(self) -> list[RouteDecision]:
        """Ce que chaque rôle résoudrait actuellement (agrégat calculé une fois)."""
        aggregate = await self.registry.aggregate_inventory()
        return [self._resolve_with(aggregate, role) for role in config.ROLES]

    def _resolve_with(
        self, aggregate: list[ModelInfo], requested: str
    ) -> RouteDecision:
        requested = (requested or "").strip() or config.GATEWAY_DEFAULT_ROLE

        is_role_syntax = requested.startswith(_ROLE_PREFIX)
        name = requested[len(_ROLE_PREFIX):] if is_role_syntax else requested
        treat_as_role = is_role_syntax or name in config.ROLES

        if treat_as_role:
            return self._resolve_role(aggregate, requested, name)
        return self._resolve_model(aggregate, requested, name)

    def _resolve_role(
        self, aggregate: list[ModelInfo], requested: str, name: str
    ) -> RouteDecision:
        if name not in config.ROLES:
            return RouteDecision(
                requested=requested, ok=False, reason=f"unknown role: {name}"
            )
        entry = roles_module._read_assignments().get(name)
        if not entry or not entry.get("model"):
            return RouteDecision(
                requested=requested, resolved_role=name, ok=False,
                reason="role not assigned",
            )
        provider = entry.get("provider", "ollama")
        model = entry["model"]
        present = any(
            m.provider == provider and m.normalized_name == model for m in aggregate
        )
        if not present:
            return RouteDecision(
                requested=requested, resolved_role=name, provider=provider,
                model=model, ok=False,
                reason="role model unavailable (provider unreachable or model missing)",
            )
        return RouteDecision(
            requested=requested, resolved_role=name, provider=provider,
            model=model, ok=True, reason=f"role '{name}' → {provider}/{model}",
        )

    def _resolve_model(
        self, aggregate: list[ModelInfo], requested: str, name: str
    ) -> RouteDecision:
        matches = [m for m in aggregate if m.normalized_name == name]
        if not matches:
            return RouteDecision(
                requested=requested, ok=False,
                reason="model not found in the aggregated inventory",
            )
        chosen = matches[0]
        return RouteDecision(
            requested=requested, provider=chosen.provider,
            model=chosen.normalized_name, ok=True,
            reason=f"real model → {chosen.provider}/{chosen.normalized_name}",
        )
