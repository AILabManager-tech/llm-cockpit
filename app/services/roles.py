"""Rôles locaux de modèles : préférence déclarée, persistée en JSON local.

V2 raisonne en usages (rôles) plutôt qu'en noms de modèles. Mono-provider
(Ollama). Pas d'optimiseur : on enregistre une préférence manuelle, on ne
choisit pas « le meilleur » modèle. Pas de base de données : un fichier JSON,
écrit atomiquement (tmp + os.replace).
"""

import json
import os
from datetime import datetime, timezone

from app import config
from app.schemas import ActionResult, RoleAssignment
from app.services.actions import ActionService
from app.services.inventory import InventoryService, normalize_name


class UnknownRoleError(Exception):
    """Rôle absent de l'énumération figée config.ROLES."""


class RoleNotAssignedError(Exception):
    """Rôle connu mais sans modèle assigné."""


class ModelNotInstalledError(Exception):
    """Modèle demandé absent de l'inventaire installé."""


class RolesConfigError(Exception):
    """Fichier roles.json présent mais illisible / corrompu."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> str:
    return config.ROLES_CONFIG_PATH


def _read_assignments() -> dict[str, dict]:
    """Charge les assignations brutes. {} si fichier absent (état vide).

    Corrompu → RolesConfigError (jamais d'écrasement silencieux).
    """
    path = _path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError) as exc:
        raise RolesConfigError(f"roles.json illisible : {exc}") from exc
    assignments = data.get("assignments") if isinstance(data, dict) else None
    if not isinstance(assignments, dict):
        raise RolesConfigError(
            "roles.json corrompu : clé 'assignments' manquante ou invalide"
        )
    return assignments


def _write_assignments(assignments: dict[str, dict]) -> None:
    """Écriture atomique : tmp + os.replace."""
    path = _path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"assignments": assignments}, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class RoleService:
    """Charge/sauvegarde roles.json, valide, et délègue le test au service V1."""

    def __init__(
        self, inventory: InventoryService, action_service: ActionService
    ) -> None:
        self.inventory = inventory
        self.action_service = action_service

    async def _installed_names(self) -> set[str]:
        models = await self.inventory.get_inventory()  # réutilise la fusion V0
        return {m.normalized_name for m in models if m.installed}

    async def list_roles(self) -> list[RoleAssignment]:
        """Tous les rôles figés, dans l'ordre, assignés ou non."""
        stored = _read_assignments()
        result: list[RoleAssignment] = []
        for role in config.ROLES:
            entry = stored.get(role)
            if entry and entry.get("model"):
                result.append(
                    RoleAssignment(
                        role=role,
                        provider=entry.get("provider", "ollama"),
                        model=entry.get("model"),
                        updated_at=entry.get("updated_at"),
                    )
                )
            else:
                result.append(RoleAssignment(role=role))  # non assigné
        return result

    async def set_role(self, role: str, model: str) -> RoleAssignment:
        if role not in config.ROLES:
            raise UnknownRoleError(role)
        norm = normalize_name({"model": model})
        if not norm:
            raise ModelNotInstalledError("nom de modèle vide")
        if norm not in await self._installed_names():
            raise ModelNotInstalledError(norm)

        stored = _read_assignments()
        stored[role] = {
            "model": norm,
            "provider": "ollama",
            "updated_at": _now_iso(),
        }
        _write_assignments(stored)
        return RoleAssignment(
            role=role,
            provider="ollama",
            model=norm,
            updated_at=stored[role]["updated_at"],
        )

    async def test_role(
        self, role: str, prompt: str | None = None
    ) -> tuple[ActionResult, int]:
        if role not in config.ROLES:
            raise UnknownRoleError(role)
        stored = _read_assignments()
        entry = stored.get(role)
        if not entry or not entry.get("model"):
            raise RoleNotAssignedError(role)
        # Réutilise STRICTEMENT le chemin de test V1 (validation + journal).
        return await self.action_service.run(
            "test", entry["model"], prompt=prompt
        )
