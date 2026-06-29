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
        raise RegistryError(f"version inconnue : {version_id}")
    rate = run_pass_rate(eval_run_id)
    store.set_version_eval(version_id, eval_run_id, rate)
    return ModelVersion(**store.get_model_version(version_id))


def promote(version_id: int) -> ModelVersion:
    version = store.get_model_version(version_id)
    if version is None:
        raise RegistryError(f"version inconnue : {version_id}")
    if version["is_baseline"]:
        raise PromotionError("le baseline est déjà la référence")
    if version["eval_run_id"] is None or version["pass_rate"] is None:
        raise PromotionError("aucune évaluation associée à cette version")

    baseline = store.get_baseline(version["base_model"])
    if baseline is None or baseline["pass_rate"] is None:
        raise PromotionError("baseline non évalué : comparaison impossible")

    if version["pass_rate"] <= baseline["pass_rate"]:
        raise PromotionError(
            f"évals défavorables : candidat {version['pass_rate']:.3f} "
            f"<= baseline {baseline['pass_rate']:.3f}"
        )

    store.set_active_version(version["base_model"], version_id)
    return ModelVersion(**store.get_model_version(version_id))


def rollback(version_id: int) -> ModelVersion:
    """Revient au baseline (non destructif : le candidat reste enregistré)."""
    version = store.get_model_version(version_id)
    if version is None:
        raise RegistryError(f"version inconnue : {version_id}")
    baseline = store.get_baseline(version["base_model"])
    if baseline is None:
        raise RegistryError("aucun baseline à restaurer")
    store.set_active_version(version["base_model"], baseline["id"])
    return ModelVersion(**store.get_model_version(baseline["id"]))


def list_versions() -> list[ModelVersion]:
    return [ModelVersion(**v) for v in store.list_model_versions()]
