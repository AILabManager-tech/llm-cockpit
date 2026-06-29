import logging

from app.providers.base import ProviderAdapter
from app.schemas import ModelInfo

logger = logging.getLogger("llm_cockpit.inventory")


def normalize_name(entry: dict) -> str:
    raw = (entry.get("model") or entry.get("name") or "").strip()
    if not raw:
        return ""              # vide → l'appelant décide, ne pas inventer
    if ":" not in raw:
        raw = f"{raw}:latest"  # tag implicite → latest
    return raw


def merge_models(
    installed: list[ModelInfo], loaded: list[ModelInfo]
) -> list[ModelInfo]:
    """Fusionne installés (tags) + chargés (ps).

    Clé de jointure primaire = nom normalisé. `digest` ne sert que de
    validation secondaire (non bloquante) quand il est présent des deux côtés.
    """
    index: dict[str, ModelInfo] = {m.normalized_name: m for m in installed}

    for entry in loaded:
        key = entry.normalized_name
        if key in index:
            base = index[key]
            base.loaded = True
            base.size_vram = entry.size_vram
            base.expires_at = entry.expires_at
            if base.digest and entry.digest and base.digest != entry.digest:
                logger.warning(
                    "Digest incohérent pour %s : tags=%s ps=%s "
                    "(entrée tags conservée, non masquée)",
                    key,
                    base.digest,
                    entry.digest,
                )
            # On garde l'entrée "tags" et sa source.
        else:
            # Chargé mais absent de /api/tags : on l'expose quand même.
            entry.loaded = True
            entry.installed = True
            entry.source = "ps_only"
            index[key] = entry

    return list(index.values())


class InventoryService:
    """Combine les appels de l'adapter et applique la fusion. Lecture seule."""

    def __init__(self, adapter: ProviderAdapter) -> None:
        self.adapter = adapter

    async def get_inventory(self) -> list[ModelInfo]:
        installed = await self.adapter.list_installed()
        loaded = await self.adapter.list_loaded()
        return merge_models(installed, loaded)
