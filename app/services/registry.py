"""Registry local de providers : agrégation multi-provider + détection de drift.

Persistance JSON local (`data/providers.json`), écriture atomique. Aucune base
de données. Si le fichier est absent → un seul provider Ollama par défaut
(depuis OLLAMA_BASE_URL), jamais d'invention d'un second provider.

Un provider injoignable est isolé : il n'invalide pas les autres et n'apparaît
pas dans l'agrégat, mais reste visible dans le statut et le drift.
"""

import json
import os

from app import config
from app.providers.base import ProviderAdapter
from app.providers.ollama import OllamaAdapter
from app.providers.openai_compat import OpenAICompatAdapter
from app.schemas import (
    ModelInfo,
    ProviderCapabilities,
    ProviderConfig,
    ProviderStatus,
    RegistryDrift,
)
from app.services.inventory import merge_models

KINDS = {"ollama", "openai_compat"}


class RegistryConfigError(Exception):
    """providers.json présent mais illisible / corrompu."""


class DuplicateProviderError(Exception):
    """id ou base_url déjà enregistré."""


class UnknownProviderError(Exception):
    """provider absent du registry."""


class UnknownProviderKindError(Exception):
    """kind de provider non pris en charge."""


def _path() -> str:
    return config.PROVIDERS_CONFIG_PATH


def _default_providers() -> list[ProviderConfig]:
    return [
        ProviderConfig(
            id="ollama", kind="ollama", base_url=config.OLLAMA_BASE_URL, enabled=True
        )
    ]


def _read_providers() -> list[ProviderConfig]:
    path = _path()
    if not os.path.exists(path):
        return _default_providers()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError) as exc:
        raise RegistryConfigError(f"providers.json unreadable: {exc}") from exc
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, list):
        raise RegistryConfigError(
            "providers.json corrompu : clé 'providers' manquante ou invalide"
        )
    result: list[ProviderConfig] = []
    for entry in providers:
        try:
            result.append(ProviderConfig(**entry))
        except (TypeError, ValueError) as exc:
            raise RegistryConfigError(
                f"invalid provider entry: {entry!r}"
            ) from exc
    return result


def _write_providers(providers: list[ProviderConfig]) -> None:
    path = _path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(
            {"providers": [p.model_dump() for p in providers]},
            fh,
            ensure_ascii=False,
            indent=2,
        )
    os.replace(tmp, path)


def _build_adapter(pc: ProviderConfig) -> ProviderAdapter:
    if pc.kind == "ollama":
        return OllamaAdapter(base_url=pc.base_url)
    if pc.kind == "openai_compat":
        return OpenAICompatAdapter(base_url=pc.base_url, provider_id=pc.id)
    raise UnknownProviderKindError(pc.kind)


class RegistryService:
    def list_providers(self) -> list[ProviderConfig]:
        return _read_providers()

    def register(self, pc: ProviderConfig) -> ProviderConfig:
        if pc.kind not in KINDS:
            raise UnknownProviderKindError(pc.kind)
        providers = _read_providers()
        if any(p.id == pc.id for p in providers):
            raise DuplicateProviderError(f"id already registered: {pc.id}")
        if any(p.base_url == pc.base_url for p in providers):
            raise DuplicateProviderError(
                f"base_url already registered: {pc.base_url}"
            )
        providers.append(pc)
        _write_providers(providers)
        return pc

    def remove(self, provider_id: str) -> None:
        providers = _read_providers()
        if not any(p.id == provider_id for p in providers):
            raise UnknownProviderError(provider_id)
        _write_providers([p for p in providers if p.id != provider_id])

    def _safe_adapter(self, pc: ProviderConfig) -> ProviderAdapter | None:
        try:
            return _build_adapter(pc)
        except UnknownProviderKindError:
            return None

    def adapter_for(self, provider_id: str) -> ProviderAdapter | None:
        """Adapter d'un provider du registry par id (None si absent/kind inconnu)."""
        for pc in _read_providers():
            if pc.id == provider_id:
                return self._safe_adapter(pc)
        return None

    async def aggregate_inventory(self) -> list[ModelInfo]:
        """Inventaire agrégé sur tous les providers activés (concaténation).

        Pas de fusion inter-provider : chaque ModelInfo garde son provider.
        Un provider injoignable contribue [] sans casser les autres.
        """
        aggregate: list[ModelInfo] = []
        for pc in _read_providers():
            if not pc.enabled:
                continue
            adapter = self._safe_adapter(pc)
            if adapter is None:
                continue
            installed = await adapter.list_installed()
            loaded = await adapter.list_loaded()
            merged = merge_models(installed, loaded)
            for model in merged:
                model.provider = pc.id
            aggregate.extend(merged)
        return aggregate

    async def provider_statuses(self) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        for pc in _read_providers():
            adapter = self._safe_adapter(pc)
            if adapter is None:
                statuses.append(
                    ProviderStatus(
                        id=pc.id, kind=pc.kind, base_url=pc.base_url,
                        enabled=pc.enabled, reachable=False,
                        error="kind de provider inconnu",
                        capabilities=ProviderCapabilities(),
                    )
                )
                continue
            health = await adapter.healthcheck()
            count = 0
            if pc.enabled and health.reachable:
                count = len(await adapter.list_installed())
            statuses.append(
                ProviderStatus(
                    id=pc.id, kind=pc.kind, base_url=pc.base_url,
                    enabled=pc.enabled, reachable=health.reachable,
                    error=health.error, capabilities=adapter.capabilities(),
                    model_count=count,
                )
            )
        return statuses

    async def compute_drift(self) -> list[RegistryDrift]:
        """Drift = désaccord entre l'état déclaré et la réalité observée.

        - déclaré actif (enabled) mais injoignable → drift ;
        - déclaré désactivé mais répond quand même → drift (présent inattendu).
        Jamais masqué.
        """
        drifts: list[RegistryDrift] = []
        for pc in _read_providers():
            adapter = self._safe_adapter(pc)
            detail: str | None = None
            if adapter is None:
                reachable = False
                detail = "kind de provider inconnu"
                drift = True
            else:
                health = await adapter.healthcheck()
                reachable = health.reachable
                drift = pc.enabled != reachable
                if drift and pc.enabled and not reachable:
                    detail = "déclaré actif mais injoignable"
                elif drift and not pc.enabled and reachable:
                    detail = "déclaré désactivé mais répond"
            drifts.append(
                RegistryDrift(
                    provider_id=pc.id, base_url=pc.base_url, enabled=pc.enabled,
                    reachable=reachable, drift=drift, detail=detail,
                )
            )
        return drifts
