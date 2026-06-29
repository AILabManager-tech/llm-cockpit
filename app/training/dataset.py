"""Validation de dataset d'adaptation (JSONL local).

Formats acceptés par ligne (au moins un) :
  - {"prompt": ..., "response": ...}
  - {"instruction": ..., "output": ...}
  - {"messages": [ {"role": ..., "content": ...}, ... ]}

Aucune donnée n'est exécutée. L'ingestion est restreinte à DATASETS_DIR.
Aucun téléchargement distant.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.db import store
from app.schemas import Dataset


class DatasetError(Exception):
    """Chemin hors périmètre, fichier absent, ou contenu invalide."""


def _datasets_root() -> Path:
    return Path(config.DATASETS_DIR).resolve()


def resolve_in_datasets_dir(path: str) -> Path:
    root = _datasets_root()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise DatasetError(f"chemin hors du dossier autorisé : {path}")
    if not resolved.is_file():
        raise DatasetError(f"fichier introuvable : {path}")
    return resolved


def _valid_row(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("prompt") and obj.get("response"):
        return True
    if obj.get("instruction") and obj.get("output"):
        return True
    msgs = obj.get("messages")
    if isinstance(msgs, list) and msgs:
        return all(
            isinstance(m, dict) and m.get("role") and m.get("content") is not None
            for m in msgs
        )
    return False


def validate_file(path: Path) -> int:
    """Valide un JSONL ; renvoie le nombre de lignes valides. Lève sinon."""
    rows = 0
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError as exc:
                raise DatasetError(
                    f"ligne {lineno} : JSON invalide ({exc})"
                ) from exc
            if not _valid_row(obj):
                raise DatasetError(
                    f"ligne {lineno} : champs requis manquants "
                    "(prompt/response, instruction/output ou messages)"
                )
            rows += 1
    if rows < config.TRAIN_MIN_ROWS:
        raise DatasetError(
            f"dataset trop petit : {rows} ligne(s) < {config.TRAIN_MIN_ROWS}"
        )
    return rows


def create_dataset(name: str, path: str) -> Dataset:
    resolved = resolve_in_datasets_dir(path)
    rows = validate_file(resolved)
    ts = datetime.now(timezone.utc).isoformat()
    detail = f"{rows} exemples validés"
    dataset_id = store.insert_dataset(
        ts=ts, name=name, path=str(resolved), rows=rows, status="valid",
        detail=detail,
    )
    return Dataset(
        id=dataset_id, ts=ts, name=name, path=str(resolved), rows=rows,
        status="valid", detail=detail,
    )
