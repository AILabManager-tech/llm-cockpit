"""Cycle de vie d'un job d'adaptation (supervision in-process seulement).

L'entraînement réel tourne dans un **sous-process runner externe allowlisté**
(argv liste, jamais shell). Le cockpit supervise : pending → running →
done/failed/cancelled, ou dry_run si aucun runner n'est configuré. Un job
échoué/annulé laisse le baseline intact (non destructif).
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.db import store
from app.training import registry
from app.training.runner import build_runner_argv

logger = logging.getLogger("llm_cockpit.training.job")

# Sous-process vivants (pour l'annulation). Supervision in-process uniquement.
_RUNNING: dict[int, object] = {}


class JobError(Exception):
    """Paramètres de job invalides (base model, dataset, méthode)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_output_dir(job_id: int) -> Path:
    return Path(config.ADAPTERS_DIR) / f"job_{job_id}"


async def create_job(
    dataset_id: int, base_model: str | None, method: str
) -> dict:
    if method not in config.TRAIN_ALLOWED_METHODS:
        raise JobError(f"méthode non supportée : {method}")
    resolved_base = (base_model or config.TRAIN_BASE_MODEL or "").strip()
    if not resolved_base:
        raise JobError(
            "base_model requis (fournir base_model ou définir TRAIN_BASE_MODEL)"
        )
    dataset = store.get_dataset(dataset_id)
    if dataset is None or dataset["status"] != "valid":
        raise JobError(f"dataset invalide ou introuvable : {dataset_id}")

    job_id = store.insert_train_job(
        ts=_now_iso(), dataset_id=dataset_id, base_model=resolved_base,
        method=method, status="pending",
    )
    return store.get_train_job(job_id)


async def run_job(job_id: int, spawn=asyncio.create_subprocess_exec) -> dict:
    """Exécute le job. `spawn` est injectable (tests) ; jamais de shell."""
    job = store.get_train_job(job_id)
    if job is None:
        raise JobError(f"job inconnu : {job_id}")
    dataset = store.get_dataset(job["dataset_id"])
    output_dir = _job_output_dir(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    argv = (
        build_runner_argv(
            config.TRAIN_RUNNER or "<runner>", dataset["path"],
            job["base_model"], job["method"], str(output_dir),
        )
    )

    # Pas de runner configuré → dry-run : on prépare/valide, on ne lance rien.
    if not config.TRAIN_RUNNER:
        tail = "dry-run : aucun TRAIN_RUNNER configuré. Commande qui serait " \
               f"exécutée : {' '.join(argv)}"
        store.update_train_job(job_id, status="dry_run", log_tail=tail)
        return store.get_train_job(job_id)

    store.update_train_job(job_id, status="running")
    try:
        proc = await spawn(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _RUNNING[job_id] = proc
        out, _ = await proc.communicate()
        return_code = proc.returncode
    except Exception as exc:  # noqa: BLE001 - échec runner avalé en statut
        logger.warning("job %s : échec de lancement : %s", job_id, exc)
        store.update_train_job(job_id, status="failed", log_tail=str(exc))
        return store.get_train_job(job_id)
    finally:
        _RUNNING.pop(job_id, None)

    log_tail = (out or b"").decode("utf-8", "replace")[-config.TRAIN_LOG_TAIL_MAX:]

    # Annulé entre-temps : ne pas écraser le statut "cancelled".
    current = store.get_train_job(job_id)
    if current and current["status"] == "cancelled":
        store.update_train_job(job_id, log_tail=log_tail)
        return store.get_train_job(job_id)

    if return_code == 0:
        version_id = registry.register_candidate(
            base_model=job["base_model"], method=job["method"],
            adapter_path=str(output_dir), job_id=job_id,
        )
        store.update_train_job(
            job_id, status="done", version_id=version_id, log_tail=log_tail
        )
    else:
        store.update_train_job(
            job_id, status="failed",
            log_tail=f"[exit {return_code}]\n{log_tail}",
        )
    return store.get_train_job(job_id)


async def cancel_job(job_id: int) -> dict:
    job = store.get_train_job(job_id)
    if job is None:
        raise JobError(f"job inconnu : {job_id}")
    proc = _RUNNING.get(job_id)
    if proc is not None:
        try:
            proc.terminate()
        except ProcessLookupError:  # pragma: no cover - déjà terminé
            pass
    store.update_train_job(job_id, status="cancelled")
    return store.get_train_job(job_id)
