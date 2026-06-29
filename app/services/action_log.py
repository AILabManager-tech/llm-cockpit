"""Journal d'actions append-only au format JSONL.

Pas de base de données, pas de SQLite, pas de rotation : un fichier texte,
une ligne JSON par action. (La vraie observabilité, c'est V5.)
"""

import logging
import os
from datetime import datetime, timezone

from app import config
from app.schemas import ActionLogEntry

logger = logging.getLogger("llm_cockpit.action_log")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> str:
    return config.ACTION_LOG_PATH


def append_entry(
    *,
    action: str,
    model: str,
    status: str,
    detail: str | None = None,
    provider: str = "ollama",
) -> ActionLogEntry:
    """Ajoute une ligne au journal (open en mode 'a', jamais de réécriture)."""
    entry = ActionLogEntry(
        ts=_now_iso(),
        action=action,
        model=model,
        provider=provider,
        status=status,
        detail=detail,
    )
    path = _path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
    return entry


def read_entries(limit: int | None = None) -> list[ActionLogEntry]:
    """Retourne les entrées, les plus récentes d'abord. [] si fichier absent."""
    path = _path()
    if not os.path.exists(path):
        return []
    entries: list[ActionLogEntry] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(ActionLogEntry.model_validate_json(line))
            except ValueError:
                # Ligne corrompue : ignorée, jamais de crash de tout le journal.
                logger.warning("Ligne de journal illisible ignorée : %r", line)
    entries.reverse()  # ordre chronologique inverse (dernières en premier)
    if limit is not None:
        entries = entries[:limit]
    return entries
