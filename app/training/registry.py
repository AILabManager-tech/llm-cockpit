"""Versions de modèle : baseline + candidats adaptés, promote/rollback gatés.

Le baseline n'est JAMAIS écrasé : on ajoute une version. La promotion est
**gatée par la preuve V6** (le candidat doit battre le baseline sur son eval_run).
"""

from datetime import datetime, timezone

from app.db import store
from app.schemas import ModelVersion


class RegistryError(Exception):
    """Version absente / état incohérent."""


class PromotionError(Exception):
    """Promotion refusée (éval manquante ou défavorable)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Le gateway V4 sert toujours le modèle de base : « actif dans le registry » ne
# signifie PAS « servi ». On l'expose explicitement pour ne pas tromper.
_NOT_SERVED_NOTE = (
    "Version active dans le registry seulement ; le gateway sert encore le "
    "modèle de base (l'adapter n'est pas servi par /v1/chat/completions)."
)
_BASE_SERVED_NOTE = "Modèle de base réellement servi par le gateway."


def _to_model_version(d: dict) -> ModelVersion:
    if d["is_baseline"]:
        status, note = "served_as_base", _BASE_SERVED_NOTE
    else:
        status, note = "not_served", _NOT_SERVED_NOTE
    return ModelVersion(**d, serving_status=status, serving_note=note)


def ensure_baseline(base_model: str) -> dict:
    """Garantit l'existence d'un baseline (actif) pour ce base_model."""
    baseline = store.get_baseline(base_model)
    if baseline:
        return baseline
    version_id = store.insert_model_version(
        ts=_now_iso(), base_model=base_model, method=None, adapter_path=None,
        status="baseline", is_baseline=True, active=True, job_id=None,
    )
    return store.get_model_version(version_id)


def register_candidate(
    *, base_model: str, method: str, adapter_path: str | None, job_id: int | None,
) -> int:
    ensure_baseline(base_model)   # toujours un baseline pour comparer
    return store.insert_model_version(
        ts=_now_iso(), base_model=base_model, method=method,
        adapter_path=adapter_path, status="candidate", is_baseline=False,
        active=False, job_id=job_id,
    )


def run_pass_rate(eval_run_id: int) -> float:
    """Taux de checks réussis pour un run V6 (preuve de promotion)."""
    results = store.get_eval_results(eval_run_id)
    passed = sum(r["passed"] for r in results)
    total = sum(r["total"] for r in results)
    return (passed / total) if total else 0.0


def attach_eval(version_id: int, eval_run_id: int) -> ModelVersion:
    version = store.get_model_version(version_id)
    if version is None:
        raise RegistryError(f"unknown version: {version_id}")
    rate = run_pass_rate(eval_run_id)
    store.set_version_eval(version_id, eval_run_id, rate)
    return _to_model_version(store.get_model_version(version_id))


def promote(version_id: int) -> ModelVersion:
    version = store.get_model_version(version_id)
    if version is None:
        raise RegistryError(f"unknown version: {version_id}")
    if version["is_baseline"]:
        raise PromotionError("the baseline is already the reference")
    if version["eval_run_id"] is None or version["pass_rate"] is None:
        raise PromotionError("no evaluation attached to this version")

    baseline = store.get_baseline(version["base_model"])
    if baseline is None or baseline["pass_rate"] is None:
        raise PromotionError("baseline not evaluated: comparison impossible")

    if version["pass_rate"] <= baseline["pass_rate"]:
        raise PromotionError(
            f"évals défavorables : candidat {version['pass_rate']:.3f} "
            f"<= baseline {baseline['pass_rate']:.3f}"
        )

    store.set_active_version(version["base_model"], version_id)
    return _to_model_version(store.get_model_version(version_id))


def rollback(version_id: int) -> ModelVersion:
    """Revient au baseline (non destructif : le candidat reste enregistré)."""
    version = store.get_model_version(version_id)
    if version is None:
        raise RegistryError(f"unknown version: {version_id}")
    baseline = store.get_baseline(version["base_model"])
    if baseline is None:
        raise RegistryError("no baseline to restore")
    store.set_active_version(version["base_model"], baseline["id"])
    return _to_model_version(store.get_model_version(baseline["id"]))


def list_versions() -> list[ModelVersion]:
    return [_to_model_version(v) for v in store.list_model_versions()]
